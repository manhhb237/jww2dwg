import os
import shutil
import subprocess
from pathlib import Path
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

def convert_jww_to_dwg(jww_path: str, output_dir: str, dwg_version: str, 
                        oda_path: str, keep_dxf: bool = False, 
                        explode_inserts: bool = True, target_font: str = "msgothic.ttc") -> tuple[bool, str]:
    """
    Converts a single JWW file to DWG.
    
    Pipeline:
    1. ezjww parses JWW → writes DXF (with proper Shift-JIS encoding & font mapping)
    2. ODA File Converter converts DXF → DWG (preserving all fonts/encoding faithfully)
    
    NO intermediate ezdxf processing — this preserves the original Japanese text,
    font styles, line types, and block structure exactly as ezjww intended.
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
        ezjww.write_dxf(str(jww_path_obj), str(dxf_path), explode_inserts=explode_inserts)
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
        
        # 1. Update text style font to user selected font (for Japanese/Vietnamese support)
        for style in doc.styles:
            style.dxf.font = target_font
            
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
