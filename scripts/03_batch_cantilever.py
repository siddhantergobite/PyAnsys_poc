"""BRD FR-5: run the approved force cases and aggregate CSV output."""

from __future__ import annotations

import csv
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.simulation.cantilever import solve_cantilever  # noqa: E402
from app.simulation.config import CantileverInputs, get_paths  # noqa: E402
from app.simulation.mapdl_session import close_session, launch_session  # noqa: E402
from app.simulation.results import SimulationResult, write_result_files  # noqa: E402


def read_cases(path: Path) -> list[CantileverInputs]:
    with path.open(newline="", encoding="utf-8") as stream:
        rows = csv.DictReader(stream)
        return [
            CantileverInputs(
                case_id=row["case_id"],
                force_n=float(row["force_n"]),
                length_m=float(row["length_m"]),
                width_m=float(row["width_m"]),
                height_m=float(row["height_m"]),
                material=row["material"],
            )
            for row in rows
        ]


def write_batch_csv(results: list[SimulationResult], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [result.as_dict() for result in results]
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    paths = get_paths("batch")
    cases = read_cases(PROJECT_ROOT / "input" / "cases.csv")
    results: list[SimulationResult] = []
    for inputs in cases:
        inputs.validate()
        case_dir = paths.output_root / "batch" / inputs.case_id
        run_dir = paths.run_root / inputs.case_id
        mapdl = None
        try:
            mapdl = launch_session(paths.mapdl_executable, run_dir, inputs.case_id)
            result = solve_cantilever(mapdl, inputs, case_dir)
            write_result_files(result, case_dir)
            results.append(result)
            print(f"Completed: {inputs.case_id}")
        finally:
            if mapdl is not None:
                close_session(mapdl, inputs.case_id)

    write_batch_csv(results, paths.output_root / "batch" / "results.csv")
    print(f"Batch results: {paths.output_root / 'batch' / 'results.csv'}")


if __name__ == "__main__":
    main()
