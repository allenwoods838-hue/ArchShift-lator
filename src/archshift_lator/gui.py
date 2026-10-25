"""Minimal standard-library desktop interface."""
from __future__ import annotations
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .fallback import inspect_target, run_with_fallback


def launch() -> None:
    root = tk.Tk()
    root.title("ArchShift-lator")
    root.geometry("900x620")
    root.minsize(700, 460)

    chosen = tk.StringVar()
    ttk.Label(root, text="ArchShift-lator", font=("TkDefaultFont", 18, "bold")).pack(anchor="w", padx=16, pady=(16, 2))
    ttk.Label(root, text="Maclator-first routing with an experimental Python fallback").pack(anchor="w", padx=16, pady=(0, 12))
    row = ttk.Frame(root)
    row.pack(fill="x", padx=16)
    ttk.Entry(row, textvariable=chosen).pack(side="left", fill="x", expand=True)
    def choose() -> None:
        path = filedialog.askopenfilename(title="Choose a Mach-O file")
        if not path:
            path = filedialog.askdirectory(title="Choose an app bundle or folder")
        if path:
            chosen.set(path)
    ttk.Button(row, text="Choose…", command=choose).pack(side="left", padx=(8, 0))

    output = tk.Text(root, wrap="word", height=24)
    output.pack(fill="both", expand=True, padx=16, pady=12)
    output.insert("end", "Select a Mach-O executable or .app bundle, then inspect it or try the configured Maclator command.\n\n")
    output.configure(state="disabled")

    def show(text: str) -> None:
        output.configure(state="normal")
        output.delete("1.0", "end")
        output.insert("end", text)
        output.configure(state="disabled")

    def inspect_action() -> None:
        if not chosen.get():
            messagebox.showinfo("Choose a target", "Choose a file, .app bundle, or folder first.")
            return
        try:
            report = inspect_target(chosen.get())
            lines = [f"Target: {report.target}", f"Files checked: {report.files_checked}", ""]
            for item in report.binaries:
                lines.extend([item.path, "  Architectures: " + ", ".join(item.architectures), "  Type: " + item.file_type_name])
            lines.extend(report.errors)
            show("\n".join(lines))
        except Exception as exc:
            messagebox.showerror("Inspection failed", str(exc))

    def route_action() -> None:
        if not chosen.get():
            messagebox.showinfo("Choose a target", "Choose a file, .app bundle, or folder first.")
            return
        try:
            report = run_with_fallback(chosen.get())
            lines = [report.message, "", "External engine: " + report.engine.message]
            if report.engine.stdout:
                lines.extend(["", "Engine output:", report.engine.stdout])
            if report.engine.stderr:
                lines.extend(["", "Engine errors:", report.engine.stderr])
            if report.inspection:
                lines.extend(["", f"Fallback inspected {len(report.inspection.binaries)} Mach-O binary/binaries."])
                for item in report.inspection.binaries:
                    lines.append(f"{item.path}: {', '.join(item.architectures)}")
            show("\n".join(lines))
        except Exception as exc:
            messagebox.showerror("Routing failed", str(exc))

    buttons = ttk.Frame(root)
    buttons.pack(fill="x", padx=16, pady=(0, 16))
    ttk.Button(buttons, text="Inspect", command=inspect_action).pack(side="left")
    ttk.Button(buttons, text="Try Maclator → fallback", command=route_action).pack(side="left", padx=8)
    ttk.Label(buttons, text="Fallback does not yet convert arbitrary ARM64 apps.", foreground="#805000").pack(side="right")
    root.mainloop()
