"""D2 baseline governance. Baselines are content-addressed: the repo stores a
sha256 manifest (baselines.json), the images live in an artifact store / LFS
(out of git). A baseline update is a deliberate act — `record_baseline` writes
the manifest entry; CI/PR review attaches before/after images and a named
approver. Three tiers per the plan:
  (a) self      — first-run snapshot of our own render (regression-only)
  (b) ref-render — the pilot package's host ref-render (arrives with C-line)
  (c) acad      — AutoCAD reference captured per X3 (absolute fidelity)
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

TIERS = ("self", "ref-render", "acad")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass
class BaselineEntry:
    drawing: str          # logical drawing id (corpus stem / golden name)
    tier: str             # self | ref-render | acad
    sha256: str           # of the baseline image
    approver: str         # who signed off this baseline (PR reviewer)
    note: str = ""


class BaselineStore:
    """Manifest of expected baselines. The manifest (not the images) is the
    repo's source of truth; image bytes are verified by sha256 at compare time
    against whatever the artifact store/LFS provides."""

    def __init__(self, manifest_path: Path):
        self.path = Path(manifest_path)
        self.entries: Dict[str, BaselineEntry] = {}
        if self.path.is_file():
            self._load()

    def _key(self, drawing: str, tier: str) -> str:
        return drawing + "@" + tier

    def _load(self) -> None:
        doc = json.loads(self.path.read_text("utf-8"))
        for raw in doc.get("baselines", []):
            e = BaselineEntry(**raw)
            self.entries[self._key(e.drawing, e.tier)] = e

    def save(self) -> None:
        doc = {
            "schema": "vemcad.render_baselines",
            "schema_version": "0.1",
            "baselines": [vars(e) for e in sorted(
                self.entries.values(), key=lambda x: (x.drawing, x.tier))],
        }
        self.path.write_text(json.dumps(doc, ensure_ascii=False, indent=1), "utf-8")

    def get(self, drawing: str, tier: str) -> Optional[BaselineEntry]:
        return self.entries.get(self._key(drawing, tier))

    def best(self, drawing: str) -> Optional[BaselineEntry]:
        """Highest-trust baseline available: acad > ref-render > self."""
        for tier in ("acad", "ref-render", "self"):
            e = self.get(drawing, tier)
            if e:
                return e
        return None

    def record(self, drawing: str, tier: str, image_path: Path,
               approver: str, note: str = "") -> BaselineEntry:
        if tier not in TIERS:
            raise ValueError("unknown tier: %s" % tier)
        if not approver:
            raise ValueError("baseline updates require a named approver")
        e = BaselineEntry(drawing=drawing, tier=tier,
                          sha256=sha256_file(Path(image_path)),
                          approver=approver, note=note)
        self.entries[self._key(drawing, tier)] = e
        return e

    def verify_image(self, drawing: str, tier: str, image_path: Path) -> bool:
        """True if image_path's bytes match the recorded baseline sha256."""
        e = self.get(drawing, tier)
        return e is not None and e.sha256 == sha256_file(Path(image_path))
