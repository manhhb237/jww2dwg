import os
import shutil
import subprocess
from pathlib import Path
from math import pi, radians
from collections import defaultdict, deque
import ezjww

# Common install paths for ODA File Converter on Windows
COMMON_ODA_PATHS = [
    r"C:\Program Files\ODA\ODAFileConverter 27.1.0\ODAFileConverter.exe",
    r"C:\Program Files\ODA\ODAFileConverter 26.1.0\ODAFileConverter.exe",
    r"C:\Program Files\ODA\ODAFileConverter\ODAFileConverter.exe",
    r"C:\Program Files (x86)\ODA\ODAFileConverter\ODAFileConverter.exe",
]

# ODA version string mapping
ODA_VERSION_MAP = {
    "R2018": "ACAD2018",
    "R2013": "ACAD2013",
    "R2010": "ACAD2010",
    "R2007": "ACAD2007",
    "R2004": "ACAD2004",
    "R2000": "ACAD2000",
}

def find_oda_converter() -> str:
    """Scan the system for ODA File Converter executable."""
    for path in COMMON_ODA_PATHS:
        if os.path.exists(path):
            return path
    which_path = shutil.which("ODAFileConverter.exe")
    if which_path:
        return which_path
    return ""

def _run_oda_direct(oda_exe: str, input_dir: str, output_dir: str, 
                     dwg_version: str, input_filename: str) -> bool:
    """
    Run ODA File Converter directly via command line.
    ODA syntax: ODAFileConverter "InputFolder" "OutputFolder" ACAD_VER DWG 0 1 "filename"
    - ACAD_VER: target version e.g. ACAD2018
    - DWG: output format
    - 0: recursive off
    - 1: audit on
    """
    oda_ver = ODA_VERSION_MAP.get(dwg_version, "ACAD2018")
    
    cmd = [
        oda_exe,
        input_dir,      # Input folder
        output_dir,     # Output folder
        oda_ver,        # Output version
        "DWG",          # Output format
        "0",            # Recursive: 0 = no
        "1",            # Audit: 1 = yes
        input_filename  # Filter: single file
    ]
    
    try:
        si = None
        cf = 0
        if os.name == 'nt':
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            si.wShowWindow = 0  # SW_HIDE
            cf = subprocess.CREATE_NO_WINDOW
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            timeout=120,
            startupinfo=si,
            creationflags=cf
        )
        return True
    except subprocess.TimeoutExpired:
        return False
    except Exception:
        return False

def _extended_font_family(font_name: str) -> str:
    """Return a TrueType family name for CAD text styles when known."""
    normalized = font_name.lower().strip()
    mapping = {
        "msgothic.ttc": "MS Gothic",
        "ms gothic": "MS Gothic",
        "meiryo.ttc": "Meiryo",
        "meiryo": "Meiryo",
        "yugothic.ttc": "Yu Gothic",
        "yu gothic": "Yu Gothic",
        "arial.ttf": "Arial",
        "arial": "Arial",
        "times new roman": "Times New Roman",
        "times.ttf": "Times New Roman",
        "vni-times.ttf": "VNI-Times",
    }
    return mapping.get(normalized, "")


def _entity_display_length(entity) -> float | None:
    """Approximate visible entity length for linetype-fragment heuristics."""
    dxftype = entity.dxftype()
    if dxftype == "LINE":
        start = entity.dxf.start
        end = entity.dxf.end
        return ((start.x - end.x) ** 2 + (start.y - end.y) ** 2) ** 0.5
    if dxftype == "ARC":
        angle = (entity.dxf.end_angle - entity.dxf.start_angle) % 360
        if angle == 0:
            angle = 360
        return abs(radians(angle) * entity.dxf.radius)
    if dxftype == "CIRCLE":
        return 2 * pi * entity.dxf.radius
    return None


