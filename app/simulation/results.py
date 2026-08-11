"""Result model and CSV/JSON export for the PoC."""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass
class SimulationResult:
    case_id: str
    force_n: float
    material: str
    beam_length_m: float
    beam_width_m: float
    beam_height_m: float
    maximum_stress_pa: float
    maximum_displacement_m: float
    safety_factor: float | None
    status: str
    youngs_modulus_pa: float | None = None
    poissons_ratio: float | None = None
    density_kg_m3: float | None = None
    reference_strength_pa: float | None = None
    strength_basis: str = "yield strength"
    material_model_note: str = ""
    stress_image: str = ""
    displacement_image: str = ""
    template: str = "cantilever"
    stress_method: str = "solver"
    diameter_m: float | None = None
    force_start_n: float | None = None
    force_end_n: float | None = None
    force_steps: int | None = None
    break_force_n: float | None = None
    break_status: str = "not_evaluated"
    force_curve: list[dict[str, Any]] | None = None
    sweep_image: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def write_result_files(result: SimulationResult, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = result.as_dict()
    with (output_dir / "results.json").open("w", encoding="utf-8") as stream:
        json.dump(payload, stream, indent=2)

    with (output_dir / "results.csv").open("w", newline="", encoding="utf-8") as stream:
        if result.force_curve:
            # A range run is useful only when each force point is visible in
            # Excel/CSV. Keep the shared run metadata with every point.
            fields = [
                "case_id", "template", "material", "force_n",
                "maximum_stress_pa", "maximum_displacement_m", "safety_factor",
                "point_status", "force_start_n", "force_end_n", "force_steps",
                "break_force_n", "break_status", "reference_strength_pa",
                "strength_basis", "stress_method",
            ]
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            common = {
                "case_id": result.case_id,
                "template": result.template,
                "material": result.material,
                "force_start_n": result.force_start_n,
                "force_end_n": result.force_end_n,
                "force_steps": result.force_steps,
                "break_force_n": result.break_force_n,
                "break_status": result.break_status,
                "reference_strength_pa": result.reference_strength_pa,
                "strength_basis": result.strength_basis,
                "stress_method": result.stress_method,
            }
            for point in result.force_curve:
                writer.writerow({**common, **point})
        else:
            writer = csv.DictWriter(stream, fieldnames=list(payload))
            writer.writeheader()
            writer.writerow(payload)
