import json
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory
from tkinter import filedialog


def enable_expansion_pak(archipelago):
    import yaml

    with (archipelago / "host.yaml").open(encoding="utf-8-sig") as file:
        options = yaml.safe_load(file).get("bizhawkclient_options", {})
    emulator = archipelago / options.get("emuhawk_path", "EmuHawk.exe")
    if not emulator.is_file():
        picked = filedialog.askopenfilename(title="Where is BizHawk?", filetypes=[("BizHawk", "EmuHawk.exe")])
        if not picked:
            raise ValueError("Choose BizHawk to enable the Expansion Pak.")
        emulator = Path(picked)

    path = emulator.with_name("config.ini")
    config = json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else {}
    core = "BizHawk.Emulation.Cores.Nintendo.N64.N64"
    settings = config.setdefault("CoreSyncSettings", {}).setdefault(core, {
        "$type": "BizHawk.Emulation.Cores.Nintendo.N64.N64SyncSettings, BizHawk.Emulation.Cores"
    })
    if settings.get("DisableExpansionSlot") is not False:
        settings["DisableExpansionSlot"] = False
        with TemporaryDirectory(dir=path.parent) as temp:
            updated = Path(temp) / path.name
            updated.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
            updated.replace(path)


def install(archipelago):
    enable_expansion_pak(archipelago)
    world = archipelago / "custom_worlds/papermario.apworld"
    if not world.exists():
        world.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(Path(__file__).with_name(world.name), world)


def play(address, name, play_patch):
    return play_patch(address, name, "Paper Mario", ".appm64", install)
