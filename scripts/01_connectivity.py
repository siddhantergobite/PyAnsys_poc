"""BRD FR-1/FR-2: launch MAPDL and print its version."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.simulation.config import get_paths  # noqa: E402
from app.simulation.mapdl_session import close_session, launch_session  # noqa: E402


def main() -> None:
    paths = get_paths("connectivity")
    mapdl = None
    payload = {
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "mapdl_executable": str(paths.mapdl_executable),
        "status": "failed",
    }
    try:
        mapdl = launch_session(paths.mapdl_executable, paths.run_root, "connectivity")
        payload.update({"status": "connected", "mapdl_version": str(mapdl.version)})
        print("MAPDL launched successfully")
        print(f"MAPDL version: {mapdl.version}")
    finally:
        if mapdl is not None:
            close_session(mapdl, "connectivity")
            print("MAPDL session closed")
        with (paths.output_root / "connectivity" / "connectivity.json").open(
            "w", encoding="utf-8"
        ) as stream:
            json.dump(payload, stream, indent=2)


if __name__ == "__main__":
    main()
