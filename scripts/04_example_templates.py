"""Run one bounded example for each additional dashboard template."""

from __future__ import annotations

import csv
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.simulation.config import get_paths  # noqa: E402
from app.simulation.examples import ExampleInputs, solve_example  # noqa: E402
from app.simulation.mapdl_session import close_session, launch_session  # noqa: E402
from app.simulation.results import SimulationResult, write_result_files  # noqa: E402


def main() -> None:
    paths = get_paths("examples")
    cases: list[ExampleInputs] = []
    with (PROJECT_ROOT / "input" / "example_cases.csv").open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            cases.append(
                ExampleInputs(
                    template=row["template"],
                    case_id=row["case_id"],
                    force_n=float(row["force_n"]),
                    length_m=float(row["length_m"]),
                    width_m=float(row["width_m"]),
                    height_m=float(row["height_m"]),
                    diameter_m=float(row["diameter_m"]),
                    mesh_size_m=float(row["mesh_size_m"]),
                    material=row["material"],
                )
            )

    results: list[SimulationResult] = []
    for inputs in cases:
        inputs.validate()
        output_dir = paths.output_root / "examples" / inputs.template
        run_dir = paths.run_root / inputs.template
        mapdl = None
        try:
            mapdl = launch_session(paths.mapdl_executable, run_dir, inputs.template)
            result = solve_example(mapdl, inputs, output_dir)
            write_result_files(result, output_dir)
            results.append(result)
            print(
                f"Completed: {inputs.template} | "
                f"stress={result.maximum_stress_pa:.6g} Pa | "
                f"displacement={result.maximum_displacement_m:.6g} m | "
                f"safety_factor={result.safety_factor:.6g}"
            )
        finally:
            if mapdl is not None:
                close_session(mapdl, inputs.template)

    aggregate = paths.output_root / "examples" / "results.csv"
    aggregate.parent.mkdir(parents=True, exist_ok=True)
    rows = [result.as_dict() for result in results]
    with aggregate.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Aggregate results: {aggregate}")


if __name__ == "__main__":
    main()
