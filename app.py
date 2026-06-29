import os
import sys
import json
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from datetime import datetime

import sv_ttk
import converter

CONFIG_FILE = Path(os.path.expanduser("~")) / ".jww2dwg_config.json"
CONFIG_VERSION = 2
DEFAULT_EXPLODE_INSERTS = False

TRANSLATIONS = {
    "vi": {
        "title": "JWW → DWG Converter",
        "input_dir": "Nguồn JWW:",
        "output_dir": "Đích DWG:",
        "browse": "...",
        "settings": "Cài đặt",
        "dwg_version": "Phiên bản:",
        "font_label": "Font xuất:",
        "oda_path": "ODA path:",
        "oda_detected": "✓ OK",
        "oda_missing": "⚠ Thiếu ODA (chỉ xuất DXF)",
        "keep_dxf": "Giữ DXF",
        "explode_blocks": "Phân rã Block",
        "files_list": "Danh sách file",
        "col_name": "Tên File",
        "col_size": "Kích thước",
        "col_status": "Trạng thái",
        "status_ready": "Chờ",
        "status_converting": "Đang chuyển...",
        "status_success": "✓ OK",
        "status_failed": "✗ Lỗi",
        "convert_btn": "▶  BẮT ĐẦU CHUYỂN ĐỔI",
        "open_output": "Mở folder kết quả",
        "console_log": "Log",
        "clear_log": "Xóa",
        "success_msg": "Hoàn tất!\nThành công: {}\nThất bại: {}",
        "select_input_err": "Chọn thư mục chứa file JWW.",
        "select_output_err": "Chọn thư mục lưu file DWG.",
        "open_output_err": "Thư mục kết quả chưa tồn tại.",
        "no_files_found": "Không tìm thấy file .jww.",
        "stop_btn": "⏹  DỪNG",
        "stopped_msg": "Đã dừng.",
    },
    "ja": {
        "title": "JWW → DWG 変換",
        "input_dir": "変換元:",
        "output_dir": "出力先:",
        "browse": "...",
        "settings": "設定",
        "dwg_version": "バージョン:",
        "font_label": "フォント:",
        "oda_path": "ODAパス:",
        "oda_detected": "✓ OK",
        "oda_missing": "⚠ ODAなし (DXFのみ)",
        "keep_dxf": "DXF保持",
        "explode_blocks": "ブロック分解",
        "files_list": "ファイル一覧",
        "col_name": "ファイル名",
        "col_size": "サイズ",
        "col_status": "状態",
        "status_ready": "待機",
        "status_converting": "変換中...",
        "status_success": "✓ OK",
        "status_failed": "✗ 失敗",
        "convert_btn": "▶  変換スタート",
        "open_output": "出力フォルダを開く",
        "console_log": "ログ",
        "clear_log": "消去",
        "success_msg": "完了！\n成功: {}\n失敗: {}",
        "select_input_err": "JWWフォルダを選択",
        "select_output_err": "DWGフォルダを選択",
        "open_output_err": "出力フォルダが存在しません。",
        "no_files_found": "JWWファイルなし",
        "stop_btn": "⏹  中止",
        "stopped_msg": "中止しました。",
    },
    "en": {
        "title": "JWW → DWG Converter",
        "input_dir": "JWW Source:",
        "output_dir": "DWG Output:",
        "browse": "...",
        "settings": "Settings",
        "dwg_version": "Version:",
        "font_label": "Export Font:",
        "oda_path": "ODA path:",
        "oda_detected": "✓ OK",
        "oda_missing": "⚠ ODA missing (DXF only)",
        "keep_dxf": "Keep DXF",
        "explode_blocks": "Explode Blocks",
        "files_list": "File List",
        "col_name": "File Name",
        "col_size": "Size",
        "col_status": "Status",
        "status_ready": "Ready",
        "status_converting": "Converting...",
        "status_success": "✓ OK",
        "status_failed": "✗ Failed",
        "convert_btn": "▶  START CONVERSION",
        "open_output": "Open output folder",
        "console_log": "Log",
        "clear_log": "Clear",
        "success_msg": "Done!\nSuccess: {}\nFailed: {}",
        "select_input_err": "Please select JWW input folder.",
        "select_output_err": "Please select DWG output folder.",
        "open_output_err": "Output folder does not exist.",
        "no_files_found": "No .jww files found.",
        "stop_btn": "⏹  STOP",
        "stopped_msg": "Stopped.",
    }
}

