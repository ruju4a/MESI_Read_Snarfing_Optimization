#!/usr/bin/env python3

import os
import subprocess
import sys
from pathlib import Path


CASES = [
    ("disjoint_writes", "baseline with little/no sharing"),
    ("disjoint_read_only", "private reads (MESI tends to keep E, MSI uses S)"),
    ("disjoint_read_then_write", "private read->write on same lines (MESI E->M vs MSI S->M)"),
    ("single_line_read_sharing", "all cores read one shared line repeatedly"),
    ("shared_read_only", "shared lines, reads only"),
    ("shared_write_pingpong", "shared lines, writes by all cores"),
    ("mixed_rw_upgrade", "cores 0-1 read, cores 2-3 write"),
]


def run_case(sst_input: Path, case_name: str, description: str, protocol: str) -> None:
    env = os.environ.copy()
    env["MIRANDA_CASE"] = case_name
    env["MIRANDA_PROTOCOL"] = protocol

    out_name = f"miranda_bus_suite_{case_name}_{protocol.lower()}.out"
    out_path = sst_input.parent / out_name

    print(f"[bus-suite] running {case_name} [{protocol}]: {description}")
    print(f"[bus-suite] output -> {out_path.name}")

    with out_path.open("w", encoding="utf-8") as outfile:
        subprocess.run(
            ["sst", str(sst_input)],
            cwd=str(sst_input.parent),
            env=env,
            stdout=outfile,
            stderr=subprocess.STDOUT,
            check=True,
        )


def main() -> int:
    base_dir = Path(__file__).resolve().parent
    sst_input = base_dir / "example-4core-miranda-coherence.py"

    if not sst_input.exists():
        print(f"[bus-suite] missing input file: {sst_input}", file=sys.stderr)
        return 1

    valid_case_names = {name for name, _ in CASES}
    selected_cases = valid_case_names
    protocol = os.environ.get("MIRANDA_PROTOCOL", "MSI").strip().upper()
    valid_protocols = {"MSI", "MESI"}
    if protocol not in valid_protocols:
        print(f"[bus-suite] invalid MIRANDA_PROTOCOL '{protocol}'", file=sys.stderr)
        print(f"[bus-suite] valid protocols: {', '.join(sorted(valid_protocols))}", file=sys.stderr)
        return 3

    if len(sys.argv) > 1:
        selected_cases = set(sys.argv[1:])
        unknown = sorted(selected_cases - valid_case_names)
        if unknown:
            print(f"[bus-suite] unknown case(s): {', '.join(unknown)}", file=sys.stderr)
            print(f"[bus-suite] valid cases: {', '.join(name for name, _ in CASES)}", file=sys.stderr)
            return 2

    for case_name, description in CASES:
        if case_name not in selected_cases:
            continue
        run_case(sst_input, case_name, description, protocol)

    print("[bus-suite] done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
