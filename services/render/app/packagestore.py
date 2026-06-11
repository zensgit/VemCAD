"""Content-addressed package store with contract §2.2 identity semantics.

Layout (under <root>):
  <identity[:2]>/<identity>/<package_id>/manifest.json
  <identity[:2]>/<identity>/<package_id>/report.json
  <identity[:2]>/<identity>/<package_id>/payloads/<sha256>
  <identity[:2]>/<identity>/latest.json        — upsert pointer
  _index/<package_id>.json                     — package_id → location

Identity key = (tenant, source.sha256, producer.plugin_name,
producer.host_app, schema_major). Nothing is ever overwritten: every
package_id is retained; the `latest` pointer implements upsert, and MUST NOT
move backwards to a lower producer.plugin_version (contract §2.2).
"""

import hashlib
import json
import re
from pathlib import Path
from typing import Dict, Optional, Tuple

DEFAULT_TENANT = "default"


def schema_major(schema_version: str) -> Optional[int]:
    m = re.match(r"^(\d+)\.", str(schema_version) + ".")
    return int(m.group(1)) if m else None


def identity_key(manifest: dict, tenant: str = DEFAULT_TENANT) -> str:
    payload = json.dumps(
        {
            "tenant": tenant,
            "source_sha256": manifest.get("source", {}).get("sha256"),
            "plugin_name": manifest.get("producer", {}).get("plugin_name"),
            "host_app": manifest.get("producer", {}).get("host_app"),
            "schema_major": schema_major(manifest.get("schema_version", "")),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _version_tuple(version: str) -> Tuple:
    parts = []
    for piece in str(version).split("."):
        m = re.match(r"^(\d+)", piece)
        parts.append(int(m.group(1)) if m else 0)
    return tuple(parts) or (0,)


class PackageStore:
    def __init__(self, root: Path):
        self.root = root
        (self.root / "_index").mkdir(parents=True, exist_ok=True)

    def _identity_dir(self, identity: str) -> Path:
        return self.root / identity[:2] / identity

    def package_dir(self, identity: str, package_id: str) -> Path:
        return self._identity_dir(identity) / package_id

    def save(
        self,
        manifest: dict,
        payloads: Dict[str, bytes],
        report: dict,
        tenant: str = DEFAULT_TENANT,
    ) -> dict:
        """Persist a validated package. Returns upsert info (identity,
        superseded flag). Caller passes payloads keyed by sha256 — only the
        ones that were actually received."""
        identity = identity_key(manifest, tenant)
        package_id = str(manifest.get("package_id"))
        pdir = self.package_dir(identity, package_id)
        paydir = pdir / "payloads"
        paydir.mkdir(parents=True, exist_ok=True)

        (pdir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=1), "utf-8"
        )
        for sha, data in payloads.items():
            (paydir / sha).write_bytes(data)
        (pdir / "report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=1), "utf-8"
        )

        # Upsert pointer: never moves to a lower plugin_version (§2.2).
        latest_path = self._identity_dir(identity) / "latest.json"
        incoming_version = manifest.get("producer", {}).get("plugin_version", "0")
        superseded_by_existing = False
        if latest_path.is_file():
            try:
                current = json.loads(latest_path.read_text("utf-8"))
            except (OSError, ValueError):
                current = {}
            cur_ver = current.get("plugin_version", "0")
            if _version_tuple(incoming_version) < _version_tuple(cur_ver):
                superseded_by_existing = True
        if not superseded_by_existing:
            latest_path.write_text(
                json.dumps(
                    {"package_id": package_id, "plugin_version": incoming_version},
                    ensure_ascii=False,
                ),
                "utf-8",
            )

        (self.root / "_index" / (package_id + ".json")).write_text(
            json.dumps({"identity": identity, "tenant": tenant}, ensure_ascii=False),
            "utf-8",
        )
        return {"identity": identity, "superseded_by_existing": superseded_by_existing}

    def locate(self, package_id: str) -> Optional[Path]:
        idx = self.root / "_index" / (package_id + ".json")
        if not idx.is_file():
            return None
        try:
            meta = json.loads(idx.read_text("utf-8"))
        except (OSError, ValueError):
            return None
        pdir = self.package_dir(meta["identity"], package_id)
        return pdir if pdir.is_dir() else None

    def get_report(self, package_id: str) -> Optional[dict]:
        pdir = self.locate(package_id)
        if not pdir:
            return None
        try:
            return json.loads((pdir / "report.json").read_text("utf-8"))
        except (OSError, ValueError):
            return None

    def get_manifest(self, package_id: str) -> Optional[dict]:
        pdir = self.locate(package_id)
        if not pdir:
            return None
        try:
            return json.loads((pdir / "manifest.json").read_text("utf-8"))
        except (OSError, ValueError):
            return None

    def get_payload(self, package_id: str, sha256: str) -> Optional[bytes]:
        pdir = self.locate(package_id)
        if not pdir:
            return None
        p = pdir / "payloads" / sha256
        if not re.match(r"^[0-9a-f]{64}$", sha256) or not p.is_file():
            return None
        return p.read_bytes()
