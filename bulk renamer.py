import re
import subprocess
import sys
from pathlib import Path

try:
    import customtkinter as ctk
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "customtkinter"])
    import customtkinter as ctk

from tkinter import filedialog, messagebox


class BulkRenamer:
    def __init__(self):
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.root = ctk.CTk()
        self.root.title("Bulk File Renamer")
        self.root.geometry("1150x700")
        self.root.minsize(900, 580)

        self.folder = None
        self.files = []
        self.preview = []   # (Path, new_name, matched)
        self.undo_stack = []
        self.table_rows = []

        self._build_ui()

    def _build_ui(self):
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(1, weight=1)
        self._build_header()
        self._build_main_area()
        self._build_status_bar()

    def _build_header(self):
        bar = ctk.CTkFrame(self.root, height=52, corner_radius=0, fg_color="#1a1a2e")
        bar.grid(row=0, column=0, sticky="ew")
        bar.grid_propagate(False)

        ctk.CTkLabel(bar, text="Bulk File Renamer",
                     font=ctk.CTkFont(size=17, weight="bold"),
                     text_color="#c8d8ff").pack(side="left", padx=20, pady=14)

        ctk.CTkLabel(bar, text="regex batch rename",
                     font=ctk.CTkFont(size=11),
                     text_color="#555577").pack(side="left", pady=14)

    def _build_main_area(self):
        main = ctk.CTkFrame(self.root, corner_radius=0, fg_color="transparent")
        main.grid(row=1, column=0, sticky="nsew", padx=10, pady=(8, 4))
        main.grid_columnconfigure(1, weight=1)
        main.grid_rowconfigure(0, weight=1)
        self._build_left_panel(main)
        self._build_right_panel(main)

    def _build_left_panel(self, parent):
        left = ctk.CTkFrame(parent, width=310)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        left.grid_propagate(False)
        left.grid_rowconfigure(99, weight=1)

        row = 0
        row = self._section(left, "FOLDER", row)

        self.folder_display = ctk.CTkLabel(left, text="No folder selected",
                                           anchor="w", wraplength=260,
                                           font=ctk.CTkFont(size=11),
                                           text_color="#666688")
        self.folder_display.grid(row=row, column=0, sticky="ew", padx=16, pady=(0, 6))
        row += 1

        ctk.CTkButton(left, text="Browse Folder",
                      command=self._browse_folder, height=32).grid(
            row=row, column=0, sticky="ew", padx=16, pady=(0, 10))
        row += 1

        row = self._divider(left, row)
        row = self._section(left, "FIND PATTERN  (regex)", row)

        self.pattern_entry = ctk.CTkEntry(left, placeholder_text=r"e.g.  (\d+)_(.+)",
                                          font=ctk.CTkFont(family="Courier New", size=12),
                                          height=34)
        self.pattern_entry.grid(row=row, column=0, sticky="ew", padx=16, pady=(0, 10))
        self.pattern_entry.bind("<KeyRelease>", lambda _: self._update_preview())
        row += 1

        row = self._section(left, "REPLACE WITH", row)

        self.replace_entry = ctk.CTkEntry(left, placeholder_text=r"e.g.  \2_\1  or  prefix_\g<0>",
                                          font=ctk.CTkFont(family="Courier New", size=12),
                                          height=34)
        self.replace_entry.grid(row=row, column=0, sticky="ew", padx=16, pady=(0, 10))
        self.replace_entry.bind("<KeyRelease>", lambda _: self._update_preview())
        row += 1

        row = self._divider(left, row)
        row = self._section(left, "OPTIONS", row)

        self.case_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(left, text="Case sensitive",
                        variable=self.case_var,
                        command=self._update_preview).grid(
            row=row, column=0, padx=16, pady=(0, 6), sticky="w")
        row += 1

        self.match_ext_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(left, text="Match full filename (incl. ext)",
                        variable=self.match_ext_var,
                        command=self._update_preview).grid(
            row=row, column=0, padx=16, pady=(0, 10), sticky="w")
        row += 1

        row = self._section(left, "EXTENSION FILTER  (comma-separated)", row)

        self.ext_var = ctk.StringVar()
        ext_entry = ctk.CTkEntry(left, textvariable=self.ext_var,
                                 placeholder_text=".txt, .mp4 — blank = all", height=32)
        ext_entry.grid(row=row, column=0, sticky="ew", padx=16, pady=(0, 10))
        ext_entry.bind("<KeyRelease>", lambda _: self._update_preview())
        row += 1

        row = self._divider(left, row)

        ctk.CTkFrame(left, fg_color="transparent").grid(row=99, column=0, sticky="nsew")

        btn_frame = ctk.CTkFrame(left, fg_color="transparent")
        btn_frame.grid(row=100, column=0, sticky="ew", padx=16, pady=14)
        btn_frame.grid_columnconfigure((0, 1), weight=1)

        self.apply_btn = ctk.CTkButton(btn_frame, text="Apply Renames",
                                       command=self._apply_renames,
                                       fg_color="#1a6e42", hover_color="#145535", height=36)
        self.apply_btn.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 6))

        self.undo_btn = ctk.CTkButton(btn_frame, text="Undo Last",
                                      command=self._undo_renames,
                                      fg_color="#6e2a1a", hover_color="#552015",
                                      height=32, state="disabled")
        self.undo_btn.grid(row=1, column=0, sticky="ew", padx=(0, 4))

        ctk.CTkButton(btn_frame, text="Clear", command=self._clear_all,
                      fg_color="#333344", hover_color="#22223a", height=32).grid(
            row=1, column=1, sticky="ew", padx=(4, 0))

    def _build_right_panel(self, parent):
        right = ctk.CTkFrame(parent)
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_rowconfigure(1, weight=1)
        right.grid_columnconfigure(0, weight=1)

        hdr = ctk.CTkFrame(right, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 4))
        hdr.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(hdr, text="PREVIEW",
                     font=ctk.CTkFont(size=11, weight="bold")).grid(row=0, column=0, sticky="w")

        self.match_label = ctk.CTkLabel(hdr, text="0 matches",
                                        font=ctk.CTkFont(size=11), text_color="#556677")
        self.match_label.grid(row=0, column=1, sticky="e")

        self.table = ctk.CTkScrollableFrame(right)
        self.table.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 12))
        self.table.grid_columnconfigure(0, weight=1)
        self.table.grid_columnconfigure(1, weight=0)
        self.table.grid_columnconfigure(2, weight=1)

        for col, text in enumerate(["Original Name", "", "New Name"]):
            ctk.CTkLabel(self.table, text=text,
                         font=ctk.CTkFont(size=11, weight="bold"),
                         anchor="w" if col != 1 else "center").grid(
                row=0, column=col, sticky="ew", padx=(5, 8), pady=(0, 4))

        ctk.CTkFrame(self.table, height=1, fg_color="#333355").grid(
            row=1, column=0, columnspan=3, sticky="ew", pady=(0, 4))

    def _build_status_bar(self):
        bar = ctk.CTkFrame(self.root, height=28, corner_radius=0, fg_color="#111120")
        bar.grid(row=2, column=0, sticky="ew")
        bar.grid_propagate(False)

        self.status_var = ctk.StringVar(value="ready.")
        ctk.CTkLabel(bar, textvariable=self.status_var,
                     font=ctk.CTkFont(size=11), text_color="#445566",
                     anchor="w").pack(side="left", padx=14, fill="y")

        self.undo_info = ctk.CTkLabel(bar, text="",
                                      font=ctk.CTkFont(size=11),
                                      text_color="#335544", anchor="e")
        self.undo_info.pack(side="right", padx=14, fill="y")

    def _section(self, parent, text, row):
        ctk.CTkLabel(parent, text=text, font=ctk.CTkFont(size=10, weight="bold"),
                     text_color="#778899", anchor="w").grid(
            row=row, column=0, sticky="w", padx=16, pady=(10, 3))
        return row + 1

    def _divider(self, parent, row):
        ctk.CTkFrame(parent, height=1, fg_color="#2a2a3a").grid(
            row=row, column=0, sticky="ew", padx=16, pady=4)
        return row + 1

    def _clear_table(self):
        for widgets in self.table_rows:
            for w in widgets:
                w.destroy()
        self.table_rows.clear()

    def _browse_folder(self):
        folder = filedialog.askdirectory(title="Select folder")
        if not folder:
            return
        self.folder = Path(folder)
        display = str(self.folder)
        if len(display) > 40:
            display = "..." + display[-38:]
        self.folder_display.configure(text=display, text_color="#aabbcc")
        self._load_files()
        self._update_preview()

    def _load_files(self):
        if not self.folder:
            return
        try:
            self.files = sorted(
                [f for f in self.folder.iterdir() if f.is_file()],
                key=lambda x: x.name.lower()
            )
            self.status_var.set(f"{len(self.files)} files in {self.folder.name}/")
        except PermissionError:
            self.status_var.set("Permission denied.")
            self.files = []
        except Exception as e:
            self.status_var.set(str(e))
            self.files = []

    def _filtered_files(self):
        raw = self.ext_var.get().strip()
        if not raw:
            return self.files
        exts = set()
        for e in raw.split(","):
            e = e.strip().lower()
            if e:
                exts.add(e if e.startswith(".") else f".{e}")
        return [f for f in self.files if f.suffix.lower() in exts]

    def _compile_pattern(self):
        pattern = self.pattern_entry.get()
        if not pattern:
            return None
        flags = 0 if self.case_var.get() else re.IGNORECASE
        try:
            return re.compile(pattern, flags)
        except re.error as e:
            self.status_var.set(f"Regex error: {e}")
            self.match_label.configure(text="bad pattern")
            return None

    def _do_sub(self, rx, repl, name):
        if self.match_ext_var.get():
            return rx.sub(repl, name)
        p = Path(name)
        return rx.sub(repl, p.stem) + p.suffix

    def _update_preview(self):
        self._clear_table()
        self.preview.clear()

        files = self._filtered_files()
        rx = self._compile_pattern()
        repl = self.replace_entry.get()

        if not self.folder or rx is None:
            self.match_label.configure(text="—")
            return

        hits = 0
        trow = 2

        for f in files:
            try:
                new_name = self._do_sub(rx, repl, f.name)
                matched = new_name != f.name
            except re.error:
                new_name = f.name
                matched = False

            self.preview.append((f, new_name, matched))
            if matched:
                hits += 1

            if trow - 2 < 300:
                oc = "#ddeeff" if matched else "#445566"
                nc = "#4fd494" if matched else "#445566"
                ac = "#2a8a5a" if matched else "#334455"

                w1 = ctk.CTkLabel(self.table, text=f.name, anchor="w",
                                   font=ctk.CTkFont(family="Courier New", size=11),
                                   text_color=oc)
                w1.grid(row=trow, column=0, sticky="ew", padx=(5, 4), pady=1)

                w2 = ctk.CTkLabel(self.table, text="->",
                                   font=ctk.CTkFont(size=12), text_color=ac)
                w2.grid(row=trow, column=1, padx=6)

                w3 = ctk.CTkLabel(self.table, text=new_name, anchor="w",
                                   font=ctk.CTkFont(family="Courier New", size=11),
                                   text_color=nc)
                w3.grid(row=trow, column=2, sticky="ew", padx=(4, 5), pady=1)

                self.table_rows.append([w1, w2, w3])
                trow += 1

        self.match_label.configure(text=f"{hits} matches")
        extra = "  (capped at 300)" if len(files) > 300 else ""
        self.status_var.set(f"{hits} of {len(files)} files will be renamed.{extra}")

    def _apply_renames(self):
        to_rename = [(f, n) for f, n, m in self.preview if m]

        if not to_rename:
            self.status_var.set("No matches.")
            return

        new_names = [n for _, n in to_rename]
        if len(new_names) != len(set(new_names)):
            messagebox.showerror("Conflict",
                                 "Pattern produces duplicate filenames. Aborting.")
            return

        if len(to_rename) > 50:
            if not messagebox.askyesno("Confirm", f"Rename {len(to_rename)} files?"):
                return

        done = []
        errors = []

        for f, new_name in to_rename:
            dest = f.parent / new_name
            if dest.exists() and dest.resolve() != f.resolve():
                errors.append(f"{f.name} -> target exists")
                continue
            try:
                f.rename(dest)
                done.append((dest, f))
            except Exception as e:
                errors.append(f"{f.name}: {e}")

        if done:
            self.undo_stack.append(done)
            self.undo_btn.configure(state="normal")

        self._sync_undo_label()
        self._load_files()
        self._update_preview()

        msg = f"Renamed {len(done)} files."
        if errors:
            msg += f" {len(errors)} failed."
        self.status_var.set(msg)

        if errors:
            messagebox.showwarning("Errors", "\n".join(errors[:10]))

    def _undo_renames(self):
        if not self.undo_stack:
            return

        batch = self.undo_stack.pop()
        errors = []
        count = 0

        for cur, orig in reversed(batch):
            try:
                cur.rename(orig)
                count += 1
            except Exception as e:
                errors.append(str(e))

        self.undo_btn.configure(state="normal" if self.undo_stack else "disabled")
        self._sync_undo_label()
        self._load_files()
        self._update_preview()

        msg = f"Reverted {count} files."
        if errors:
            msg += f" {len(errors)} failed."
        self.status_var.set(msg)

    def _clear_all(self):
        self.folder = None
        self.files.clear()
        self.preview.clear()
        self.table_rows.clear()
        self._clear_table()
        self.pattern_entry.delete(0, "end")
        self.replace_entry.delete(0, "end")
        self.ext_var.set("")
        self.folder_display.configure(text="No folder selected", text_color="#666688")
        self.match_label.configure(text="—")
        self.status_var.set("Cleared.")

    def _sync_undo_label(self):
        n = len(self.undo_stack)
        self.undo_info.configure(text=f"{n} undo batches" if n else "")

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = BulkRenamer()
    app.run()
