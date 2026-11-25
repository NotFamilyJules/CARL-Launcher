import sys

from worlds.LauncherComponents import Component, Type, components


def launch(address):
    from archipelago.DK64Client import launch as start

    sys.argv[1:] = ["--connect", address]
    start()


components.append(Component("CARL DK64", func=launch, component_type=Type.CLIENT))
