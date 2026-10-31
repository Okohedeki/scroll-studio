"""The shortlist: the best candidates that stay far enough apart, so a shot never shows several takes of one idea."""
from __future__ import annotations

from typing import Optional

import numpy as np

from .critics import distance


def pick(candidates: list[dict], vectors: dict[str, np.ndarray], keep: int, min_gap: Optional[float] = None,
         fail_below: float = 0.0) -> list[str]:
    """Ids of up to `keep` candidates, best score first, each at least `min_gap` from those already picked (default:
    a third of the median distance between all of them). Candidates scoring at or under `fail_below` never make it."""
    ok = [c for c in candidates if c["score"] > fail_below]
    ok.sort(key=lambda c: -c["score"])
    if min_gap is None:
        ids = [c["id"] for c in ok]
        ds = [distance(vectors[a], vectors[b]) for i, a in enumerate(ids) for b in ids[i + 1:]]
        min_gap = float(np.median(ds)) / 3 if ds else 0.0
    picked: list[str] = []
    for c in ok:
        if len(picked) >= keep:
            break
        if all(distance(vectors[c["id"]], vectors[p]) >= min_gap for p in picked):
            picked.append(c["id"])
    return picked
