import json
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.request import urlretrieve
from zipfile import ZipFile


FOLDER = Path(__file__).resolve().parents[1] / "data" / "Ship of Harkinian"
PACKAGE = ("https://github.com/HarbourMasters/Archipelago-SoH/releases/download/"
           "Soh_1.4.2/SoH_Archipelago_1-4-2_Windows.zip")


def install():
    FOLDER.parent.mkdir(exist_ok=True)
    with TemporaryDirectory(dir=FOLDER.parent) as temp:
        archive = Path(temp) / "ship.zip"
        urlretrieve(PACKAGE, archive)
        with ZipFile(archive) as package:
            package.extractall(FOLDER)


def play(address, name):
    game = FOLDER / "soh.exe"
    if not game.is_file():
        install()

    path = FOLDER / "shipofharkinian.json"
    settings = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    remote = settings.setdefault("CVars", {}).setdefault("gRemote", {})
    connection = remote.setdefault("Archipelago", {})
    connection.update(ServerAddress=address, SlotName=name)
    path.write_text(json.dumps(settings, indent=4), encoding="utf-8")
    subprocess.Popen([game], cwd=FOLDER)
    return "Ship of Harkinian is open. Choose your Archipelago save."
