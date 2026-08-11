"""BRD FR-3/FR-4/FR-6: solve one predefined cantilever case."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.simulation.cantilever import solve_cantilever  # noqa: E402
from app.simulation.config import default_inputs, get_paths  # noqa: E402
from app.simulation.mapdl_session import close_session, launch_session  # noqa: E402
from app.simulation.results import write_result_files  # noqa: E402


def main() -> None:
    paths = get_paths("single_1000N")
    output_dir = paths.output_root / "single"
    inputs = default_inputs()
    mapdl = None
    try:
        mapdl = launch_session(paths.mapdl_executable, paths.run_root, "cantilever")
        result = solve_cantilever(mapdl, inputs, output_dir)
        write_result_files(result, output_dir)
        print(f"Completed: {result.case_id}")
        print(f"Maximum stress: {result.maximum_stress_pa:.6g} Pa")
        print(f"Maximum displacement: {result.maximum_displacement_m:.6g} m")
        print(f"Results: {output_dir}")
    finally:
        if mapdl is not None:
            close_session(mapdl, "cantilever")


if __name__ == "__main__":
    main()
