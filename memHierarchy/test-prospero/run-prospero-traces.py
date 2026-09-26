#!/usr/bin/env python3

import os
import shutil
import subprocess
import sys
from pathlib import Path


def resolve_sst_executable() -> str:
    """Return path to the SST driver. Prefer SST_EXE, then SST, then PATH."""
    for key in ("SST_EXE", "SST"):
        v = os.environ.get(key, "").strip()
        if not v:
            continue
        if os.path.isfile(v) and os.access(v, os.X_OK):
            return v
        on_path = shutil.which(v)
        if on_path:
            return on_path
    w = shutil.which("sst")
    return w if w else ""


def filter_prospero_run_output(log_text: str, *, opt_on: bool, opt_on_env: str) -> str:
    """Keep SDL banner ([prospero-test] ... opt_on=...) and custom L1 counter lines."""
    banner = []
    counters = []
    for line in log_text.splitlines():
        if "[prospero-test]" in line:
            banner.append(line)
        if "Counter[" in line and "inv=" in line:
            counters.append(line)
    if not banner:
        banner.append(
            f"[prospero-runner] OPT_ON={opt_on_env} mode={'opt' if opt_on else 'base'} "
            "(no [prospero-test] line in SST stdout)"
        )
    parts = []
    parts.extend(banner)
    parts.append("")
    parts.extend(counters)
    return "\n".join(parts) + ("\n" if parts else "")


def run_case(sst_exe: str, sdl_path: Path, opt_on: bool, env_base: dict, out_name: str) -> None:
    env = dict(env_base)
    env["OPT_ON"] = "1" if opt_on else "0"

    out_path = sdl_path.parent / out_name
    res = subprocess.run(
        [sst_exe, str(sdl_path)],
        cwd=str(sdl_path.parent),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    if res.returncode != 0:
        print(res.stdout, end="")
        raise subprocess.CalledProcessError(res.returncode, res.args, output=res.stdout)
    out_path.write_text(
        filter_prospero_run_output(res.stdout, opt_on=opt_on, opt_on_env=env["OPT_ON"]),
        encoding="utf-8",
    )


def main() -> int:
    base_dir = Path(__file__).resolve().parent
    sdl_path = base_dir / "example-4core-prospero.py"
    if not sdl_path.exists():
        raise FileNotFoundError(f"Missing SDL: {sdl_path}")

    sst_exe = resolve_sst_executable()
    if not sst_exe:
        print(
            "[prospero] error: SST executable not found.\n"
            "  Fix: run after `source init.sh` (or your module load), or set SST_EXE to the full path, e.g.\n"
            "    export SST_EXE=/path/to/sst/bin/sst\n"
            "  Then re-run: python3 run-prospero-traces.py",
            file=sys.stderr,
        )
        return 1

    protocol = "MESI"

    # Directory containing the editable trace files:
    #   prospero-traces/prospero_core0.trace ... prospero_core3.trace
    trace_dir = base_dir / "prospero-traces"
    if not trace_dir.exists():
        raise FileNotFoundError(
            f"Trace dir not found: {trace_dir}. Create/adjust it or run the generating script first."
        )

    env_base = os.environ.copy()
    env_base["PROSPERO_TRACE_DIR"] = str(trace_dir)

    for opt_on in (False, True):
        out_name = f"prospero_{protocol.lower()}_{'opt' if opt_on else 'base'}.out"
        print(f"[prospero] run protocol={protocol} {'opt' if opt_on else 'base'} -> {out_name} (sst={sst_exe})")
        run_case(sst_exe, sdl_path, opt_on=opt_on, env_base=env_base, out_name=out_name)

    print("[prospero] done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

