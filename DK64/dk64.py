import base64
import hashlib
import json
import shutil
import subprocess
import sys
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from tkinter import filedialog, messagebox
from urllib.request import urlopen, urlretrieve
from zipfile import ZipFile


DATA = Path(__file__).resolve().parents[1] / "data/DK64"


def generate_rom(patch, base_rom, version, target):
    try:
        from playwright.sync_api import Error, sync_playwright
    except ModuleNotFoundError as error:
        if error.name != "playwright":
            raise
        subprocess.run([sys.executable, "-m", "pip", "install", "playwright"], check=True)
        from playwright.sync_api import Error, sync_playwright

    for site in ("https://dev.dk64randomizer.com", "https://dk64randomizer.com"):
        with urlopen(site + "/version.py", timeout=20) as response:
            if f'version = "{version}"' in response.read().decode():
                break
    else:
        raise ValueError(f"The official DK64 patchers do not currently list version {version}.")

    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        with sync_playwright() as tools, TemporaryDirectory(dir=target.parent) as temp:
            browser = tools.chromium.launch(channel="msedge", headless=True)
            page = browser.new_page()
            page.goto(site + "/randomizer", wait_until="domcontentloaded", timeout=120000)
            page.locator("#nav-patch-tab").click()
            page.wait_for_function("typeof filebox === 'function' && window.romdatabase?.readyState === 'done'")
            with page.expect_file_chooser() as chooser:
                page.locator("#choose_rom_2").click()
            chooser.value.set_files(base_rom)
            page.locator("#rom.is-valid").wait_for(state="attached", timeout=90000)
            page.locator("#patchfileloader").set_input_files(patch)
            page.locator("#patchfileloader.is-valid").wait_for()
            with page.expect_download(timeout=300000) as output:
                page.locator("#generate_lanky_seed").click()
            rom = Path(temp) / "patched.z64"
            output.value.save_as(rom)
            with rom.open("rb") as file:
                if file.read(4) != bytes.fromhex("80371240"):
                    raise ValueError("The DK64 patcher did not return a .z64 ROM.")
            rom.replace(target)
    except Error as error:
        raise ValueError(f"DK64 patcher: {error.message.splitlines()[0]}") from error


def find_rom(patch, name):
    with ZipFile(patch) as archive:
        manifest = json.loads(archive.read("archipelago.json"))
        if manifest["game"] != "Donkey Kong 64" or manifest["player_name"] != name:
            raise ValueError(f"Choose the Donkey Kong 64 patch for {name}.")
        payload = archive.read("patch_data")
    with ZipFile(BytesIO(base64.b64decode(payload))) as seed:
        seed_id = seed.read("seed_id").decode()
        version = seed.read("version").decode().strip()
    record = DATA / (hashlib.sha256(payload).hexdigest() + ".txt")
    if record.exists():
        rom = Path(record.read_text(encoding="utf-8"))
        if rom.is_file():
            return rom
    filename = f"dk64r-rom-{seed_id}.z64"
    downloads = Path.home() / "Downloads"
    for folder in (patch.parent, downloads, DATA):
        rom = folder / Path(filename).name
        if rom.is_file():
            break
    else:
        existing = messagebox.askyesnocancel("Donkey Kong 64", "Have you already created the ROM for this patch?")
        if existing is None:
            return
        if existing:
            picked = filedialog.askopenfilename(title="Choose the patched DK64 ROM", initialdir=downloads,
                                                filetypes=[("Patched DK64 ROM", "*.z64")])
            if not picked:
                return
            rom = Path(picked)
        else:
            picked = filedialog.askopenfilename(title="Choose your original US DK64 ROM", initialdir=downloads,
                                                filetypes=[("DK64 ROM", "*.z64 *.n64 *.v64")])
            if not picked:
                return
            rom = DATA / Path(filename).name
            generate_rom(patch, Path(picked), version, rom)
    DATA.mkdir(parents=True, exist_ok=True)
    record.write_text(str(rom), encoding="utf-8")
    return rom


def install(archipelago):
    folder = DATA / "Project64"
    exe = folder / "Project64.exe"
    if not exe.is_file():
        with TemporaryDirectory(dir=DATA) as temp:
            package = Path(temp) / "project64.zip"
            urlretrieve("https://www.pj64-emu.com/file/project64-3-0-1-5664-2df3434/", package)
            with ZipFile(package) as archive:
                staged = Path(temp) / "Project64"
                archive.extractall(staged)
                shutil.copytree(staged, folder, dirs_exist_ok=True)

    database = folder / "Config/Project64.rdb"
    if b"[69696969-69696969-C:45]" not in database.read_bytes():
        with database.open("ab") as file:
            file.write(b"\r\n[DONKEY KONG 64-C:45]\r\nAlt Identifier=69696969-69696969-C:45\r\nRDRAM Size=8\r\n"
                       b"\r\n[69696969-69696969-C:45]\r\nInternal Name=DONKEY KONG 64\r\nStatus=Compatible\r\n"
                       b"Counter Factor=1\r\nCulling=1\r\nEmulate Clear=1\r\nPrimary Frame Buffer=1\r\n"
                       b"Save Type=16kbit Eeprom\r\nLinking=Off\r\n")

    world = archipelago / "custom_worlds/dk64.apworld"
    if not world.is_file():
        world.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(Path(__file__).with_name(world.name), world)
    adapter = archipelago / "custom_worlds/carl_dk64.apworld"
    if not adapter.exists():
        with TemporaryDirectory(dir=adapter.parent) as temp:
            package = Path(temp) / adapter.name
            with ZipFile(package, "w") as archive:
                archive.write(Path(__file__).with_name("client.py"), "carl_dk64/__init__.py")
            package.replace(adapter)
    return exe


def play(address, name, archipelago):
    picked = filedialog.askopenfilename(title="Choose your DK64 patch", filetypes=[("DK64 patch", "*.chunky")])
    if not picked:
        return "CARL is ready"
    rom = find_rom(Path(picked), name)
    if not rom:
        return "CARL is ready"
    emulator = install(archipelago)
    subprocess.Popen([emulator, rom], cwd=emulator.parent)
    subprocess.Popen([archipelago / "ArchipelagoLauncher.exe", "CARL DK64", "--", address], cwd=archipelago)
    return "CARL is opening Donkey Kong 64."