class Jww2DwgApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.load_config()
        if getattr(self, "_config_needs_save", False):
            self.save_config()
        
        self.title(TRANSLATIONS[self.lang]["title"])
        self.geometry("680x560")
        self.minsize(580, 480)
        
        sv_ttk.set_theme("dark")
        self.style = ttk.Style(self)
        
        # Icon
        icon_path = Path(__file__).parent / "app_icon.ico"
        if icon_path.exists():
            try: self.iconbitmap(str(icon_path))
            except: pass
                
        self.files_to_convert = []
        self.stop_requested = False
        self.converting_thread = None
        
        self.create_widgets()
        self.scan_source_folder()
        self.check_oda_status()
        
    def load_config(self):
        self.lang = "vi"
        self.input_dir = ""
        self.output_dir = ""
        self.dwg_version = "R2018"
        self.font_name = "yumindb.ttf"
        self.oda_path = converter.find_oda_converter()
        self.keep_dxf = False
        self.explode_inserts = DEFAULT_EXPLODE_INSERTS
        self._config_needs_save = False
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    d = json.load(f)
                    config_version = int(d.get("config_version", 0) or 0)
                    self.lang = d.get("lang", "vi")
                    self.input_dir = d.get("input_dir", "")
                    self.output_dir = d.get("output_dir", "")
                    self.dwg_version = d.get("dwg_version", "R2018")
                    self.font_name = d.get("font_name", "msgothic.ttc")
                    self.oda_path = d.get("oda_path", self.oda_path)
                    self.keep_dxf = d.get("keep_dxf", False)
                    self.explode_inserts = (
                        d.get("explode_inserts", DEFAULT_EXPLODE_INSERTS)
                        if config_version >= CONFIG_VERSION
                        else DEFAULT_EXPLODE_INSERTS
                    )
                    self._config_needs_save = config_version < CONFIG_VERSION
            except: pass
                
    def save_config(self):
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump({
                    "config_version": CONFIG_VERSION,
                    "lang": self.lang, "input_dir": self.input_dir,
                    "output_dir": self.output_dir, "dwg_version": self.dwg_version,
                    "font_name": self.font_name,
                    "oda_path": self.oda_path, "keep_dxf": self.keep_dxf,
                    "explode_inserts": self.explode_inserts
                }, f, ensure_ascii=False, indent=2)
        except: pass

    def switch_language(self, lang):
        self.lang = lang
        self.save_config()
        t = TRANSLATIONS[self.lang]
        self.title(t["title"])
        self.header_lbl.config(text=t["title"])
        self.input_lbl.config(text=t["input_dir"])
        self.output_lbl.config(text=t["output_dir"])
        self.input_btn.config(text=t["browse"])
        self.output_btn.config(text=t["browse"])
        self.open_output_btn.config(text=t["open_output"])
        self.settings_lf.config(text=t["settings"])
        self.version_lbl.config(text=t["dwg_version"])
        self.font_lbl.config(text=t["font_label"])
        self.oda_lbl.config(text=t["oda_path"])
        self.oda_btn.config(text=t["browse"])
        self.dxf_chk.config(text=t["keep_dxf"])
        self.explode_chk.config(text=t["explode_blocks"])
        self.files_lf.config(text=t["files_list"])
        self.log_lf.config(text=t["console_log"])
        self.clear_btn.config(text=t["clear_log"])
        self.tree.heading("name", text=t["col_name"])
        self.tree.heading("size", text=t["col_size"])
        self.tree.heading("status", text=t["col_status"])
        self.scan_source_folder()
        self.check_oda_status()
        if not self.converting_thread or not self.converting_thread.is_alive():
            self.action_btn.config(text=t["convert_btn"])
        else:
            self.action_btn.config(text=t["stop_btn"])

    def create_widgets(self):
        t = TRANSLATIONS[self.lang]
        PAD = 8
        
        # ── Bottom: Action bar (packed first = always visible) ──
        bot = ttk.Frame(self)
        bot.pack(side="bottom", fill="x", padx=PAD, pady=(4, PAD))
        
        self.progress_var = tk.DoubleVar(value=0)
        ttk.Progressbar(bot, variable=self.progress_var, mode="determinate").pack(fill="x", pady=(0, 6))
        action_row = ttk.Frame(bot)
        action_row.pack(fill="x")
        self.action_btn = ttk.Button(action_row, text=t["convert_btn"], style="Accent.TButton", command=self.toggle_conversion)
        self.action_btn.pack(side="left", fill="x", expand=True, ipady=6)
        self.open_output_btn = ttk.Button(action_row, text=t["open_output"], command=self.open_output_folder)
        self.open_output_btn.pack(side="left", padx=(6, 0), ipady=6)

        # ── Top container ──
        top = ttk.Frame(self)
        top.pack(side="top", fill="both", expand=True, padx=PAD, pady=(PAD, 0))

        # Header row
        hdr = ttk.Frame(top)
        hdr.pack(fill="x", pady=(0, 6))
        self.header_lbl = ttk.Label(hdr, text=t["title"], font=("Segoe UI", 14, "bold"))
        self.header_lbl.pack(side="left")
        lang_f = ttk.Frame(hdr)
        lang_f.pack(side="right")
        ttk.Button(lang_f, text="VN", width=4, command=lambda: self.switch_language("vi")).pack(side="left", padx=1)
        ttk.Button(lang_f, text="JP", width=4, command=lambda: self.switch_language("ja")).pack(side="left", padx=1)
        ttk.Button(lang_f, text="EN", width=4, command=lambda: self.switch_language("en")).pack(side="left", padx=1)

        # Folders row (compact grid)
        folders = ttk.Frame(top)
        folders.pack(fill="x", pady=(0, 6))
        folders.columnconfigure(1, weight=1)
        folders.columnconfigure(4, weight=1)
        
        self.input_lbl = ttk.Label(folders, text=t["input_dir"])
        self.input_lbl.grid(row=0, column=0, sticky="w", padx=(0, 4))
        self.input_var = tk.StringVar(value=self.input_dir)
        self.input_entry = ttk.Entry(folders, textvariable=self.input_var)
        self.input_entry.grid(row=0, column=1, sticky="ew", padx=(0, 2))
        self.input_entry.bind("<KeyRelease>", lambda e: self.on_input_dir_change())
        self.input_btn = ttk.Button(folders, text=t["browse"], width=3, command=self.browse_input_dir)
        self.input_btn.grid(row=0, column=2, padx=(0, 12))
        
        self.output_lbl = ttk.Label(folders, text=t["output_dir"])
        self.output_lbl.grid(row=0, column=3, sticky="w", padx=(0, 4))
        self.output_var = tk.StringVar(value=self.output_dir)
        self.output_entry = ttk.Entry(folders, textvariable=self.output_var)
        self.output_entry.grid(row=0, column=4, sticky="ew", padx=(0, 2))
        self.output_entry.bind("<KeyRelease>", lambda e: self.on_output_dir_change())
        self.output_btn = ttk.Button(folders, text=t["browse"], width=3, command=self.browse_output_dir)
        self.output_btn.grid(row=0, column=5)

        # Settings (compact 3-row grid inside a thin LabelFrame)
        self.settings_lf = ttk.LabelFrame(top, text=t["settings"])
        self.settings_lf.pack(fill="x", pady=(0, 6))
        sf = ttk.Frame(self.settings_lf)
        sf.pack(fill="x", padx=6, pady=4)
        sf.columnconfigure(5, weight=1)

        # Row 0
        self.version_lbl = ttk.Label(sf, text=t["dwg_version"])
        self.version_lbl.grid(row=0, column=0, sticky="w", padx=(0, 4))
        self.version_var = tk.StringVar(value=self.dwg_version)
        self.version_cb = ttk.Combobox(sf, textvariable=self.version_var, values=["R2018","R2013","R2010","R2007","R2004","R2000"], state="readonly", width=8)
        self.version_cb.grid(row=0, column=1, sticky="w", padx=(0, 12))
        self.version_cb.bind("<<ComboboxSelected>>", lambda e: self.on_settings_change())
        
        self.dxf_var = tk.BooleanVar(value=self.keep_dxf)
        self.dxf_chk = ttk.Checkbutton(sf, text=t["keep_dxf"], variable=self.dxf_var, command=self.on_settings_change)
        self.dxf_chk.grid(row=0, column=2, sticky="w", padx=(0, 12))
        
        self.explode_var = tk.BooleanVar(value=self.explode_inserts)
        self.explode_chk = ttk.Checkbutton(sf, text=t["explode_blocks"], variable=self.explode_var, command=self.on_settings_change)
        self.explode_chk.grid(row=0, column=3, sticky="w")
        
        # Row 1
        self.oda_lbl = ttk.Label(sf, text=t["oda_path"])
        self.oda_lbl.grid(row=1, column=0, sticky="w", pady=(4, 0), padx=(0, 4))
        self.oda_var = tk.StringVar(value=self.oda_path)
        self.oda_entry = ttk.Entry(sf, textvariable=self.oda_var)
        self.oda_entry.grid(row=1, column=1, columnspan=3, sticky="ew", pady=(4, 0), padx=(0, 4))
        self.oda_entry.bind("<KeyRelease>", lambda e: self.on_oda_path_change())
        self.oda_btn = ttk.Button(sf, text=t["browse"], width=3, command=self.browse_oda_path)
        self.oda_btn.grid(row=1, column=4, sticky="w", pady=(4, 0))
        self.oda_status_lbl = ttk.Label(sf, text="", font=("Segoe UI", 8, "bold"))
        self.oda_status_lbl.grid(row=1, column=5, sticky="w", pady=(4, 0), padx=(6, 0))
        
        # Row 2 (Font settings)
        self.font_lbl = ttk.Label(sf, text=t["font_label"])
        self.font_lbl.grid(row=2, column=0, sticky="w", pady=(4, 0), padx=(0, 4))
        self.font_var = tk.StringVar(value=self.font_name)
        self.font_cb = ttk.Combobox(sf, textvariable=self.font_var, values=["yumindb.ttf", "msgothic.ttc", "arial.ttf", "romans.shx", "VNI-Times.ttf", "Times New Roman"], width=15)
        self.font_cb.grid(row=2, column=1, columnspan=2, sticky="w", pady=(4, 0), padx=(0, 12))
        self.font_cb.bind("<<ComboboxSelected>>", lambda e: self.on_settings_change())
        self.font_cb.bind("<KeyRelease>", lambda e: self.on_settings_change())

        # File list + Log (PanedWindow, resizable)
        pw = ttk.PanedWindow(top, orient="vertical")
        pw.pack(fill="both", expand=True)

        self.files_lf = ttk.LabelFrame(pw, text=t["files_list"])
        pw.add(self.files_lf, weight=3)
        self.tree = ttk.Treeview(self.files_lf, columns=("name","size","status"), show="headings", selectmode="none", height=6)
        self.tree.heading("name", text=t["col_name"])
        self.tree.heading("size", text=t["col_size"])
        self.tree.heading("status", text=t["col_status"])
        self.tree.column("name", width=300)
        self.tree.column("size", width=80, anchor="center")
        self.tree.column("status", width=80, anchor="center")
        ts = ttk.Scrollbar(self.files_lf, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=ts.set)
        self.tree.pack(side="left", fill="both", expand=True, padx=1, pady=1)
        ts.pack(side="right", fill="y", padx=(0,1), pady=1)

        self.log_lf = ttk.LabelFrame(pw, text=t["console_log"])
        pw.add(self.log_lf, weight=1)
        log_top = ttk.Frame(self.log_lf)
        log_top.pack(fill="both", expand=True)
        self.log_text = tk.Text(log_top, height=3, font=("Consolas", 8), wrap="word")
        ls = ttk.Scrollbar(log_top, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=ls.set)
        self.log_text.pack(side="left", fill="both", expand=True, padx=1, pady=1)
        ls.pack(side="right", fill="y", padx=(0,1), pady=1)
        self.clear_btn = ttk.Button(self.log_lf, text=t["clear_log"], width=5, command=self.clear_log)
        self.clear_btn.pack(side="right", padx=4, pady=2)

    # ── Utility ──
    def write_log(self, msg):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{ts}] {msg}\n")
        self.log_text.see(tk.END)
    def clear_log(self):
        self.log_text.delete("1.0", tk.END)
    def open_output_folder(self):
        t = TRANSLATIONS[self.lang]
        folder = self.output_var.get().strip() if hasattr(self, "output_var") else self.output_dir
        if not folder or not os.path.isdir(folder):
            messagebox.showerror("Error", t["open_output_err"])
            return
        try:
            os.startfile(os.path.normpath(folder))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ── Browse ──
    def browse_input_dir(self):
        d = filedialog.askdirectory(initialdir=self.input_dir)
        if d: self.input_var.set(os.path.normpath(d)); self.on_input_dir_change()
    def browse_output_dir(self):
        d = filedialog.askdirectory(initialdir=self.output_dir)
        if d: self.output_var.set(os.path.normpath(d)); self.on_output_dir_change()
    def browse_oda_path(self):
        f = filedialog.askopenfilename(
            initialdir=os.path.dirname(self.oda_path) if self.oda_path else "C:\\",
            filetypes=[("Executables","*.exe"),("All","*.*")])
        if f: self.oda_var.set(os.path.normpath(f)); self.on_oda_path_change()

    # ── Events ──
    def on_input_dir_change(self):
        self.input_dir = self.input_var.get(); self.save_config(); self.scan_source_folder()
    def on_output_dir_change(self):
        self.output_dir = self.output_var.get(); self.save_config()
    def on_oda_path_change(self):
        self.oda_path = self.oda_var.get(); self.save_config(); self.check_oda_status()
    def on_settings_change(self):
        self.dwg_version = self.version_var.get()
        self.keep_dxf = self.dxf_var.get()
        self.explode_inserts = self.explode_var.get()
        self.font_name = self.font_var.get()
        self.save_config()

    def check_oda_status(self):
        t = TRANSLATIONS[self.lang]
        if self.oda_path and os.path.exists(self.oda_path):
            self.oda_status_lbl.config(text=t["oda_detected"], foreground="#00E676")
        else:
            self.oda_status_lbl.config(text=t["oda_missing"], foreground="#FF5252")

    def scan_source_folder(self):
        for i in self.tree.get_children(): self.tree.delete(i)
        self.files_to_convert = []
        p = self.input_var.get()
        if not p or not os.path.isdir(p): return
        try:
            for f in sorted(os.listdir(p)):
                if f.lower().endswith(".jww"):
                    fp = os.path.join(p, f)
                    sz = os.path.getsize(fp)
                    ss = f"{sz} B" if sz < 1024 else (f"{sz/1024:.1f} KB" if sz < 1048576 else f"{sz/1048576:.1f} MB")
                    iid = self.tree.insert("", tk.END, values=(f, ss, TRANSLATIONS[self.lang]["status_ready"]))
                    self.files_to_convert.append({"id": iid, "name": f, "path": fp})
        except Exception as e:
            self.write_log(f"Scan error: {e}")

    # ── Conversion ──
    def toggle_conversion(self):
        if self.converting_thread and self.converting_thread.is_alive():
            self.stop_requested = True
            self.action_btn.config(state="disabled")
            return
        t = TRANSLATIONS[self.lang]
        if not self.input_dir: messagebox.showerror("Error", t["select_input_err"]); return
        if not self.output_dir: messagebox.showerror("Error", t["select_output_err"]); return
        if not self.files_to_convert: messagebox.showinfo("Info", t["no_files_found"]); return
        
        self.stop_requested = False
        self.action_btn.config(text=t["stop_btn"])
        for w in [self.input_btn, self.output_btn, self.oda_btn]:
            w.config(state="disabled")
        self.version_cb.config(state="disabled")
        self.font_cb.config(state="disabled")
        for w in [self.dxf_chk, self.explode_chk, self.input_entry, self.output_entry, self.oda_entry]:
            w.config(state="disabled")
        self.converting_thread = threading.Thread(target=self._convert_loop, daemon=True)
        self.converting_thread.start()

    def _convert_loop(self):
        total = len(self.files_to_convert)
        ok = fail = 0
        self.progress_var.set(0)
        self.write_log("Starting batch conversion...")
        for i, fi in enumerate(self.files_to_convert):
            if self.stop_requested:
                self.write_log(TRANSLATIONS[self.lang]["stopped_msg"]); break
            self.tree.item(fi["id"], values=(fi["name"], self.tree.item(fi["id"],"values")[1], TRANSLATIONS[self.lang]["status_converting"]))
            self.tree.see(fi["id"])
            self.write_log(f"({i+1}/{total}): {fi['name']}")
            
            success, msg = converter.convert_jww_to_dwg(
                jww_path=fi["path"], output_dir=self.output_dir,
                dwg_version=self.dwg_version, oda_path=self.oda_path,
                keep_dxf=self.keep_dxf, explode_inserts=self.explode_inserts, target_font=self.font_name)
            
            if success:
                ok += 1; st = TRANSLATIONS[self.lang]["status_success"]
                self.write_log(f"✓ {fi['name']}")
            else:
                fail += 1; st = TRANSLATIONS[self.lang]["status_failed"]
                self.write_log(f"✗ {fi['name']}: {msg}")
            self.tree.item(fi["id"], values=(fi["name"], self.tree.item(fi["id"],"values")[1], st))
            self.after(0, lambda p=((i+1)/total)*100: self.progress_var.set(p))
        self.after(0, lambda: self._done(ok, fail))

    def _done(self, ok, fail):
        t = TRANSLATIONS[self.lang]
        self.action_btn.config(text=t["convert_btn"], state="normal")
        for w in [self.input_btn, self.output_btn, self.oda_btn]:
            w.config(state="normal")
        self.version_cb.config(state="readonly")
        self.font_cb.config(state="normal")
        for w in [self.dxf_chk, self.explode_chk, self.input_entry, self.output_entry, self.oda_entry]:
            w.config(state="normal")
        self.write_log(f"Done. OK: {ok}, Fail: {fail}")
        messagebox.showinfo("Done", t["success_msg"].format(ok, fail))

if __name__ == "__main__":
    app = Jww2DwgApp()
    app.mainloop()
