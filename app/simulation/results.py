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

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def write_result_files(result: SimulationResult, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = result.as_dict()
    with (output_dir / "results.json").open("w", encoding="utf-8") as stream:
        json.dump(payload, stream, indent=2)

    with (output_dir / "results.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(payload))
        writer.writeheader()
        writer.writerow(payload)
