import hashlib
import os
import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile


def find_hades():
    steamapps = Path("C:/Program Files (x86)/Steam/steamapps")
    manifest = steamapps / "appmanifest_1145360.acf"

    if not manifest.is_file():
        return None

    for line in manifest.read_text(encoding="utf-8-sig").splitlines():
        if '"installdir"' in line:
            folder = line.split('"')[-2]
            path = steamapps / "common" / folder

            if (path / "Content").is_dir():
                return path

    return None


def configure_client(source):
    source = source.replace(
        "args = parser.parse_args()",
        'args = parser.parse_args([] if sys.argv[1:] == ["Hades Client"] else None)',
    )
    source = source.replace(
        'styx_scribe_path = settings.get_settings()',
        'styx_scribe_path = os.getenv("CARL_STYX_SCRIBE") or settings.get_settings()',
    )
    source = source.replace(
        '    thr.start()',
        '    if os.getenv("CARL_SERVER"):\n'
        '        subsume.args.extend(["/FullScreen=false", "/NoBorder=false", "/X=1280", "/Y=720"])\n'
        '    thr.start()',
    )
    return source.replace(
        '        ctx.server_task =',
        '        if os.getenv("CARL_SERVER"):\n'
        '            import yaml\n'
        '            with open(os.environ["CARL_PLAYER_YAML"], encoding="utf-8-sig") as player:\n'
        '                ctx.username = yaml.safe_load(player)["name"]\n'
        '            ctx.server_address = os.environ["CARL_SERVER"]\n'
        '        ctx.server_task =',
    )


def install_client(archipelago):
    original = Path(__file__).with_name("hades.apworld")
    installed = archipelago / "custom_worlds/hades.apworld"
    release_hash = "bbf210a05d6f8cce322db23dc50befda2b0ee7b432e65c8380777e62ae3b050f"
    if hashlib.sha256(original.read_bytes()).hexdigest() != release_hash:
        raise ValueError("CARL needs Polycosmos 0.16.3")

    if installed.is_file() and hashlib.sha256(installed.read_bytes()).hexdigest() == "18d56a27713add9874fce7b21b75a89ed260231081e670f9f281f8031ea50962":
        return
    installed.parent.mkdir(exist_ok=True)
    with TemporaryDirectory(dir=installed.parent) as folder:
        updated = Path(folder) / original.name
        with ZipFile(original) as src, ZipFile(updated, "w") as dst:
            for entry in src.infolist():
                data = src.read(entry)
                if entry.filename == "hades/Client.py":
                    data = configure_client(data.decode("utf-8")).encode("utf-8")
                dst.writestr(entry, data)

        current = installed.read_bytes() if installed.exists() else original.read_bytes()
        if current == updated.read_bytes():
            return
        if current != original.read_bytes():
            raise ValueError("CARL doesn't recognize the provided APWorld. Installation stopped.")
        updated.replace(installed)


def install(hades_path, archipelago):
    source = Path(__file__).resolve().parent
    content = hades_path / "Content"
    main_script = content / "Scripts/Main.lua"
    if not main_script.is_file() or not (hades_path / "x64/Hades.exe").is_file():
        raise ValueError("CARL couldn't verify Hades.")
    if not (archipelago / "ArchipelagoLauncher.exe").is_file():
        raise ValueError("CARL couldn't find Archipelago.")
    install_client(archipelago)

    mods = content / "Mods"
    scribe = source / "StyxScribeWTREPL"
    files = [(scribe / "StyxScribe.py", hades_path / "StyxScribe.py"),
             (source / "modimporter.exe", content / "modimporter.exe")]
    for package, destination in [(source / "Polycosmos", mods / "Polycosmos"),
                                 (source / "SGG_Modding-ModUtil-2.10.1", mods / "ModUtil"),
                                 (scribe / "Content/Mods", mods)]:
        for file in package.rglob("*"):
            if file.is_file():
                files.append((file, destination / file.relative_to(package)))

    pending = content / ".carl-import-pending"
    for file, destination in files:
        if not destination.exists():
            pending.touch()
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file, destination)

    if pending.exists() or "Polycosmos" not in main_script.read_text(encoding="utf-8-sig"):
        subprocess.run([content / "modimporter.exe"], cwd=content, input=b"\n", check=True)
        pending.unlink(missing_ok=True)


if __name__ == "__main__":
    game = find_hades()
    if game is None:
        raise SystemExit("Feed CARL your Hades folder.")
    install(game, Path(os.environ["ProgramData"]) / "Archipelago")