def _fix_fragmented_linetypes(doc) -> None:
    """
    JWW pen styles sometimes arrive as DASHED on fixture curves split into many
    tiny ARC/LINE pieces. AutoCAD applies the dash pattern to every tiny piece,
    which makes fixtures look shattered. Normalize only layers that clearly
    match that fragmented-curve pattern.
    """
    from collections import defaultdict

    geometry_types = {"LINE", "ARC", "CIRCLE"}
    continuous = {"continuous", "bylayer", "byblock"}
    layer_lengths: dict[str, list[float]] = defaultdict(list)
    layer_arc_counts: dict[str, int] = defaultdict(int)

    for entity in doc.modelspace():
        if entity.dxftype() not in geometry_types:
            continue
        if entity.dxf.linetype.lower() in continuous:
            continue
        length = _entity_display_length(entity)
        if length is None:
            continue
        layer_lengths[entity.dxf.layer].append(length)
        if entity.dxftype() == "ARC":
            layer_arc_counts[entity.dxf.layer] += 1

    layers_to_normalize = set()
    for layer, lengths in layer_lengths.items():
        if layer_arc_counts[layer] < 20 or len(lengths) < 30:
            continue
        sorted_lengths = sorted(lengths)
        median_length = sorted_lengths[len(sorted_lengths) // 2]
        short_ratio = sum(1 for length in lengths if length <= 5.0) / len(lengths)
        if median_length <= 2.0 and short_ratio >= 0.7:
            layers_to_normalize.add(layer)

    if not layers_to_normalize:
        return

    for entity in doc.modelspace():
        if entity.dxftype() in geometry_types and entity.dxf.layer in layers_to_normalize:
            if entity.dxf.linetype.lower() not in continuous:
                entity.dxf.linetype = "Continuous"


def _layer_group_metadata(jww_path: Path) -> tuple[dict[str, float], dict[tuple[int, int], str]]:
    """Read JWW layer group scales and layer names."""
    header = ezjww.read_header(str(jww_path))
    layer_scales: dict[str, float] = {}
    group_layer_names: dict[tuple[int, int], str] = {}
    for group_index, group in enumerate(header.get("layer_groups", [])):
        scale = float(group.get("scale") or 1.0)
        for layer_index, layer in enumerate(group.get("layers", [])):
            layer_name = layer.get("name") or f"{group_index:X}-{layer_index:X}"
            group_layer_names[(group_index, layer_index)] = layer_name
            if layer_name in layer_scales and abs(layer_scales[layer_name] - scale) > 1e-9:
                # Ambiguous duplicate layer name in different groups; leave it unscaled.
                layer_scales[layer_name] = 1.0
            else:
                layer_scales[layer_name] = scale
    return layer_scales, group_layer_names


def _arc_match_key(layer_name: str, center_x: float, center_y: float,
                   radius: float, start_angle: float, end_angle: float) -> tuple:
    return (
        layer_name,
        round(center_x, 6),
        round(center_y, 6),
        round(radius, 6),
        round(start_angle % 360, 6),
        round(end_angle % 360, 6),
    )


def _fix_tilted_arcs(doc, jww_path: Path, group_layer_names: dict[tuple[int, int], str]) -> None:
    """Apply JWW ARC tilt angles that ezjww currently leaves out of DXF ARC angles."""
    try:
        jww_doc = ezjww.read_document(str(jww_path))
    except Exception:
        return

    tilted_arcs: dict[tuple, deque[float]] = defaultdict(deque)
    for entity in jww_doc.get("entities", []):
        if entity.get("type") != "ARC":
            continue
        tilt = float(entity.get("tilt_angle") or 0.0)
        flatness = float(entity.get("flatness") or 1.0)
        if abs(tilt) < 1e-9 or abs(flatness - 1.0) > 1e-9:
            continue
        base = entity.get("base", {})
        layer_name = group_layer_names.get(
            (int(base.get("layer_group", -1)), int(base.get("layer", -1)))
        )
        if not layer_name:
            continue
        start = float(entity.get("start_angle") or 0.0)
        arc = float(entity.get("arc_angle") or 0.0)
        key = _arc_match_key(
            layer_name,
            float(entity.get("center_x") or 0.0),
            float(entity.get("center_y") or 0.0),
            float(entity.get("radius") or 0.0),
            start * 180.0 / pi,
            (start + arc) * 180.0 / pi,
        )
        tilted_arcs[key].append(tilt * 180.0 / pi)

    if not tilted_arcs:
        return

    for arc_entity in doc.modelspace().query("ARC"):
        key = _arc_match_key(
            arc_entity.dxf.layer,
            arc_entity.dxf.center.x,
            arc_entity.dxf.center.y,
            arc_entity.dxf.radius,
            arc_entity.dxf.start_angle,
            arc_entity.dxf.end_angle,
        )
        if not tilted_arcs[key]:
            continue
        tilt_degrees = tilted_arcs[key].popleft()
        arc_entity.dxf.start_angle = (arc_entity.dxf.start_angle + tilt_degrees) % 360
        arc_entity.dxf.end_angle = (arc_entity.dxf.end_angle + tilt_degrees) % 360


def _apply_layer_group_scaling(doc, layer_scales: dict[str, float]) -> None:
    """Convert JWW paper-scaled layer groups back to real model millimeters."""
    try:
        from ezdxf.math import Matrix44
    except Exception:
        Matrix44 = None

    doc.header["$INSUNITS"] = 4  # millimeters
    doc.header["$MEASUREMENT"] = 1

    continuous = {"continuous", "bylayer", "byblock"}
    for entity in doc.modelspace():
        scale = layer_scales.get(entity.dxf.layer, 1.0)
        if abs(scale - 1.0) < 1e-9:
            continue
        if entity.dxf.linetype.lower() not in continuous:
            try:
                entity.dxf.ltscale = float(getattr(entity.dxf, "ltscale", 1.0) or 1.0) * scale
            except Exception:
                pass
        if Matrix44 is None:
            continue
        try:
            entity.transform(Matrix44.scale(scale, scale, 1.0))
        except Exception:
            pass


def convert_jww_to_dwg(jww_path: str, output_dir: str, dwg_version: str,
                        oda_path: str, keep_dxf: bool = False,
                        explode_inserts: bool = False, target_font: str = "msgothic.ttc") -> tuple[bool, str]:
    """
    Converts a single JWW file to DWG.
    
    Pipeline:
    1. ezjww parses JWW → writes DXF without flattening INSERTs/ARCs.
    2. ezdxf applies text style metadata and optional block explosion.
    3. ODA File Converter converts DXF → DWG.
    """
    jww_path_obj = Path(jww_path)
    output_dir_obj = Path(output_dir)
    
    if not jww_path_obj.exists():
        return False, f"File JWW không tồn tại / JWWファイルが存在しません: {jww_path}"
        
    if not output_dir_obj.exists():
        try:
            output_dir_obj.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            return False, f"Không thể tạo thư mục đầu ra / 出力フォルダを作成できません: {e}"
            
    base_name = jww_path_obj.stem
    
    # --- Step 1: Validate JWW ---
    try:
        if not ezjww.is_jww_file(str(jww_path_obj)):
            return False, "Không phải định dạng JWW hợp lệ / 有効なJWWファイルではありません。"
    except Exception as e:
        return False, f"Lỗi kiểm tra định dạng / ファイル検証エラー: {e}"
        
    # --- Step 2: JWW → DXF via ezjww (pure, untouched) ---
    # Write DXF directly to output directory (ODA needs input & output folders)
    dxf_filename = f"{base_name}.dxf"
    dxf_path = output_dir_obj / dxf_filename
    
    try:
        # Keep ezjww's output as close to the source geometry as possible.
        # Its INSERT expansion can tessellate ARC entities into many tiny LINEs.
        ezjww.write_dxf(str(jww_path_obj), str(dxf_path), explode_inserts=False)
    except Exception as e:
        if dxf_path.exists():
            try: dxf_path.unlink()
            except: pass
        return False, f"Lỗi xuất DXF / DXFエクスポートエラー: {e}"
    
    if not dxf_path.exists():
        return False, "ezjww không tạo được file DXF / ezjwwがDXFファイルを生成できませんでした。"
        
    # --- Step 2.5: Sanitize DXF & Set Font Style via ezdxf ---
    try:
        import ezdxf
        doc = ezdxf.readfile(str(dxf_path))
        layer_scales, group_layer_names = _layer_group_metadata(jww_path_obj)
        
        # 1. Update text style font to user selected font (for Japanese/Vietnamese support)
        font_family = _extended_font_family(target_font)
        for style in doc.styles:
            style.dxf.font = target_font
            if font_family and hasattr(style, "set_extended_font_data"):
                style.set_extended_font_data(font_family)
            
        # 2. Forcefully explode remaining block references if requested
        if explode_inserts:
            inserts = list(doc.modelspace().query('INSERT'))
            while inserts:
                insert = inserts.pop()
                try:
                    new_entities = insert.explode()
                    inserts.extend([e for e in new_entities if e.dxftype() == 'INSERT'])
                except Exception:
                    pass

        _fix_tilted_arcs(doc, jww_path_obj, group_layer_names)
        _fix_fragmented_linetypes(doc)
        _apply_layer_group_scaling(doc, layer_scales)

        doc.saveas(str(dxf_path))
    except Exception as e:
        if dxf_path.exists() and not keep_dxf:
            try: dxf_path.unlink()
            except: pass
        return False, f"Lỗi tối ưu hóa DXF / DXF最適化エラー: {e}"
        
    # --- Step 3: DXF → DWG via ODA File Converter (direct CLI) ---
    if not oda_path or not os.path.exists(oda_path):
        # No ODA: keep DXF as final output
        return True, "Đã xuất sang DXF (Không có ODA Converter) / DXFに書き出しました（ODA Converterなし）"
    
    final_dwg_path = output_dir_obj / f"{base_name}.dwg"
    err_file_path = output_dir_obj / f"{base_name}.dwg.err"
    
    try:
        _run_oda_direct(
            oda_exe=oda_path,
            input_dir=str(output_dir_obj),
            output_dir=str(output_dir_obj),
            dwg_version=dwg_version,
            input_filename=dxf_filename
        )
        
        # Wait a bit and check for output
        import time
        dwg_success = False
        for _ in range(10):
            if final_dwg_path.exists() and final_dwg_path.stat().st_size > 0:
                dwg_success = True
                break
            time.sleep(0.5)
        
        if not dwg_success:
            # Check if there is an error file
            err_msg = ""
            if err_file_path.exists():
                try:
                    with open(err_file_path, "r", encoding="utf-8", errors="ignore") as f:
                        lines = f.readlines()
                        # Extract the last few lines of the error file
                        err_msg = " ".join([line.strip() for line in lines[-3:] if line.strip()])
                except:
                    pass
            
            # Clean up files if needed
            if final_dwg_path.exists():
                try: final_dwg_path.unlink()
                except: pass
            if not keep_dxf and dxf_path.exists():
                try: dxf_path.unlink()
                except: pass
                
            error_details = f": {err_msg}" if err_msg else ""
            return False, f"Lỗi ODA File Converter / ODA変換エラー{error_details}"
        
        # Clean up temporary files on success
        if err_file_path.exists():
            try: err_file_path.unlink()
            except: pass
            
        if not keep_dxf:
            if dxf_path.exists():
                try: dxf_path.unlink()
                except: pass
                
        return True, "Chuyển đổi thành công / 変換に成功しました"
        
    except Exception as e:
        return False, f"Lỗi chuyển đổi sang DWG / DWG変換エラー: {e}"
