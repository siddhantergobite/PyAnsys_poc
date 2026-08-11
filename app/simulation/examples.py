"""Small, bounded MAPDL example templates beyond the mandatory cantilever.

These examples are intentionally simple engineering abstractions. They prove
that the API can select a model template and update values; they are not a
replacement for validated CAD/contact models of real products.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import pi
from pathlib import Path

from .cantilever import _beam_max_bending_stress, _export_images, _finite_max
from .materials import get_material
from .results import SimulationResult


TEMPLATE_DEFINITIONS = {
    "table": {
        "name": "Table frame",
        "description": "Four-leg table frame with a centre top load",
        "stress_method": "BEAM188 section bending stress",
    },
    "bolt": {
        "name": "Bolt",
        "description": "Simplified solid shank under axial tension",
        "stress_method": "Axial force divided by shank area",
    },
    "screw": {
        "name": "Screw",
        "description": "Simplified solid shank under axial tension",
        "stress_method": "Axial force divided by shank area",
    },
    "nut": {
        "name": "Nut",
        "description": "Simplified annular nut section under axial compression",
        "stress_method": "Axial force divided by annular area",
    },
}


@dataclass(frozen=True)
class ExampleInputs:
    template: str
    case_id: str = "example_case"
    force_n: float = 1000.0
    length_m: float = 0.08
    width_m: float = 0.6
    height_m: float = 0.75
    diameter_m: float = 0.01
    mesh_size_m: float = 0.01
    material: str = "Structural Steel"
    youngs_modulus_pa: float | None = None
    poissons_ratio: float | None = None
    density_kg_m3: float | None = None
    yield_strength_pa: float | None = None
    strength_basis: str | None = None
    material_model_note: str | None = None

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
        if self.template not in TEMPLATE_DEFINITIONS:
            raise ValueError(f"Unsupported example template: {self.template}")
        if self.force_n <= 0:
            raise ValueError("force_n must be greater than zero")
        if self.length_m <= 0 or self.mesh_size_m <= 0:
            raise ValueError("length_m and mesh_size_m must be positive")
        if self.width_m <= 0 or self.height_m <= 0 or self.diameter_m <= 0:
            raise ValueError("width_m, height_m, and diameter_m must be positive")
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
        if self.template == "table" and self.height_m <= self.diameter_m:
            raise ValueError("table leg height must be greater than leg diameter")


def _configure_beam(mapdl, inputs: ExampleInputs) -> None:
    mapdl.clear()
    mapdl.prep7()
    mapdl.et(1, 188)
    mapdl.keyopt(1, 4, 1)
    mapdl.keyopt(1, 6, 1)
    mapdl.mp("EX", 1, inputs.youngs_modulus_pa)
    mapdl.mp("PRXY", 1, inputs.poissons_ratio)
    mapdl.mp("DENS", 1, inputs.density_kg_m3)


def _finish_and_solve(mapdl, inputs: ExampleInputs) -> None:
    mapdl.allsel("ALL")
    mapdl.finish()
    mapdl.run("/SOLU")
    mapdl.antype("STATIC")
    mapdl.solve()
    mapdl.finish()
    mapdl.post1()
    mapdl.set("LAST")


def _build_table(mapdl, inputs: ExampleInputs) -> None:
    _configure_beam(mapdl, inputs)
    mapdl.sectype(1, "BEAM", "CSOLID")
    mapdl.secdata(inputs.diameter_m / 2.0)

    length = inputs.width_m if inputs.width_m > 0 else 0.6
    depth = inputs.height_m
    half_l = inputs.length_m / 2.0
    half_w = length / 2.0
    # Four bottom corners, four top corners, and a top-centre load point.
    points = {
        1: (-half_l, -half_w, 0.0), 2: (half_l, -half_w, 0.0),
        3: (half_l, half_w, 0.0), 4: (-half_l, half_w, 0.0),
        5: (-half_l, -half_w, depth), 6: (half_l, -half_w, depth),
        7: (half_l, half_w, depth), 8: (-half_l, half_w, depth),
        9: (0.0, 0.0, depth),
    }
    for keypoint, coords in points.items():
        mapdl.k(keypoint, *coords)

    lines = [
        (1, 5), (2, 6), (3, 7), (4, 8),
        (5, 6), (6, 7), (7, 8), (8, 5),
        (5, 9), (6, 9), (7, 9), (8, 9),
    ]
    for start, end in lines:
        mapdl.l(start, end)
    mapdl.lesize("ALL", inputs.mesh_size_m)
    mapdl.lmesh("ALL")

    mapdl.nsel("S", "LOC", "Z", 0.0)
    mapdl.d("ALL", "ALL", 0.0)
    mapdl.nsel("S", "LOC", "Z", depth)
    mapdl.nsel("R", "LOC", "X", 0.0)
    mapdl.nsel("R", "LOC", "Y", 0.0)
    mapdl.f("ALL", "FZ", -inputs.force_n)
    _finish_and_solve(mapdl, inputs)


def _build_axial(mapdl, inputs: ExampleInputs, tube: bool = False) -> None:
    _configure_beam(mapdl, inputs)
    if tube:
        outer_radius = inputs.diameter_m / 2.0
        inner_radius = outer_radius * 0.55
        mapdl.sectype(1, "BEAM", "CTUBE")
        # CTUBE expects inner radius, outer radius, and circumferential
        # integration divisions (Ri, Ro, N), in that order.
        mapdl.secdata(inner_radius, outer_radius, 12)
    else:
        mapdl.sectype(1, "BEAM", "CSOLID")
        mapdl.secdata(inputs.diameter_m / 2.0)

    mapdl.k(1, 0.0, 0.0, 0.0)
    mapdl.k(2, inputs.length_m, 0.0, 0.0)
    mapdl.l(1, 2)
    mapdl.lesize("ALL", min(inputs.mesh_size_m, inputs.length_m / 4.0))
    mapdl.lmesh("ALL")

    mapdl.nsel("S", "LOC", "X", 0.0)
    mapdl.d("ALL", "ALL", 0.0)
    mapdl.nsel("S", "LOC", "X", inputs.length_m)
    direction = "FX" if inputs.template in {"bolt", "screw"} else "FX"
    mapdl.f("ALL", direction, inputs.force_n if inputs.template != "nut" else -inputs.force_n)
    _finish_and_solve(mapdl, inputs)


def _axial_stress(inputs: ExampleInputs) -> float:
    if inputs.template == "nut":
        outer = inputs.diameter_m / 2.0
        inner = outer * 0.55
        area = pi * (outer**2 - inner**2)
    else:
        area = pi * (inputs.diameter_m / 2.0) ** 2
    return inputs.force_n / area


def solve_example(mapdl, inputs: ExampleInputs, output_dir: Path) -> SimulationResult:
    """Solve one bounded table/bolt/screw/nut example with MAPDL."""

    inputs.validate()
    if inputs.template == "table":
        _build_table(mapdl, inputs)
        maximum_stress = _beam_max_bending_stress(mapdl)
        stress_method = TEMPLATE_DEFINITIONS[inputs.template]["stress_method"]
    else:
        _build_axial(mapdl, inputs, tube=inputs.template == "nut")
        maximum_stress = _axial_stress(inputs)
        stress_method = TEMPLATE_DEFINITIONS[inputs.template]["stress_method"]

    maximum_displacement = _finite_max(
        mapdl.post_processing.nodal_displacement("NORM"), "displacement"
    )
    safety_factor = inputs.yield_strength_pa / maximum_stress if maximum_stress > 0 else None
    stress_image, displacement_image = _export_images(mapdl, output_dir)
    return SimulationResult(
        case_id=inputs.case_id,
        force_n=inputs.force_n,
        material=inputs.material,
        beam_length_m=inputs.length_m,
        beam_width_m=inputs.width_m,
        beam_height_m=inputs.height_m,
        maximum_stress_pa=maximum_stress,
        maximum_displacement_m=maximum_displacement,
        safety_factor=safety_factor,
        status="completed",
        youngs_modulus_pa=inputs.youngs_modulus_pa,
        poissons_ratio=inputs.poissons_ratio,
        density_kg_m3=inputs.density_kg_m3,
        reference_strength_pa=inputs.yield_strength_pa,
        strength_basis=inputs.strength_basis or "reference strength",
        material_model_note=inputs.material_model_note or "",
        stress_image=stress_image,
        displacement_image=displacement_image,
        template=inputs.template,
        stress_method=stress_method,
        diameter_m=inputs.diameter_m,
    )
