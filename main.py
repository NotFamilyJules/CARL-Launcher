import json
import os
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tempfile import TemporaryDirectory
from tkinter import filedialog, ttk
from urllib.parse import urlsplit
from urllib.request import urlopen
from zipfile import ZipFile

from CELESTE import celeste
from DK64 import dk64
from EMERALD import emerald
from FACTORIO import factorio
from HADES import hades
from HOLLOW_KNIGHT import hollow_knight
from PAPER_MARIO import paper_mario
from SM64 import sm64
from SOH import soh

ARCHIPELAGO = Path(os.environ["ProgramData"]) / "Archipelago"

root = tk.Tk()
root.title("CARL Launcher")
server_bar = ttk.Frame(root)
server_bar.pack(fill="x", padx=10, pady=(10, 0))
ttk.Label(server_bar, text="Server IP:port").pack(side="left")
server = ttk.Entry(server_bar, width=30)
server.pack(side="left", fill="x", expand=True, padx=(6, 0))
server.focus_set()

status = tk.Label(root, text="CARL is ready")
status.pack(pady=5)


def slot_name(game):
    try:
        import yaml
    except ModuleNotFoundError as error:
        if error.name != "yaml":
            raise
        subprocess.run([sys.executable, "-m", "pip", "install", "PyYAML>=6.0.3,<7"], check=True)
        import yaml

    path = Path(__file__).parent / "yamls" / f"{game}.yaml"
    with path.open(encoding="utf-8-sig") as file:
        return yaml.safe_load(file)["name"]


def server_address(address):
    room_url = "https://archipelago.gg/room/"
    if not address.startswith(room_url):
        return address

    room = urlsplit(address).path.removeprefix("/room/").rstrip("/")
    with urlopen(f"https://archipelago.gg/api/room_status/{room}", timeout=10) as response:
        port = json.load(response)["last_port"]
    if not port:
        raise ValueError("Open the Archipelago room page to start the server.")
    return f"archipelago.gg:{port}"


def prepare_patch(patch, address, name, game):
    with ZipFile(patch) as source:
        manifest = json.loads(source.read("archipelago.json"))
        if manifest["player_name"] != name:
            raise ValueError(f"This patch is for {manifest['player_name']}. Choose the patch for {name}.")
        if not manifest["server"] or manifest["server"] == address:
            return patch

    folder = Path(__file__).resolve().parent / "data" / game
    folder.mkdir(parents=True, exist_ok=True)
    manifest["server"] = address
    with TemporaryDirectory(dir=folder) as temp:
        updated = Path(temp) / patch.name
        with ZipFile(patch) as source, ZipFile(updated, "w") as output:
            for entry in source.infolist():
                if entry.filename == "archipelago.json":
                    output.writestr(entry, json.dumps(manifest))
                else:
                    output.writestr(entry, source.read(entry))
        return updated.replace(folder / patch.name)


def play_patch(address, name, game, extension, install=None):
    picked = filedialog.askopenfilename(title=f"Choose the patch for {name}",
                                        filetypes=[(f"{game} patch", f"*{extension}")])
    if not picked:
        return "CARL is ready"

    patch = prepare_patch(Path(picked), address, name, game)
    if install:
        install(ARCHIPELAGO)
    subprocess.Popen([ARCHIPELAGO / "ArchipelagoBizHawkClient.exe", "--connect", address, patch], cwd=ARCHIPELAGO)
    return f"CARL is opening {game}."


def launch(name, play, *args):
    address = server.get().strip()
    if not address:
        status.config(text="Enter the Archipelago server address.")
        server.focus_set()
        return
    status.config(text=f"CARL is checking out {name}...")
    root.update_idletasks()

    try:
        address = server_address(address)
        slot = slot_name(name)
        message = play(address, slot, *args)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        message = str(error)
    status.config(text=message)


def add_game(name, play, *args):
    button = tk.Button(root, text=name, command=lambda: launch(name, play, *args))
    button.pack(padx=10, pady=2, fill="x", expand=True)


add_game("Hades", hades.play, ARCHIPELAGO)
add_game("Super Mario 64", sm64.play)
add_game("Ship of Harkinian", soh.play)
add_game("Pokemon Emerald", emerald.play, play_patch)
add_game("Paper Mario", paper_mario.play, play_patch)
add_game("Hollow Knight", hollow_knight.play)
add_game("Factorio", factorio.play, ARCHIPELAGO, status)
add_game("Donkey Kong 64", dk64.play, ARCHIPELAGO)
add_game("Celeste (Open World)", celeste.play)

root.mainloop()
