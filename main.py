import os
import subprocess
import tkinter as tk
from tkinter import ttk
from tkinter import filedialog
from pathlib import Path

from HADES.hades import find_hades, install

root = tk.Tk()
root.title("CARL Launcher")
server_bar = ttk.Frame(root)
server_bar.pack(fill="x", padx=10, pady=(10, 0))
ttk.Label(server_bar, text="Server IP:port").pack(side="left")
server = ttk.Entry(server_bar, width=30)
server.pack(side="left", fill="x", expand=True, padx=(6, 0))
server.focus_set()
progress = ttk.Progressbar(root, length=250, mode="determinate")
progress.pack(padx=10, pady=10)

status = tk.Label(root, text="CARL is ready")
status.pack(pady=5)


def launch_hades():
    address = server.get().strip()
    if not address:
        status.config(text="Enter the Archipelago server address.")
        server.focus_set()
        return
    status.config(text="CARL is checking out Hades...")
    root.update_idletasks()

    hades_path = find_hades()

    if hades_path:
        print("CARL found Hades at:", hades_path)
        status.config(text="CARL found Hades!")
    else:
        status.config(text="CARL couldn't find Hades...")
        hades_path = filedialog.askdirectory(title="Where is Hades?")

        if hades_path and (Path(hades_path) / "Content").is_dir():
            status.config(text="CARL found Hades.")
        else:
            status.config(text="CARL couldn't verify Hades.")
            return

    launcher = Path(os.environ["ProgramData"]) / "Archipelago" / "ArchipelagoLauncher.exe"
    try:
        install(Path(hades_path), launcher.parent)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        status.config(text=str(error))
        return
    env = os.environ.copy()
    env["CARL_SERVER"] = address
    env["CARL_PLAYER_YAML"] = str(Path(__file__).resolve().parent / "yamls" / "Hades.yaml")
    env["CARL_STYX_SCRIBE"] = (Path(hades_path) / "StyxScribe.py").as_posix()
    subprocess.Popen([launcher, "Hades Client"], cwd=launcher.parent, env=env)
    status.config(text="CARL is connecting to Hades...")

hades_button = tk.Button(root, text="Hades", command=launch_hades)
hades_button.pack(padx=10, pady=10)

root.mainloop()
