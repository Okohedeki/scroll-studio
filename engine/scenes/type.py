"""type: kinetic typography; nothing to build ahead of time."""
from ..project import BuildContext
from ..spec import TypeScene


def build(sec: TypeScene, ctx: BuildContext, theme: dict) -> dict:
    return {"mode": sec.mode, "text": sec.text, "words": sec.words}
