"""Scene modules. Each exposes build(section, ctx, theme) -> client config (asset URLs + player options).

Adding a new kind of site = a spec class in engine/spec.py, a builder here, and a player in runtime/src/players.
"""
from importlib import import_module

MODULES = {
    "film": "film",
    "artwork": "artwork",
    "scene3d": "scene3d",
    "sequence": "sequence",
    "parallax": "parallax",
    "type": "type",
    "vector": "vector",
    "chart": "chart",
    "map": "map",
}


def builder_for(scene_type: str):
    if scene_type not in MODULES:
        raise KeyError(f"no builder for scene type '{scene_type}'")
    return import_module(f"{__name__}.{MODULES[scene_type]}").build
