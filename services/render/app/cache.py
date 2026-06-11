"""Content-addressed render cache with the four-tuple key (plan A2a):
(content sha256, canonical params, render_cli binary sha256, font-store
fingerprint). The renderer-version and font components exist from day one so
a renderer upgrade or font-set change can never serve stale pixels."""

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Optional


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def font_fingerprint(font_dir: Optional[Path]) -> str:
    if not font_dir or not font_dir.is_dir():
        return "no-fonts"
    entries = []
    for p in sorted(font_dir.iterdir(), key=lambda q: q.name.lower()):
        if p.is_file():
            entries.append(p.name.lower() + ":" + sha256_file(p))
    if not entries:
        return "no-fonts"
    return sha256_bytes("\n".join(entries).encode("utf-8"))


def cache_key(content_sha: str, params: dict, cli_sha: str, font_fp: str) -> str:
    payload = json.dumps(
        {"content": content_sha, "params": params, "cli": cli_sha, "fonts": font_fp},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return sha256_bytes(payload.encode("utf-8"))


class RenderCache:
    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _dir(self, key: str) -> Path:
        return self.root / key[:2]

    def artifact_path(self, key: str, fmt: str) -> Path:
        return self._dir(key) / (key + "." + fmt)

    def report_path(self, key: str) -> Path:
        return self._dir(key) / (key + ".report.json")

    def get(self, key: str, fmt: str) -> Optional[Path]:
        p = self.artifact_path(key, fmt)
        return p if p.is_file() and p.stat().st_size > 0 else None

    def get_report(self, key: str) -> Optional[dict]:
        p = self.report_path(key)
        if not p.is_file():
            return None
        try:
            return json.loads(p.read_text("utf-8"))
        except (OSError, ValueError):
            return None

    def put(self, key: str, fmt: str, src: Path, report: dict) -> Path:
        d = self._dir(key)
        d.mkdir(parents=True, exist_ok=True)
        dst = self.artifact_path(key, fmt)
        # Atomic publish: copy to a temp name in the same dir, then rename.
        fd, tmp = tempfile.mkstemp(dir=str(d), suffix=".tmp")
        try:
            with os.fdopen(fd, "wb") as out, open(src, "rb") as inp:
                for chunk in iter(lambda: inp.read(1 << 20), b""):
                    out.write(chunk)
            os.replace(tmp, dst)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
        rp = self.report_path(key)
        rp.write_text(json.dumps(report, ensure_ascii=False, indent=1), "utf-8")
        return dst
