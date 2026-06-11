"""Subprocess sandbox for untrusted-input rendering (plan A3).

The Linux canonical deployment adds container-level network isolation
(`--network none`, asserted via RENDER_ASSUME_NO_NETWORK=1); on macOS dev
machines we opportunistically wrap with `sandbox-exec` (deny network) and
always record whether isolation applied. The same runner class is reused by
the package validator and the regression comparator (plan A3: all payload
parsing inside the sandbox worker class).
"""

import os
import resource
import shutil
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

_MACOS_DENY_NET_PROFILE = "(version 1)(allow default)(deny network*)"
_TAIL = 4096

# Qt/fontconfig need these to reach a non-system Qt build and the font cache;
# scrubbing them breaks (or silently degrades) rendering on the Linux image.
_ENV_PASSTHROUGH = (
    "LD_LIBRARY_PATH",
    "QT_PLUGIN_PATH",
    "QT_QPA_FONTDIR",
    "FONTCONFIG_PATH",
    "FONTCONFIG_FILE",
    "LANG",
    "LC_ALL",
)


@dataclass
class SandboxResult:
    exit_code: int
    timed_out: bool
    duration_s: float
    stdout: str
    stderr: str
    network_isolated: bool


class SandboxRunner:
    def __init__(
        self,
        timeout_s: float,
        mem_limit_mb: int,
        allow_sandbox_exec: bool = True,
        cache_home: Optional[Path] = None,
    ):
        self.timeout_s = timeout_s
        self.mem_limit_mb = mem_limit_mb
        self.allow_sandbox_exec = allow_sandbox_exec
        # Persistent XDG cache (fontconfig) so every render does not rebuild
        # the font cache inside a throwaway tempdir.
        self.cache_home = cache_home

    def _limits(self):  # pragma: no cover - runs in the forked child
        mem = self.mem_limit_mb * 1024 * 1024
        for limit in (resource.RLIMIT_AS, resource.RLIMIT_DATA):
            try:
                resource.setrlimit(limit, (mem, mem))
            except (ValueError, OSError):
                pass
        try:
            cpu = int(self.timeout_s) + 30
            resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu))
        except (ValueError, OSError):
            pass

    def _build_env(self, workdir: Path, extra_env: Optional[Dict[str, str]]) -> Dict[str, str]:
        env = {
            "QT_QPA_PLATFORM": "offscreen",
            "HOME": str(workdir),
            "TMPDIR": str(workdir),
            "PATH": "/usr/bin:/bin",
            "XDG_CACHE_HOME": str(self.cache_home or workdir),
        }
        for key in _ENV_PASSTHROUGH:
            val = os.environ.get(key)
            if val:
                env[key] = val
        if extra_env:
            env.update(extra_env)
        return env

    def run(
        self,
        argv: List[str],
        workdir: Path,
        extra_env: Optional[Dict[str, str]] = None,
        timeout_s: Optional[float] = None,
    ) -> SandboxResult:
        wrapped = list(argv)
        network_isolated = False
        if sys.platform == "darwin" and self.allow_sandbox_exec and shutil.which("sandbox-exec"):
            wrapped = ["sandbox-exec", "-p", _MACOS_DENY_NET_PROFILE] + wrapped
            network_isolated = True
        elif sys.platform.startswith("linux"):
            # Container-level `--network none` is asserted by deployment.
            network_isolated = os.environ.get("RENDER_ASSUME_NO_NETWORK") == "1"

        timeout = timeout_s if timeout_s is not None else self.timeout_s
        start = time.monotonic()
        proc = subprocess.Popen(
            wrapped,
            cwd=str(workdir),
            env=self._build_env(workdir, extra_env),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            errors="replace",
            start_new_session=True,  # setsid in C — no thread-unsafe setsid in preexec
            preexec_fn=self._limits,  # rlimits only; minimal post-fork body
        )
        try:
            out, err = proc.communicate(timeout=timeout)
            timed_out = False
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except OSError:
                proc.kill()
            out, err = proc.communicate()
            timed_out = True
        return SandboxResult(
            exit_code=proc.returncode if not timed_out else -1,
            timed_out=timed_out,
            duration_s=time.monotonic() - start,
            stdout=(out or "")[-_TAIL:],
            stderr=(err or "")[-_TAIL:],
            network_isolated=network_isolated,
        )
