"""Check the local PoC prerequisites before starting MAPDL."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.simulation.config import get_paths  # noqa: E402


def main() -> None:
    paths = get_paths("preflight")
    print(f"Python: {sys.version.split()[0]}")
    print(f"MAPDL executable: {paths.mapdl_executable}")
    print(f"MAPDL executable exists: {paths.mapdl_executable.is_file()}")
    print(f"MAPDL run root: {paths.run_root}")
    print("Ansys environment:")
    for name in ("AWP_ROOT261", "ANSYS261_DIR", "CADOE_LIBDIR261", "ANSYSLMD_LICENSE_FILE"):
        value = os.environ.get(name)
        print(f"  {name}: {value or '<not set>'}")

    process_names = {"AnsysWBU.exe", "AnsysWB.exe", "Workbench.exe"}
    running = []
    for row in subprocess.run(
        ["tasklist", "/FO", "CSV", "/NH"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines():
        name = row.split(",", 1)[0].strip('"') if row else ""
        if name in process_names:
            running.append(name)

    if running:
        print("WARNING: close Workbench/Mechanical before the solve:")
        for name in sorted(set(running)):
            print(f"  {name}")
    else:
        print("Workbench/Mechanical GUI processes detected: none")


if __name__ == "__main__":
    main()
