"""Run and verify the approved material cards against beam references.

This is an acceptance test for the exact bounded 1000 N cantilever PoC.  It
does not certify arbitrary grades, geometries, nonlinear response, or failure.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.simulation.cantilever import solve_cantilever  # noqa: E402
from app.simulation.config import CantileverInputs, get_paths  # noqa: E402
from app.simulation.mapdl_session import close_session, launch_session  # noqa: E402
from app.simulation.materials import MATERIAL_NAMES  # noqa: E402
from app.simulation.results import write_result_files  # noqa: E402


STRESS_TOLERANCE_PERCENT = 5.0
DISPLACEMENT_TOLERANCE_PERCENT = 3.0


def reference_values(inputs: CantileverInputs) -> tuple[float, float]:
    """Return Euler-Bernoulli tip-load stress and displacement references."""

    inertia = inputs.width_m * inputs.height_m**3 / 12.0
    stress = inputs.force_n * inputs.length_m * (inputs.height_m / 2.0) / inertia
    displacement = (
        inputs.force_n
        * inputs.length_m**3
        / (3.0 * inputs.youngs_modulus_pa * inertia)
    )
    return stress, displacement


def percent_error(actual: float, expected: float) -> float:
    return abs(actual - expected) / expected * 100.0


def main() -> None:
    paths = get_paths("material_verification")
    output_root = paths.output_root / "material_verification"
    jobname = "material_matrix"
    mapdl = None
    rows: list[dict] = []
    failures: list[str] = []

    try:
        print("Launching one clean MAPDL session for five controlled material runs...")
        mapdl = launch_session(paths.mapdl_executable, paths.run_root, jobname)
        for index, material in enumerate(MATERIAL_NAMES, start=1):
            slug = material.lower().replace(" ", "_").replace("-", "_")
            inputs = CantileverInputs(
                case_id=f"material_{index}",
                material=material,
                force_n=1000.0,
                length_m=1.0,
                width_m=0.1,
                height_m=0.1,
                mesh_size_m=0.05,
            )
            inputs.validate()
            output_dir = output_root / slug
            print(f"[{index}/{len(MATERIAL_NAMES)}] Solving {material}...")
            result = solve_cantilever(mapdl, inputs, output_dir)
            write_result_files(result, output_dir)

            expected_stress, expected_displacement = reference_values(inputs)
            stress_error = percent_error(result.maximum_stress_pa, expected_stress)
            displacement_error = percent_error(
                result.maximum_displacement_m, expected_displacement
            )
            expected_factor = inputs.yield_strength_pa / result.maximum_stress_pa
            factor_error = abs(result.safety_factor - expected_factor)
            files_ok = all(
                (output_dir / filename).is_file()
                and (output_dir / filename).stat().st_size > 0
                for filename in (
                    "results.csv",
                    "results.json",
                    "stress.png",
                    "deformation.png",
                )
            )
            passed = (
                stress_error <= STRESS_TOLERANCE_PERCENT
                and displacement_error <= DISPLACEMENT_TOLERANCE_PERCENT
                and factor_error <= 1.0e-12
                and files_ok
            )
            if not passed:
                failures.append(material)

            rows.append(
                {
                    "material": material,
                    "youngs_modulus_gpa": inputs.youngs_modulus_pa / 1.0e9,
                    "density_kg_m3": inputs.density_kg_m3,
                    "reference_strength_mpa": inputs.yield_strength_pa / 1.0e6,
                    "strength_basis": inputs.strength_basis,
                    "mapdl_stress_mpa": result.maximum_stress_pa / 1.0e6,
                    "reference_stress_mpa": expected_stress / 1.0e6,
                    "stress_error_percent": stress_error,
                    "mapdl_displacement_mm": result.maximum_displacement_m * 1.0e3,
                    "reference_displacement_mm": expected_displacement * 1.0e3,
                    "displacement_error_percent": displacement_error,
                    "safety_factor": result.safety_factor,
                    "artifacts_ok": files_ok,
                    "status": "PASS" if passed else "FAIL",
                }
            )
            print(
                f"    stress={rows[-1]['mapdl_stress_mpa']:.4f} MPa, "
                f"displacement={rows[-1]['mapdl_displacement_mm']:.4f} mm, "
                f"factor={result.safety_factor:.3f}, "
                f"status={rows[-1]['status']}"
            )
    finally:
        if mapdl is not None:
            close_session(mapdl, jobname)

    summary_path = output_root / "verification.csv"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with summary_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    print(f"Verification summary: {summary_path}")
    if failures:
        raise SystemExit(f"Material verification failed: {', '.join(failures)}")
    print("PASS: all five bounded material cards matched the acceptance checks.")


if __name__ == "__main__":
    main()
