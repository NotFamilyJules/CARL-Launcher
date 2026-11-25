import json
import os
import re
import shutil
import subprocess
import time
import winreg
from configparser import ConfigParser
from pathlib import Path
from tempfile import TemporaryDirectory
from tkinter import filedialog
from zipfile import BadZipFile, ZipFile


DATA = Path(__file__).resolve().parents[1] / "data" / "Factorio"
EXE = Path("bin/x64/factorio.exe")
AP_MOD = re.compile(r"AP-(\d+)-P\d+-(.+)")
client = None


def steam_install():
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
        steam = Path(winreg.QueryValueEx(key, "SteamPath")[0])
    libraries = (steam / "steamapps/libraryfolders.vdf").read_text(encoding="utf-8")
    for library in re.findall(r'"path"\s+"([^"]+)"', libraries):
        apps = Path(library.replace("\\\\", "\\")) / "steamapps"
        manifest = apps / "appmanifest_427520.acf"
        if manifest.is_file():
            folder = re.search(r'"installdir"\s+"([^"]+)"', manifest.read_text(encoding="utf-8"))
            if folder:
                game = apps / "common" / folder[1]
                if (game / EXE).is_file():
                    return game
    raise ValueError("CARL couldn't find Factorio in your Steam libraries.")


def standalone_install(steam):
    location = DATA / "standalone.txt"
    if location.is_file():
        folder = Path(location.read_text(encoding="utf-8"))
        if (folder / EXE).is_file() and not folder.samefile(steam):
            return folder
    picked = filedialog.askdirectory(title="Choose your standalone Factorio folder")
    if not picked:
        return None
    folder = Path(picked)
    if not (folder / EXE).is_file() or folder.samefile(steam):
        raise ValueError("Choose the standalone Factorio folder containing bin/x64/factorio.exe.")
    DATA.mkdir(parents=True, exist_ok=True)
    location.write_text(str(folder), encoding="utf-8")
    return folder


def backup(mod, folder):
    destination = folder / mod.name
    number = 1
    while destination.exists():
        destination = folder / str(number) / mod.name
        number += 1
    destination.parent.mkdir(parents=True, exist_ok=True)
    mod.rename(destination)


def install_mod(patch, info, mods, disabled):
    mods.mkdir(parents=True, exist_ok=True)
    filename = f"{info['name']}_{info['version']}.zip"
    for mod in mods.iterdir():
        if AP_MOD.fullmatch(mod.name) and (mod.is_dir() or mod.suffix.lower() == ".zip"):
            if mod.name == filename and mod.is_file() and mod.read_bytes() == patch.read_bytes():
                continue
            backup(mod, mods / "ap_backup")
    target = mods / filename
    if not target.exists():
        shutil.copy2(patch, target)

    path = mods / "mod-list.json"
    settings = json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else {"mods": [{"name": "base", "enabled": True}]}
    by_name = {entry["name"]: entry for entry in settings["mods"] if not AP_MOD.fullmatch(entry["name"])}
    for name in disabled:
        by_name.setdefault(name, {"name": name})["enabled"] = False
    by_name[info["name"]] = {"name": info["name"], "enabled": True}
    settings["mods"] = list(by_name.values())
    path.write_text(json.dumps(settings, indent=2), encoding="utf-8")


def write_data(game):
    def expand(value):
        return Path(value.replace("__PATH__system-write-data__", str(Path(os.environ["APPDATA"]) / "Factorio"))
                         .replace("__PATH__executable__", str((game / EXE).parent)))

    paths = ConfigParser(interpolation=None)
    paths.read_string("[install]\n" + (game / "config-path.cfg").read_text(encoding="utf-8-sig"))
    config = ConfigParser(interpolation=None, strict=False)
    config.read(expand(paths["install"]["config-path"]) / "config.ini", encoding="utf-8-sig")
    default = "__PATH__system-write-data__" if paths["install"].getboolean("use-system-read-write-data-directories") else str(game)
    return expand(config.get("path", "write-data", fallback=default)).resolve()


