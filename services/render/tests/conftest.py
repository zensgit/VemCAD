import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import find_default_render_cli, load_settings  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"


def resolve_render_cli():
    env = os.environ.get("RENDER_CLI_PATH")
    if env and Path(env).is_file():
        return Path(env)
    return find_default_render_cli()


RENDER_CLI = resolve_render_cli()

needs_render_cli = pytest.mark.skipif(
    RENDER_CLI is None, reason="render_cli binary not found (set RENDER_CLI_PATH)"
)


@pytest.fixture
def settings(tmp_path):
    return load_settings(
        render_cli=str(RENDER_CLI) if RENDER_CLI else None,
        cache_dir=str(tmp_path / "cache"),
        workers=2,
        timeout_s=60.0,
    )


@pytest.fixture
def fixture_dxf():
    return (FIXTURES / "block_ellipse.dxf").read_bytes()
