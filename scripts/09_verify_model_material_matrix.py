"""Real-MAPDL acceptance matrix for every template/material combination."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.simulation.cantilever import solve_cantilever  # noqa: E402
from app.simulation.config import CantileverInputs, get_paths  # noqa: E402
from app.simulation.examples import ExampleInputs, solve_example  # noqa: E402
from app.simulation.mapdl_session import close_session, launch_session  # noqa: E402
from app.simulation.materials import MATERIAL_NAMES  # noqa: E402


def _input_for(template: str, material: str):
    common = {"case_id": f"matrix_{template}", "force_n": 100.0, "material": material}
    if template == "cantilever":
        return CantileverInputs(**common)
    dimensions = {
        "table": dict(length_m=1.2, width_m=0.6, height_m=0.75, diameter_m=0.04, mesh_size_m=0.05),
        "bolt": dict(length_m=0.08, diameter_m=0.01, mesh_size_m=0.01),
        "screw": dict(length_m=0.06, diameter_m=0.006, mesh_size_m=0.01),
        "nut": dict(length_m=0.02, diameter_m=0.014, mesh_size_m=0.005),
    }
    return ExampleInputs(template=template, **common, **dimensions[template])


def main() -> None:
    paths = get_paths("model_material_matrix")
    jobname = "model_material_matrix"
    mapdl = None
    rows = []
    try:
        mapdl = launch_session(paths.mapdl_executable, paths.run_root, jobname)
        for template in ("cantilever", "table", "bolt", "screw", "nut"):
            for material in MATERIAL_NAMES:
                inputs = _input_for(template, material)
                safe_material_name = material.lower().replace(" ", "_").replace("-", "_")
                output_dir = paths.output_root / "model_material_matrix" / template / safe_material_name
                result = (
                    solve_cantilever(mapdl, inputs, output_dir)
                    if template == "cantilever"
                    else solve_example(mapdl, inputs, output_dir)
                )
                numeric = (
                    result.maximum_stress_pa,
                    result.maximum_displacement_m,
                    result.safety_factor,
                )
                if not all(value is not None and math.isfinite(value) and value >= 0 for value in numeric):
                    raise AssertionError(f"Invalid result for {template} / {material}")
                if result.material != material or result.youngs_modulus_pa != inputs.youngs_modulus_pa:
                    raise AssertionError(f"Material card mismatch for {template} / {material}")
                rows.append({
                    "template": template,
                    "material": material,
                    "maximum_stress_pa": result.maximum_stress_pa,
                    "maximum_displacement_m": result.maximum_displacement_m,
                    "safety_factor": result.safety_factor,
                    "status": "passed",
                })
                print(f"PASS {template} / {material}")
    finally:
        if mapdl is not None:
            close_session(mapdl, jobname)

    report = paths.output_root / "model_material_matrix" / "verification.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(f"PASS: {len(rows)} template/material combinations")
    print(f"Acceptance report: {report}")


if __name__ == "__main__":
    main()