def configure_host(archipelago, steam, host_data):
    import yaml

    user = archipelago if os.access(archipelago, os.W_OK) else Path.home() / "Archipelago"
    host = user / "host.yaml"
    text = host.read_text(encoding="utf-8-sig")
    executable = (steam / EXE).as_posix()
    if yaml.safe_load(text).get("factorio_options", {}).get("executable") != executable:
        if re.search(r"^factorio_options:.*$", text, re.M):
            text = re.sub(r"(^factorio_options:[^\n]*\n)((?:[ \t][^\n]*\n|\n)*)",
                          lambda m: m[1] + "  executable: " + json.dumps(executable) + "\n"
                          + re.sub(r"^  executable:[^\n]*\n", "", m[2], flags=re.M), text, count=1, flags=re.M)
        else:
            text += "\nfactorio_options:\n  executable: " + json.dumps(executable) + "\n"
        host.write_text(text, encoding="utf-8")
    path = user / "factorio/config/apconfig.ini"
    text = path.read_text(encoding="utf-8-sig") if path.exists() else "[path]\nread-data=__PATH__system-read-data__\n"
    line = "write-data=" + host_data.as_posix()
    updated = re.sub(r"^write-data\s*=.*$", lambda _: line, text, flags=re.M)
    if updated == text and not re.search(r"^write-data\s*=", text, re.M):
        updated = text.replace("[path]", "[path]\n" + line, 1)
    if updated != text:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(updated, encoding="utf-8")


def play(address, name, archipelago, status):
    global client
    picked = filedialog.askopenfilename(title="Choose your Factorio mod", filetypes=[("Factorio mod", "*.zip")])
    if not picked:
        return "CARL is ready"
    if client and client.poll() is None:
        return "Close the running Archipelago Factorio client before starting another game."
    patch = Path(picked)
    try:
        with ZipFile(patch) as archive:
            info_path = next((p for p in archive.namelist() if re.fullmatch(r"[^/]+/info\.json", p)), None)
            if not info_path:
                raise ValueError("Choose the generated Factorio mod ZIP for your slot.")
            info = json.loads(archive.read(info_path))
    except BadZipFile as error:
        raise ValueError("Choose the generated Factorio mod ZIP for your slot.") from error
    mod = AP_MOD.fullmatch(info.get("name", ""))
    if not mod or mod[2] != name:
        raise ValueError(f"Choose the generated Factorio mod for {name}.")
    steam = steam_install()
    player = standalone_install(steam)
    if not player:
        return "CARL is ready"
    versions = [json.loads((g / "data/base/info.json").read_text())["version"] for g in (steam, player)]
    if versions[0] != versions[1] or versions[0].rsplit(".", 1)[0] != info["factorio_version"]:
        raise ValueError(f"Steam is {versions[0]}. Standalone is {versions[1]}. Use matching Factorio {info['factorio_version']} versions.")
    host_data, player_data = write_data(steam), write_data(player)
    if host_data == player_data:
        raise ValueError("The standalone copy needs its own Factorio write-data folder.")
    DATA.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=DATA) as temp:
        staged = Path(temp) / patch.name
        shutil.copy2(patch, staged)
        for folder in (host_data, player_data):
            install_mod(staged, info, folder / "mods", ("space-age", "quality", "elevated-rails"))
    configure_host(archipelago, steam, host_data)
    log = host_data / "factorio-current.log"
    started = time.time()
    client = subprocess.Popen([archipelago / "ArchipelagoLauncherDebug.exe", "Factorio Client", "--",
                               "--port", "34197"], cwd=archipelago, stdin=subprocess.PIPE,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                              text=True, creationflags=subprocess.CREATE_NO_WINDOW)
    process = client

    def join():
        if process.poll() is not None:
            status.config(text="The Archipelago Factorio client closed before the server was ready.")
            return
        try:
            text = log.read_text(encoding="utf-8", errors="replace") if log.stat().st_mtime >= started else ""
        except (FileNotFoundError, PermissionError):
            text = ""
        if re.search(rf"Loading map .*[/\\]AP_{mod[1]}_[^\n]*_Save\.zip", text) and "New RCON connection" in text:
            process.stdin.write(f"/connect {address}\n")
            process.stdin.flush()
            subprocess.Popen([player / EXE, "--mp-connect", "127.0.0.1:34197"], cwd=player)
            status.config(text="Factorio is joining the local server.")
            return
        status.after(1000, join)

    status.after(1000, join)
    return "Waiting for the local Factorio server."
