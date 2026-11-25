import hashlib
import json
import os
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from tempfile import TemporaryDirectory
from tkinter import filedialog
from urllib.parse import urlsplit
from urllib.request import urlopen, urlretrieve
from zipfile import ZipFile


GAME = Path("C:/Program Files (x86)/Steam/steamapps/common/Hollow Knight")
CATALOG = "https://raw.githubusercontent.com/hk-modding/modlinks/14f6a9eb71bf283e36fb89c28d60b36e30b1a746/"
MODS = ("ItemChanger", "MenuChanger", "Benchwarp", "Vasi", "QoL", "Archipelago")
SETTINGS = Path.home() / "AppData/LocalLow/Team Cherry/Hollow Knight/ArchipelagoMod.GlobalSettings.json"


def unpack(link, folder, main_dll, backups):
    folder.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=folder) as temp:
        archive = Path(temp) / "package.zip"
        urlretrieve(link.text.strip(), archive)
        if hashlib.sha256(archive.read_bytes()).hexdigest() != link.attrib["SHA256"].lower():
            raise ValueError("Hollow Knight mod download failed verification.")
        with ZipFile(archive) as package:
            package.extractall(temp)
            files = package.namelist()
            files.remove(main_dll)
            for name in [*files, main_dll]:
                target = folder / name
                if target.exists():
                    backup = backups / name
                    if not backup.exists():
                        backup.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(target, backup)
                (Path(temp) / name).replace(target)


def install(managed):
    backups = managed / "CARL-backup"
    if b"ModHooks" not in (managed / "Assembly-CSharp.dll").read_bytes():
        with urlopen(CATALOG + "ApiLinks.xml") as response:
            unpack(ET.parse(response).find(".//{*}Windows"), managed, "Assembly-CSharp.dll", backups)

    mods = managed / "Mods"
    missing = []
    for name in MODS:
        dll = "Archipelago.HollowKnight.dll" if name == "Archipelago" else name + ".dll"
        if (mods / "Disabled" / name / dll).is_file() and not (mods / name).exists():
            (mods / "Disabled" / name).rename(mods / name)
        if not (mods / name / dll).is_file():
            missing.append((name, dll))
    if missing:
        with urlopen(CATALOG + "ModLinks.xml") as response:
            entries = ET.parse(response).findall("{*}Manifest")
        links = {entry.findtext("{*}Name"): entry.find("{*}Link") for entry in entries}
        for name, dll in missing:
            unpack(links[name], mods / name, dll, backups / "Mods" / name)


def play(address, name):
    folder = GAME
    if not (folder / "hollow_knight.exe").is_file():
        picked = filedialog.askdirectory(title="Where is Hollow Knight?")
        if not picked:
            return "CARL is ready"
        folder = Path(picked)

    data = folder / "hollow_knight_Data"
    managed = data / "Managed"
    if "1.5.78.11833".encode("utf-16-le") not in (managed / "Assembly-CSharp.dll").read_bytes():
        if (folder.parent.parent / "appmanifest_367520.acf").is_file():
            os.startfile("steam://gameproperties/367520/betas")
        return "Select Hollow Knight 1.5.78.11833 in Game Versions & Betas.\nClick Hollow Knight again after the download."

    mod = managed / "Mods/Archipelago"
    install(managed)

    server = urlsplit(f"//{address}")
    path = mod / SETTINGS.name
    if not path.exists():
        path = SETTINGS
    settings = json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else {}
    connection = settings.setdefault("MenuConnectionDetails", {})
    connection.update(ServerUrl=server.hostname, ServerPort=server.port or 38281, SlotName=name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    env = os.environ.copy()
    if (folder.parent.parent / "appmanifest_367520.acf").is_file():
        env["SteamAppId"] = "367520"
    subprocess.Popen([folder / "hollow_knight.exe", "-screen-fullscreen", "0"], cwd=folder, env=env)
    return "Choose an empty save and select Archipelago."
