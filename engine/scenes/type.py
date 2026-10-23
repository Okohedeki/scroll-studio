"""type: kinetic typography; nothing to build ahead of time."""
from ..project import BuildContext
from ..safety import angle_escaped
from ..spec import TypeScene


def build(sec: TypeScene, ctx: BuildContext, theme: dict) -> dict:
    # the runtime sets these with innerHTML: <em> stays, any other tag is shown as text
    return {"mode": sec.mode, "text": angle_escaped(sec.text, keep_em=True), "words": [angle_escaped(w, keep_em=True) for w in sec.words]}
