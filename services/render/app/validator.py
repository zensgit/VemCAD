"""cad_package validator — contract §9 semantics for 2D up to `standard`
(plan A4 capability ceiling: `rich` is never granted in v0; 3D disciplines
get an unsupported note; quarantine is per-payload; the floor is
`source-only`; check-in is never blocked by package quality).

Payloads are treated as untrusted bytes: this module hashes and magic-sniffs
only — it never decodes images/fonts (decoding happens in the sandbox worker
class per plan A3).
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from .packagestore import schema_major

SCHEMA_NAME = "vemcad.cad_package"
KNOWN_MAJOR = 0

LEVELS = ["source-only", "minimal", "standard", "rich"]

_SHA_RE = re.compile(r"^[0-9a-f]{64}$")
_BG_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_BINARY_DXF_SENTINEL = b"AutoCAD Binary DXF"

CAPTURE_METHODS = ("offscreen-render", "plot-raster", "viewport-capture", "dwg-thumbnail")
CAPTURED_AT = ("save", "checkin")
REF_RENDER_MIN_LONG_EDGE = 1600

# role → (min, max or None=unbounded) for discipline 2d-drawing
ROLE_CARDINALITY = {
    "twin-dxf": (0, 1),
    "twin-dxf-flattened": (0, 1),
    "xref-dxf": (0, None),
    "underlay-image": (0, None),
    "plot-pdf": (0, None),
    "ref-render": (0, None),
    "font-shx": (0, None),
    "font-ttf": (0, None),
    "bom": (0, None),
    "thumbnail": (0, None),
}


@dataclass
class Entry:
    role: str
    sha256: str
    file_name: str
    size_bytes: Optional[int]
    params: dict
    payload: Optional[bytes] = None  # None = not delivered
    quarantined: bool = False
    reason: str = ""


@dataclass
class ValidationResult:
    ok_manifest: bool
    package_id: Optional[str]
    claimed_level: Optional[str]
    validated_level: str
    warnings: List[dict] = field(default_factory=list)
    quarantined: List[dict] = field(default_factory=list)
    incomplete_preview: bool = False
    notes_echo: list = field(default_factory=list)
    error: Optional[str] = None

    def report(self) -> dict:
        return {
            "schema": "vemcad.package_validation_report",
            "schema_version": "0.1",
            "package_id": self.package_id,
            "claimed_level": self.claimed_level,
            "validated_level": self.validated_level,
            "warnings": self.warnings,
            "quarantined": self.quarantined,
            "incomplete_preview": self.incomplete_preview,
            "notes_echo": self.notes_echo,
            "error": self.error,
        }


def _warn(result: ValidationResult, code: str, message: str, **extra):
    w = {"code": code, "message": message}
    w.update(extra)
    result.warnings.append(w)


def _required_str(d: dict, key: str) -> bool:
    return isinstance(d.get(key), str) and bool(d.get(key))


def _manifest_basics_ok(m: dict, result: ValidationResult) -> bool:
    if m.get("schema") != SCHEMA_NAME:
        result.error = "unknown schema: %r" % (m.get("schema"),)
        return False
    major = schema_major(m.get("schema_version", ""))
    if major is None or major != KNOWN_MAJOR:
        result.error = "unknown schema_version major: %r" % (m.get("schema_version"),)
        return False
    for key in ("package_id", "level", "discipline", "created_at"):
        if not _required_str(m, key):
            result.error = "missing/invalid top-level field: %s" % key
            return False
    producer = m.get("producer")
    if not isinstance(producer, dict) or not all(
        _required_str(producer, k) for k in ("kind", "host_app", "plugin_name", "plugin_version")
    ):
        result.error = "missing/invalid producer block"
        return False
    source = m.get("source")
    if (
        not isinstance(source, dict)
        or not _required_str(source, "file_name")
        or not _required_str(source, "sha256")
        or not _SHA_RE.match(source.get("sha256", ""))
    ):
        result.error = "missing/invalid source block"
        return False
    if not isinstance(m.get("files"), list):
        result.error = "files must be a list"
        return False
    return True


def _metadata_well_formed(meta, result: ValidationResult) -> bool:
    if not isinstance(meta, dict):
        _warn(result, "metadata-malformed", "metadata is not an object")
        return False
    sheets = meta.get("sheets")
    if sheets is not None:
        if not isinstance(sheets, list) or any(not isinstance(s, dict) for s in sheets):
            _warn(result, "metadata-malformed", "metadata.sheets is not a list of objects")
            return False
    ext = meta.get("external_refs")
    if ext is not None:
        if not isinstance(ext, list) or any(not isinstance(e, dict) for e in ext):
            _warn(result, "metadata-malformed", "metadata.external_refs is not a list of objects")
            return False
    for flag in ("fields_present", "dynamic_blocks_present", "annotative_present", "xrefs_present"):
        if flag in meta and not isinstance(meta[flag], bool):
            _warn(result, "metadata-malformed", "metadata.%s is not a boolean" % flag)
            return False
    return True


def _parse_entries(m: dict, payloads: Dict[str, bytes], result: ValidationResult) -> List[Entry]:
    entries: List[Entry] = []
    for raw in m.get("files", []):
        if not isinstance(raw, dict):
            result.quarantined.append({"role": None, "sha256": None, "reason": "entry-not-object"})
            continue
        role = raw.get("role")
        sha = str(raw.get("sha256", "")).lower()
        e = Entry(
            role=str(role),
            sha256=sha,
            file_name=str(raw.get("file_name", "")),
            size_bytes=raw.get("size_bytes") if isinstance(raw.get("size_bytes"), int) else None,
            params=raw.get("params") if isinstance(raw.get("params"), dict) else {},
        )
        if role not in ROLE_CARDINALITY:
            # Unknown roles are ignored with a warning (contract §2.3 forward compat).
            _warn(result, "unknown-role", "ignoring unknown role %r" % role, file_name=e.file_name)
            continue
        if not _SHA_RE.match(sha):
            e.quarantined, e.reason = True, "invalid-sha256"
        else:
            e.payload = payloads.get(sha)
            if e.payload is None:
                e.quarantined, e.reason = True, "payload-missing"
            elif e.size_bytes is not None and e.size_bytes != len(e.payload):
                e.quarantined, e.reason = True, "size-mismatch"
        if not e.quarantined:
            e.quarantined, e.reason = _role_format_violation(e)
        if e.quarantined:
            result.quarantined.append(
                {"role": e.role, "sha256": e.sha256, "file_name": e.file_name, "reason": e.reason}
            )
        entries.append(e)
    return entries


def _role_format_violation(e: Entry):
    head = (e.payload or b"")[:4096]
    if e.role in ("twin-dxf", "twin-dxf-flattened", "xref-dxf"):
        if head.startswith(_BINARY_DXF_SENTINEL):
            return True, "binary-dxf-not-accepted"
        if b"SECTION" not in head and b"EOF" not in head:
            return True, "not-a-text-dxf"
    elif e.role in ("ref-render", "thumbnail"):
        if not head.startswith(_PNG_MAGIC):
            return True, "not-a-png"
    elif e.role == "plot-pdf":
        if not head.startswith(b"%PDF"):
            return True, "not-a-pdf"
    elif e.role == "bom":
        try:
            json.loads((e.payload or b"").decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            return True, "bom-not-json"
    return False, ""


def _ref_render_conforming(e: Entry, result: ValidationResult) -> bool:
    p = e.params
    problems = []
    view = p.get("view")
    if not (view == "extents" or str(view).startswith(("layout:", "named-view:")) or view == "iso"):
        problems.append("view")
    try:
        w, h = int(p.get("width_px")), int(p.get("height_px"))
        if max(w, h) < REF_RENDER_MIN_LONG_EDGE:
            problems.append("long-edge<%d" % REF_RENDER_MIN_LONG_EDGE)
    except (TypeError, ValueError):
        problems.append("width_px/height_px")
    if not _BG_RE.match(str(p.get("background", ""))):
        problems.append("background")
    if p.get("capture_method") not in CAPTURE_METHODS:
        problems.append("capture_method")
    if p.get("captured_at_event") not in CAPTURED_AT:
        problems.append("captured_at_event")
    if problems:
        _warn(
            result, "ref-render-nonconforming",
            "ref-render %s does not meet §7: %s" % (e.file_name, ", ".join(problems)),
        )
        return False
    return True


def _check_cardinality(entries: List[Entry], result: ValidationResult):
    counts: Dict[str, int] = {}
    for e in entries:
        if not e.quarantined:
            counts[e.role] = counts.get(e.role, 0) + 1
    for role, n in counts.items():
        lo, hi = ROLE_CARDINALITY[role]
        if hi is not None and n > hi:
            # Quarantine the extras beyond the cardinality bound.
            seen = 0
            for e in entries:
                if e.role == role and not e.quarantined:
                    seen += 1
                    if seen > hi:
                        e.quarantined, e.reason = True, "cardinality-exceeded"
                        result.quarantined.append(
                            {"role": e.role, "sha256": e.sha256,
                             "file_name": e.file_name, "reason": e.reason}
                        )


def _incomplete_preview(meta: dict, entries: List[Entry]) -> bool:
    refs = meta.get("external_refs") or []
    xref_payloads = {e.sha256 for e in entries if e.role == "xref-dxf" and not e.quarantined}
    for r in refs:
        if not isinstance(r, dict):
            continue
        if r.get("resolved") is False:
            return True
        # Freeze-review addendum: resolved dwg-xref without uploaded payload.
        if r.get("kind") == "dwg-xref" and r.get("resolved") is True:
            sha = str(r.get("sha256", "")).lower()
            if sha not in xref_payloads:
                return True
    return False


def validate_package(manifest: dict, payloads: Dict[str, bytes]) -> ValidationResult:
    """§9 validation. `payloads` maps sha256 → bytes for delivered payloads."""
    result = ValidationResult(
        ok_manifest=False,
        package_id=None,
        claimed_level=None,
        validated_level="source-only",
    )
    if not isinstance(manifest, dict) or not _manifest_basics_ok(manifest, result):
        result.validated_level = "rejected"
        return result
    result.ok_manifest = True
    result.package_id = manifest["package_id"]
    result.claimed_level = manifest.get("level")
    notes = manifest.get("notes")
    if isinstance(notes, list):
        result.notes_echo = notes

    if manifest.get("discipline") != "2d-drawing":
        _warn(result, "3d-not-supported-v0",
              "discipline %r is stored but not validated in v0 (plan A4 ceiling)"
              % manifest.get("discipline"))
        result.validated_level = "source-only"
        return result

    entries = _parse_entries(manifest, payloads, result)
    _check_cardinality(entries, result)

    meta = manifest.get("metadata")
    meta_ok = _metadata_well_formed(meta, result)
    if meta_ok and isinstance(meta, dict):
        result.incomplete_preview = _incomplete_preview(meta, entries)
        if result.incomplete_preview:
            _warn(result, "incomplete-preview",
                  "external references unresolved or not uploaded — preview will be incomplete")

    live = [e for e in entries if not e.quarantined]
    twin_ok = sum(1 for e in live if e.role == "twin-dxf") == 1
    ref_ok = any(e.role == "ref-render" and _ref_render_conforming(e, result) for e in live)

    if not meta_ok:
        result.validated_level = "source-only"
    elif twin_ok and ref_ok:
        result.validated_level = "standard"
    else:
        result.validated_level = "minimal"
        if result.claimed_level in ("standard", "rich"):
            missing = []
            if not twin_ok:
                missing.append("twin-dxf")
            if not ref_ok:
                missing.append("conforming ref-render")
            _warn(result, "level-downgraded",
                  "claimed %s but surviving payloads only satisfy %s (missing: %s)"
                  % (result.claimed_level, result.validated_level, ", ".join(missing)))

    if result.claimed_level == "rich":
        _warn(result, "rich-not-granted-v0",
              "rich is never granted by the v0 validator (plan A4 ceiling)")
    return result


def load_package_dir(package_dir: Path):
    """CLI convention: a directory with cad_package.json + payload files
    (any names — located by content hash, per contract §2.1)."""
    manifest_path = package_dir / "cad_package.json"
    manifest = json.loads(manifest_path.read_text("utf-8"))
    payloads: Dict[str, bytes] = {}
    from .cache import sha256_bytes  # local import to avoid cycles

    for p in sorted(package_dir.iterdir()):
        if p.is_file() and p.name != "cad_package.json":
            data = p.read_bytes()
            payloads[sha256_bytes(data)] = data
    return manifest, payloads
