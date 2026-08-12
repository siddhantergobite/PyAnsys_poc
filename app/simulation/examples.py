"""Small, bounded MAPDL example templates beyond the mandatory cantilever.

These examples are intentionally simple engineering abstractions. They prove
that the API can select a model template and update values; they are not a
replacement for validated CAD/contact models of real products.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import pi
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import colors
from matplotlib.patches import Rectangle

from .cantilever import _beam_bending_stress_values, _finite_max
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


def _reference_threshold_force(inputs: ExampleInputs, maximum_stress: float) -> float | None:
    """Estimate the force at the material reference strength.

    The extension templates are linear-elastic PoC abstractions, so this is a
    reference-strength threshold rather than a physical break prediction.
    """

    if maximum_stress <= 0 or inputs.yield_strength_pa is None:
        return None
    return inputs.force_n * inputs.yield_strength_pa / maximum_stress


def _export_axial_images(
    mapdl,
    inputs: ExampleInputs,
    output_dir: Path,
    axial_stress_pa: float,
) -> tuple[str, str]:
    """Create readable reports for the simplified shank model.

    The shank is a one-dimensional BEAM188 abstraction: the stress display is
    the template's uniform force/area result and the displacement line is read
    from the MAPDL solution. It deliberately does not pretend to show threads,
    bolt heads, nut contact, or a real product CAD contour.
    """

    output_dir.mkdir(parents=True, exist_ok=True)
    stress_path = output_dir / "stress.png"
    deformation_path = output_dir / "deformation.png"
    nodes = np.asarray(mapdl.mesh.nodes, dtype=float)
    x_coordinates = nodes[:, 0]
    axial_displacements_m = np.asarray(
        mapdl.post_processing.nodal_displacement("X"), dtype=float
    )
    order = np.argsort(x_coordinates)
    x_coordinates = x_coordinates[order]
    axial_displacements_m = axial_displacements_m[order]
    diameter = inputs.diameter_m
    stress_mpa = axial_stress_pa / 1e6
    colour_map = plt.get_cmap("turbo")
    normaliser = colors.Normalize(vmin=0.0, vmax=max(stress_mpa, 1e-9))

    figure, axis = plt.subplots(figsize=(10, 3.6))
    axis.add_patch(
        Rectangle(
            (0.0, -diameter / 2.0),
            inputs.length_m,
            diameter,
            facecolor=colour_map(normaliser(stress_mpa)),
            edgecolor="#163b60",
            linewidth=1.8,
        )
    )
    axis.axvline(0.0, color="#163b60", linewidth=5, alpha=0.8)
    axis.annotate(
        "Fixed support",
        xy=(0.0, -diameter / 2.0),
        xytext=(0.02 * inputs.length_m, -1.8 * diameter),
        arrowprops={"arrowstyle": "->", "color": "#163b60"},
        color="#163b60",
    )
    axis.annotate(
        f"Uniform section stress = {stress_mpa:.3f} MPa",
        xy=(inputs.length_m * 0.52, 0.0),
        ha="center",
        va="center",
        fontsize=12,
        fontweight="bold",
        color="#132f4c",
    )
    axis.set_title(
        f"MAPDL simplified {TEMPLATE_DEFINITIONS[inputs.template]['name']} shank stress",
        fontweight="bold",
    )
    axis.set_xlabel("Shank position (m)")
    axis.set_ylabel("Shank diameter (m)")
    axis.set_xlim(-0.06 * inputs.length_m, 1.06 * inputs.length_m)
    axis.set_ylim(-1.45 * diameter, 1.2 * diameter)
    axis.set_aspect("equal", adjustable="box")
    axis.grid(alpha=0.2)
    scalar_map = plt.cm.ScalarMappable(norm=normaliser, cmap=colour_map)
    scalar_map.set_array([])
    colour_bar = figure.colorbar(scalar_map, ax=axis, pad=0.02)
    colour_bar.set_label("Section stress (MPa)")
    figure.text(
        0.5,
        0.01,
        "PoC axial shank abstraction - no threads, head geometry, or contact model.",
        ha="center",
        color="#52677d",
        fontsize=9,
    )
    figure.tight_layout(rect=(0, 0.05, 1, 1))
    figure.savefig(stress_path, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(figure)

    displacement_mm = axial_displacements_m * 1e3
    figure, axis = plt.subplots(figsize=(10, 4.2))
    points = axis.scatter(
        x_coordinates,
        displacement_mm,
        c=np.abs(displacement_mm),
        cmap="turbo",
        s=55,
        zorder=3,
    )
    axis.plot(x_coordinates, displacement_mm, color="#315f89", linewidth=2.2)
    axis.scatter(
        [x_coordinates[0]],
        [displacement_mm[0]],
        marker="s",
        s=85,
        color="#163b60",
        label="Fixed support",
        zorder=4,
    )
    axis.annotate(
        f"Maximum = {np.max(np.abs(displacement_mm)):.4f} mm",
        xy=(x_coordinates[-1], displacement_mm[-1]),
        xytext=(-130, 18),
        textcoords="offset points",
        arrowprops={"arrowstyle": "->", "color": "#163b60"},
        color="#163b60",
        fontweight="bold",
    )
    axis.set_title(
        f"MAPDL nodal axial displacement - {TEMPLATE_DEFINITIONS[inputs.template]['name']}",
        fontweight="bold",
    )
    axis.set_xlabel("Shank position (m)")
    axis.set_ylabel("Axial displacement (mm)")
    axis.grid(alpha=0.25)
    axis.legend(loc="best")
    colour_bar = figure.colorbar(points, ax=axis, pad=0.02)
    colour_bar.set_label("Absolute displacement (mm)")
    figure.tight_layout()
    figure.savefig(deformation_path, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(figure)
    return stress_path.name, deformation_path.name


def _export_table_images(
    mapdl,
    inputs: ExampleInputs,
    output_dir: Path,
    stress_values_pa: np.ndarray,
) -> tuple[str, str]:
    """Create solver-derived reports for the simplified four-leg table frame."""

    output_dir.mkdir(parents=True, exist_ok=True)
    stress_path = output_dir / "stress.png"
    deformation_path = output_dir / "deformation.png"
    stress_mpa = np.asarray(stress_values_pa, dtype=float) / 1e6
    nodes = np.asarray(mapdl.mesh.nodes, dtype=float)
    displacement_mm = np.asarray(
        mapdl.post_processing.nodal_displacement("NORM"), dtype=float
    ) * 1e3

    figure, axis = plt.subplots(figsize=(11, 4.5))
    element_index = np.arange(1, len(stress_mpa) + 1)
    bars = axis.bar(element_index, stress_mpa, color=plt.get_cmap("turbo")(colors.Normalize(
        vmin=0.0, vmax=max(float(np.max(stress_mpa)), 1e-9)
    )(stress_mpa)))
    if len(stress_mpa):
        maximum_index = int(np.argmax(stress_mpa))
        bars[maximum_index].set_edgecolor("#9a321f")
        bars[maximum_index].set_linewidth(2)
        axis.annotate(
            f"Maximum = {stress_mpa[maximum_index]:.3f} MPa",
            xy=(element_index[maximum_index], stress_mpa[maximum_index]),
            xytext=(0, 12),
            textcoords="offset points",
            ha="center",
            color="#163b60",
            fontweight="bold",
        )
    axis.set_title("MAPDL simplified table-frame BEAM188 stress by element", fontweight="bold")
    axis.set_xlabel("BEAM188 element sequence")
    axis.set_ylabel("Extreme-fibre bending stress (MPa)")
    axis.grid(axis="y", alpha=0.25)
    figure.text(
        0.5,
        0.01,
        "Direct BEAM188 section stress; this is a frame model, not a solid or joint-contact contour.",
        ha="center",
        color="#52677d",
        fontsize=9,
    )
    figure.tight_layout(rect=(0, 0.05, 1, 1))
    figure.savefig(stress_path, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(figure)

    figure = plt.figure(figsize=(8.8, 6.4))
    axis = figure.add_subplot(111, projection="3d")
    points = axis.scatter(
        nodes[:, 0],
        nodes[:, 1],
        nodes[:, 2],
        c=displacement_mm,
        cmap="turbo",
        s=34,
        depthshade=False,
    )
    axis.scatter(
        nodes[:, 0],
        nodes[:, 1],
        np.zeros(len(nodes)),
        marker="s",
        color="#163b60",
        s=26,
        alpha=0.5,
        label="Support level",
    )
    axis.set_title("MAPDL simplified table-frame nodal displacement", fontweight="bold")
    axis.set_xlabel("X (m)")
    axis.set_ylabel("Y (m)")
    axis.set_zlabel("Z (m)")
    axis.legend(loc="upper left")
    colour_bar = figure.colorbar(points, ax=axis, shrink=0.72, pad=0.08)
    colour_bar.set_label("Nodal displacement magnitude (mm)")
    figure.text(
        0.5,
        0.02,
        f"Maximum MAPDL nodal displacement = {np.max(displacement_mm):.4f} mm",
        ha="center",
        color="#163b60",
        fontweight="bold",
    )
    figure.tight_layout(rect=(0, 0.05, 1, 1))
    figure.savefig(deformation_path, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(figure)
    return stress_path.name, deformation_path.name


def solve_example(mapdl, inputs: ExampleInputs, output_dir: Path) -> SimulationResult:
    """Solve one bounded table/bolt/screw/nut example with MAPDL."""

    inputs.validate()
    if inputs.template == "table":
        _build_table(mapdl, inputs)
        stress_values = _beam_bending_stress_values(mapdl)
        maximum_stress = _finite_max(stress_values, "table beam stress")
        stress_method = TEMPLATE_DEFINITIONS[inputs.template]["stress_method"]
        stress_image, displacement_image = _export_table_images(
            mapdl, inputs, output_dir, stress_values
        )
    else:
        _build_axial(mapdl, inputs, tube=inputs.template == "nut")
        maximum_stress = _axial_stress(inputs)
        stress_method = TEMPLATE_DEFINITIONS[inputs.template]["stress_method"]
        stress_image, displacement_image = _export_axial_images(
            mapdl, inputs, output_dir, maximum_stress
        )

    maximum_displacement = _finite_max(
        mapdl.post_processing.nodal_displacement("NORM"), "displacement"
    )
    safety_factor = inputs.yield_strength_pa / maximum_stress if maximum_stress > 0 else None
    threshold_force_n = _reference_threshold_force(inputs, maximum_stress)
    threshold_status = (
        "threshold_reached"
        if threshold_force_n is not None and maximum_stress >= inputs.yield_strength_pa
        else "threshold_estimated"
        if threshold_force_n is not None
        else "not_evaluated"
    )
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
        break_force_n=threshold_force_n,
        break_status=threshold_status,
    )
