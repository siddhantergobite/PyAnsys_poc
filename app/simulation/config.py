"""Central configuration for the first, fixed-template PoC."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .materials import get_material


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MAPDL_EXECUTABLE = Path(
    r"D:\ANSYS Inc\ANSYS Student\v261\ansys\bin\winx64\MAPDL.exe"
)
DEFAULT_RUN_ROOT = Path(r"D:\AnsysProjects\pyansys-poc\mapdl_runs")


@dataclass(frozen=True)
class CantileverInputs:
    """Validated inputs for the first structural template.

    Units are SI: metres, kilograms, seconds, Newtons, and Pascals.
    """

    case_id: str = "single_1000N"
    force_n: float = 1000.0
    length_m: float = 1.0
    width_m: float = 0.1
    height_m: float = 0.1
    material: str = "Structural Steel"
    youngs_modulus_pa: float | None = None
    poissons_ratio: float | None = None
    density_kg_m3: float | None = None
    yield_strength_pa: float | None = None
    strength_basis: str | None = None
    material_model_note: str | None = None
    mesh_size_m: float = 0.05

    def __post_init__(self) -> None:
        card = get_material(self.material)
        defaults = {
            "youngs_modulus_pa": card.youngs_modulus_pa,
            "poissons_ratio": card.poissons_ratio,
            "density_kg_m3": card.density_kg_m3,
            "yield_strength_pa": card.reference_strength_pa,
            "strength_basis": card.strength_basis,
            "material_model_note": card.model_note,
        }
        for field_name, value in defaults.items():
            if getattr(self, field_name) is None:
                object.__setattr__(self, field_name, value)

    def validate(self) -> None:
        if self.force_n <= 0:
            raise ValueError("force_n must be greater than zero")
        if self.length_m <= 0 or self.width_m <= 0 or self.height_m <= 0:
            raise ValueError("length_m, width_m, and height_m must be positive")
        if self.mesh_size_m <= 0:
            raise ValueError("mesh_size_m must be positive")
        if self.poissons_ratio is None or not 0 < self.poissons_ratio < 0.5:
            raise ValueError("poissons_ratio must be between 0 and 0.5")
        if (
            self.youngs_modulus_pa is None
            or self.yield_strength_pa is None
            or self.density_kg_m3 is None
            or self.youngs_modulus_pa <= 0
            or self.yield_strength_pa <= 0
            or self.density_kg_m3 <= 0
        ):
            raise ValueError("material properties must be positive")


@dataclass(frozen=True)
class ProjectPaths:
    project_root: Path
    output_root: Path
    run_root: Path
    mapdl_executable: Path


def get_paths(run_name: str) -> ProjectPaths:
    """Return paths and create only the requested run directory."""

    executable = Path(os.getenv("PYANSYS_MAPDL_EXECUTABLE", DEFAULT_MAPDL_EXECUTABLE))
    run_root = Path(os.getenv("PYANSYS_MAPDL_RUN_ROOT", DEFAULT_RUN_ROOT))
    output_root = PROJECT_ROOT / "output"
    run_dir = run_root / run_name
    run_dir.mkdir(parents=True, exist_ok=True)
    output_root.mkdir(parents=True, exist_ok=True)
    return ProjectPaths(
        project_root=PROJECT_ROOT,
        output_root=output_root,
        run_root=run_dir,
        mapdl_executable=executable,
    )


def default_inputs(case_id: str = "single_1000N", force_n: float = 1000.0) -> CantileverInputs:
    """Create the approved first-template input set."""

    inputs = CantileverInputs(case_id=case_id, force_n=float(force_n))
    inputs.validate()
    return inputs
