"""Env-driven settings for the render service (plan A2a/A3)."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

ENV_PREFIX = "RENDER_"

DEFAULT_MAX_UPLOAD_BYTES = 48 * 1024 * 1024  # /render direct-upload cap (independent of contract §2.4)
DEFAULT_TIMEOUT_S = 120.0
DEFAULT_MEM_LIMIT_MB = 2048
MAX_SIDE_PX = 8192
MAX_PIXELS = 64_000_000  # aligns with contract §2.4 raster ceiling (64 MP)


def find_default_render_cli(start: Optional[Path] = None) -> Optional[Path]:
    """Walk up from this file looking for the in-repo render_cli build."""
    here = (start or Path(__file__)).resolve()
    for parent in here.parents:
        cand = parent / "deps" / "cadgamefusion" / "build" / "editor" / "qt" / "render_cli"
        if cand.is_file():
            return cand
    return None


@dataclass(frozen=True)
class Settings:
    render_cli: Optional[Path]
    cache_dir: Path
    font_dir: Optional[Path]
    max_upload_bytes: int
    workers: int
    timeout_s: float
    mem_limit_mb: int
    allow_sandbox_exec: bool
    # Optional bearer token. Empty/None = no auth (Phase-1 trusted-internal
    # status quo). Set RENDER_AUTH_TOKEN to require `Authorization: Bearer <token>`
    # on the data endpoints (/render, /diff, /package*) — /healthz stays open.
    auth_token: Optional[str] = None


def load_settings(**overrides) -> Settings:
    def env(name: str, default: Optional[str] = None) -> Optional[str]:
        return os.environ.get(ENV_PREFIX + name, default)

    def pick(key: str, env_name: str, default=None):
        if key in overrides:
            return overrides[key]
        return env(env_name, default)

    cli_raw = pick("render_cli", "CLI_PATH")
    cli = Path(cli_raw) if cli_raw else find_default_render_cli()
    if cli is not None and not Path(cli).is_file():
        cli = None

    font_raw = pick("font_dir", "FONT_DIR")
    font_dir = Path(font_raw) if font_raw else None

    cache_raw = pick("cache_dir", "CACHE_DIR")
    cache_dir = Path(cache_raw) if cache_raw else Path.home() / ".cache" / "vemcad-render"

    workers_default = max(1, (os.cpu_count() or 4) // 2)

    return Settings(
        render_cli=Path(cli) if cli else None,
        cache_dir=cache_dir,
        font_dir=font_dir,
        max_upload_bytes=int(pick("max_upload_bytes", "MAX_UPLOAD_BYTES", DEFAULT_MAX_UPLOAD_BYTES)),
        workers=int(pick("workers", "WORKERS", workers_default)),
        timeout_s=float(pick("timeout_s", "TIMEOUT_S", DEFAULT_TIMEOUT_S)),
        mem_limit_mb=int(pick("mem_limit_mb", "MEM_LIMIT_MB", DEFAULT_MEM_LIMIT_MB)),
        allow_sandbox_exec=str(pick("allow_sandbox_exec", "SANDBOX_EXEC", "1")) not in ("0", "false", "False"),
        auth_token=(pick("auth_token", "AUTH_TOKEN", None) or None),
    )
