"""Real-MAPDL acceptance matrix for force ranges on every UI template."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.simulation.cantilever import solve_cantilever_range  # noqa: E402
from app.simulation.config import CantileverInputs, ForceRange, get_paths  # noqa: E402
from app.simulation.examples import ExampleInputs, solve_example_range  # noqa: E402
from app.simulation.mapdl_session import close_session, launch_session  # noqa: E402
from app.simulation.results import write_result_files  # noqa: E402


RANGE = ForceRange(start_n=100.0, end_n=1000.0, steps=3)


def _cases():
    return [
        CantileverInputs(case_id="verify_cantilever", force_n=RANGE.end_n),
        ExampleInputs(
            template="table", case_id="verify_table", force_n=RANGE.end_n,
            length_m=1.2, width_m=0.6, height_m=0.75,
            diameter_m=0.04, mesh_size_m=0.05,
        ),
        ExampleInputs(
            template="bolt", case_id="verify_bolt", force_n=RANGE.end_n,
            length_m=0.08, diameter_m=0.01, mesh_size_m=0.01,
        ),
        ExampleInputs(
            template="screw", case_id="verify_screw", force_n=RANGE.end_n,
            length_m=0.06, diameter_m=0.006, mesh_size_m=0.01,
        ),
        ExampleInputs(
            template="nut", case_id="verify_nut", force_n=RANGE.end_n,
            length_m=0.02, diameter_m=0.014, mesh_size_m=0.005,
        ),
    ]


def _assert_result(template: str, result, output_dir: Path) -> None:
    if result.template != template:
        raise AssertionError(f"{template}: result template mismatch")
    if result.force_steps != len(RANGE.values()) or not result.force_curve:
        raise AssertionError(f"{template}: incomplete force curve")
    if [point["force_n"] for point in result.force_curve] != list(RANGE.values()):
        raise AssertionError(f"{template}: force points are not inclusive/evenly spaced")
    for field in ("maximum_stress_pa", "maximum_displacement_m"):
        values = [float(point[field]) for point in result.force_curve]
        if not all(math.isfinite(value) and value >= 0 for value in values):
            raise AssertionError(f"{template}: invalid {field}")
        if any(right + 1e-12 < left for left, right in zip(values, values[1:])):
            raise AssertionError(f"{template}: {field} is not monotonic")
    for filename in (
        "results.json", "results.csv", "stress.png", "deformation.png",
        "failure_assessment.png", "force_sweep.png",
    ):
        path = output_dir / filename
        if not path.is_file() or path.stat().st_size == 0:
            raise AssertionError(f"{template}: missing artifact {filename}")


def main() -> None:
    paths = get_paths("range_verification")
    report = []
    for inputs in _cases():
        template = getattr(inputs, "template", "cantilever")
        output_dir = paths.output_root / "range_verification" / template
        run_dir = paths.run_root / template
        jobname = f"vr_{template}"
        mapdl = None
        try:
            mapdl = launch_session(paths.mapdl_executable, run_dir, jobname)
            if template == "cantilever":
                result = solve_cantilever_range(mapdl, inputs, RANGE, output_dir)
            else:
                result = solve_example_range(mapdl, inputs, RANGE, output_dir)
            write_result_files(result, output_dir)
            _assert_result(template, result, output_dir)
            report.append({
                "template": template,
                "points": result.force_steps,
                "maximum_stress_pa": result.maximum_stress_pa,
                "maximum_displacement_m": result.maximum_displacement_m,
                "break_force_n": result.break_force_n,
                "status": "passed",
            })
            print(f"PASS {template}: {result.force_steps} independent MAPDL solves")
        finally:
            if mapdl is not None:
                close_session(mapdl, jobname)

    report_path = paths.output_root / "range_verification" / "verification.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Acceptance report: {report_path}")


if __name__ == "__main__":
    main()
