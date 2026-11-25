import hashlib
import json
import os
import shutil
import subprocess
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from tkinter import filedialog, ttk
from urllib.request import urlretrieve
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SOURCE = DATA / "sm64ex"
MSYS = Path("C:/msys64")
REGIONS = {
    "8a20a5c83d6ceb0f0506cfc9fa20d8f438cafe51": "jp",
    "9bef1128717f958171a4afac3ed78ee2bb4e86ce": "us",
}


def port(region):
    return SOURCE / f"build/{region}_pc/sm64.{region}.f3dex2e.exe"


def build(rom):
    region = REGIONS.get(hashlib.sha1(rom.read_bytes()).hexdigest())
    if not region:
        raise ValueError("Give CARL a Japanese or US Super Mario 64 .z64 ROM.")
    DATA.mkdir(exist_ok=True)
    env = dict(os.environ, MSYSTEM="MINGW64", CHERE_INVOKING="1")
    with TemporaryDirectory(dir=DATA, prefix="sm64-build-") as folder, (DATA / "sm64-build.log").open("w") as log:
        source = Path(folder) / SOURCE.name
        try:
            subprocess.run(["git", "clone", "--recursive", "--single-branch", "--branch", "archipelago",
                            "https://github.com/N00byKing/sm64ex.git", source],
                           stdout=log, stderr=subprocess.STDOUT, check=True)
            shutil.copyfile(rom, source / f"baserom.{region}.z64")
            subprocess.run([MSYS / "usr/bin/bash.exe", "-lc", f"make -j4 WINDOWS_CONSOLE=1 VERSION={region}"],
                           cwd=source, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
        except subprocess.CalledProcessError as error:
            raise ValueError("SM64 build failed. Check data/sm64-build.log.") from error
        game = port(region)
        output = source / "build" / f"{region}_pc"
        if SOURCE.exists():
            shutil.copy2(source / f"baserom.{region}.z64", SOURCE)
            game.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(output / "libAPCpp.dll", game.parent)
            shutil.copy2(output / game.name, game)
        else:
            source.rename(SOURCE)
    return region


def build_with_progress(rom):
    window = tk.Toplevel()
    window.title("CARL is Building Super Mario 64")
    bar = ttk.Progressbar(window, length=250, mode="indeterminate")
    bar.pack(padx=10, pady=10)
    bar.start()
    window.grab_set()
    window.protocol("WM_DELETE_WINDOW", window.bell)
    with ThreadPoolExecutor(max_workers=1) as worker:
        job = worker.submit(build, rom)

        def check():
            if job.done():
                window.destroy()
            else:
                window.after(250, check)

        window.after(250, check)
        window.wait_window()
        return job.result()


def open_launcher(region, options):
    folder = DATA / "SM64AP-Launcher"
    exe = folder / "SM64APLauncher.exe"
    if not exe.is_file():
        with TemporaryDirectory(dir=DATA) as temp:
            archive = Path(temp) / "launcher.zip"
            urlretrieve("https://github.com/N00byKing/SM64AP-Launcher/releases/download/rel8/SM64AP-Launcher_windows.zip", archive)
            with ZipFile(archive) as package:
                package.extractall(folder)

    profile = folder / "SM64APLauncher_config.json"
    config = json.loads(profile.read_text(encoding="utf-8")) if profile.exists() else {}
    config["msys_path"] = MSYS.as_posix()
    config["default_build_root"] = DATA.as_posix()
    config.setdefault("rom_paths", {"jp": "_None", "us": "_None"})[region] = (SOURCE / f"baserom.{region}.z64").as_posix()
    config.setdefault("builds", {})[SOURCE.name] = {
        "directory": DATA.as_posix(), "region": region.upper(), "branch": "archipelago",
        "repo": "https://github.com/N00byKing/sm64ex", "patches": [], "make_flags": "-j4 WINDOWS_CONSOLE=1",
        "launch_opts": subprocess.list2cmdline(options),
    }
    profile.write_text(json.dumps(config, indent=2), encoding="utf-8")
    subprocess.Popen([exe], cwd=folder)


def play(address, name):
    selection = DATA / "sm64-console-region.txt"
    region = selection.read_text().strip() if selection.is_file() else ""
    if region not in REGIONS.values() or not port(region).is_file():
        picked = filedialog.askopenfilename(title="Choose your Super Mario 64 ROM",
                                            filetypes=[("Super Mario 64 ROM", "*.z64")])
        if not picked:
            return "CARL is ready"
        region = build_with_progress(Path(picked))
        selection.write_text(region)
    game = port(region)
    options = ["--windowed", "--sm64ap_ip", address, "--sm64ap_name", name]
    open_launcher(region, options)
    env = dict(os.environ, PATH=str(MSYS / "mingw64/bin") + os.pathsep + os.environ["PATH"])
    subprocess.Popen([game, *options],
                     cwd=game.parent, env=env, creationflags=subprocess.CREATE_NEW_CONSOLE)
    return "CARL is connecting to Super Mario 64..."
