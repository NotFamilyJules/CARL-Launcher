import os
import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from tkinter import filedialog
from urllib.request import urlretrieve
from zipfile import ZipFile


GAME = Path("C:/Program Files (x86)/Steam/steamapps/common/Celeste")
EVEREST = "https://github.com/EverestAPI/Everest/releases/download/stable-1.6696.0/main.zip"
MOD = "https://github.com/PoryGoneDev/Celeste-Archipelago-Open-World/releases/download/v1.1.3/Archipelago_Open_World.zip"


def install(folder):
    if not (folder / "Celeste.dll").is_file() or not (folder / "orig/Celeste.exe").is_file():
        with TemporaryDirectory() as temp:
            archive = Path(temp) / "everest.zip"
            urlretrieve(EVEREST, archive)
            with ZipFile(archive) as package:
                package.extractall(temp)
            shutil.copytree(Path(temp) / "main", folder, dirs_exist_ok=True)
        subprocess.run([folder / "MiniInstaller-win64.exe"], cwd=folder, check=True)

    mods = folder / "Mods"
    mods.mkdir(exist_ok=True)
    mod = mods / "Archipelago_Open_World.zip"
    if not mod.is_file():
        with TemporaryDirectory(dir=mods) as temp:
            download = Path(temp) / mod.name
            urlretrieve(MOD, download)
            download.replace(mod)
    blacklist = mods / "blacklist.txt"
    if blacklist.is_file():
        lines = blacklist.read_bytes().splitlines(keepends=True)
        enabled = [line for line in lines if line.strip().lower() != mod.name.lower().encode()]
        if enabled != lines:
            blacklist.write_bytes(b"".join(enabled))


def play(address, name):
    import yaml

    folder = GAME
    if not (folder / "Celeste.exe").is_file():
        picked = filedialog.askdirectory(title="Where is Celeste?")
        if not picked:
            return "CARL is ready"
        folder = Path(picked)
        if not (folder / "Celeste.exe").is_file():
            raise ValueError("Choose the folder containing Celeste.exe.")

    install(folder)
    path = folder / "Saves/modsettings-Archipelago Open World.celeste"
    settings = yaml.safe_load(path.read_text(encoding="utf-8-sig")) if path.exists() else {}
    settings.update(Address=address, SlotName=name)
    path.parent.mkdir(exist_ok=True)
    with TemporaryDirectory(dir=path.parent) as temp:
        updated = Path(temp) / path.name
        updated.write_text(yaml.safe_dump(settings, sort_keys=False, allow_unicode=True), encoding="utf-8")
        updated.replace(path)
    env = os.environ.copy()
    if (folder.parent.parent / "appmanifest_504230.acf").is_file():
        env["SteamAppId"] = "504230"
    subprocess.Popen([folder / "Celeste.exe"], cwd=folder, env=env)
    return "Choose Connect in Celeste."
