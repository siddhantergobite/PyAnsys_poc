"""Result model and CSV/JSON export for the PoC."""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass, field
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
    load_value: float | None = None
    load_type: str = "force"
    load_unit: str = "N"
    youngs_modulus_pa: float | None = None
    poissons_ratio: float | None = None
    density_kg_m3: float | None = None
    reference_strength_pa: float | None = None
    strength_basis: str = "yield strength"
    material_model_note: str = ""
    material_source_url: str = ""
    material_data_origin: str = "application_catalog_external_reference"
    stress_image: str = ""
    displacement_image: str = ""
    failure_assessment_image: str = ""
    sweep_image: str = ""
    model_definition_file: str = ""
    mapdl_database_file: str = ""
    template: str = "cantilever"
    model_provenance: str = "custom_parameterized_model"
    element_type: str = ""
    official_source_url: str = ""
    stress_method: str = "solver"
    diameter_m: float | None = None
    force_start_n: float | None = None
    force_end_n: float | None = None
    force_increment_n: float | None = None
    force_steps: int | None = None
    break_force_n: float | None = None
    threshold_load_value: float | None = None
    threshold_load_unit: str = "N"
    break_status: str = "not_evaluated"
    force_curve: list[dict[str, Any]] | None = None
    failure_status: str = "not_evaluated"
    breakage_assessment: str = "not_determinable"
    failure_criterion: str = "reference_strength_and_large_deformation_screening"
    stress_utilization: float | None = None
    deformation_ratio: float | None = None
    large_deformation_warning: bool = False
    deformation_reference_length_m: float | None = None
    deformation_limit_ratio: float | None = None
    critical_stress_location: str = "not available"
    critical_displacement_location: str = "not available"
    load_application_location: str = "not available"
    estimated_failure_load_n: float | None = None
    estimated_reference_strength_load_n: float | None = None
    estimated_deformation_limit_load_n: float | None = None
    governing_screening_load_n: float | None = None
    governing_screening_criterion: str = "not available"
    failure_summary: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        # Native MAPDL audit artifacts stay private in the run directory.
        # They are not part of the client-facing result contract.
        payload.pop("model_definition_file", None)
        payload.pop("mapdl_database_file", None)
        if payload["failure_summary"] is None:
            payload["failure_summary"] = []
        return payload


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
                "case_id", "template", "material", "force_n", "load_value", "load_type", "load_unit",
                "maximum_stress_pa", "maximum_displacement_m", "safety_factor",
                "point_status", "force_start_n", "force_end_n", "force_increment_n", "force_steps",
                "break_force_n", "break_status", "reference_strength_pa",
                "threshold_load_value", "threshold_load_unit", "model_provenance",
                "element_type", "official_source_url", "material_source_url",
                "strength_basis", "stress_method", "failure_status",
                "breakage_assessment",
                "stress_utilization", "deformation_ratio",
                "large_deformation_warning",
                "estimated_failure_load_n", "estimated_reference_strength_load_n",
                "estimated_deformation_limit_load_n", "governing_screening_load_n",
                "governing_screening_criterion",
            ]
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            common = {
                "case_id": result.case_id,
                "template": result.template,
                "material": result.material,
                "load_type": result.load_type,
                "load_unit": result.load_unit,
                "force_start_n": result.force_start_n,
                "force_end_n": result.force_end_n,
                "force_increment_n": result.force_increment_n,
                "force_steps": result.force_steps,
                "break_force_n": result.break_force_n,
                "break_status": result.break_status,
                "threshold_load_value": result.threshold_load_value,
                "threshold_load_unit": result.threshold_load_unit,
                "model_provenance": result.model_provenance,
                "element_type": result.element_type,
                "official_source_url": result.official_source_url,
                "material_source_url": result.material_source_url,
                "reference_strength_pa": result.reference_strength_pa,
                "strength_basis": result.strength_basis,
                "stress_method": result.stress_method,
                "failure_status": result.failure_status,
                "breakage_assessment": result.breakage_assessment,
                "stress_utilization": result.stress_utilization,
                "deformation_ratio": result.deformation_ratio,
                "large_deformation_warning": result.large_deformation_warning,
                "estimated_failure_load_n": result.estimated_failure_load_n,
                "estimated_reference_strength_load_n": result.estimated_reference_strength_load_n,
                "estimated_deformation_limit_load_n": result.estimated_deformation_limit_load_n,
                "governing_screening_load_n": result.governing_screening_load_n,
                "governing_screening_criterion": result.governing_screening_criterion,
            }
            for point in result.force_curve:
                writer.writerow({**common, **point})
        else:
            writer = csv.DictWriter(stream, fieldnames=list(payload))
            writer.writeheader()
            writer.writerow(payload)
