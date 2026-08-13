"""Parameterized adaptations of official Ansys PyMAPDL structural examples.

The original MIT-licensed sources are archived under ``examples/official_ansys``.
This module preserves their documented element formulations and modelling
approach while exposing controlled SI parameters to this application's API.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from math import pi
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.tri import Triangulation

from .assessment import (
    FailureAssessment,
    assess_failure,
    export_failure_assessment_image,
    export_force_sweep_image,
)
from .cantilever import _estimate_linear_threshold_force, _first_strength_crossing
from .config import ForceRange
from .materials import get_material
from .results import SimulationResult


OFFICIAL_TEMPLATE_DEFINITIONS = {
    "corner_bracket": {
        "name": "Ansys corner bracket",
        "description": "Official PyMAPDL corner-bracket example adapted to controlled SI inputs",
        "provenance": "official_ansys_example_adaptation",
        "element_type": "PLANE183",
        "stress_method": "MAPDL PLANE183 nodal equivalent (von Mises) stress",
        "source_url": "https://mapdl.docs.pyansys.com/version/stable/examples/gallery_examples/00-mapdl-examples/bracket_static.html",
    },
    "plate_hole": {
        "name": "Ansys plate with a hole",
        "description": "Official PyMAPDL stress-concentration example adapted to controlled SI inputs",
        "provenance": "official_ansys_example_adaptation",
        "element_type": "PLANE183",
        "stress_method": "MAPDL PLANE183 nodal equivalent (von Mises) stress",
        "source_url": "https://mapdl.docs.pyansys.com/version/stable/examples/gallery_examples/00-mapdl-examples/2d_plate_with_a_hole.html",
    },
    "pressure_vessel": {
        "name": "Ansys pressure vessel",
        "description": "Official PyMAPDL plane-strain pressure-vessel example adapted to controlled SI inputs",
        "provenance": "official_ansys_example_adaptation",
        "element_type": "PLANE182",
        "stress_method": "MAPDL PLANE182 nodal equivalent (von Mises) stress",
        "source_url": "https://mapdl.docs.pyansys.com/version/stable/examples/gallery_examples/00-mapdl-examples/2d_pressure_vessel.html",
    },
}


@dataclass(frozen=True)
class OfficialExampleInputs:
    template: str
    case_id: str = "official_example"
    load_value: float = 1000.0
    length_m: float = 0.4
    width_m: float = 0.1
    thickness_m: float = 0.01
    feature_diameter_m: float = 0.03
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

    @property
    def load_unit(self) -> str:
        return "Pa" if self.template == "pressure_vessel" else "N"

    @property
    def load_label(self) -> str:
        if self.template == "pressure_vessel":
            return "internal pressure"
        if self.template == "corner_bracket":
            return "resultant pin-hole load"
        return "tensile force"

    def validate(self) -> None:
        if self.template not in OFFICIAL_TEMPLATE_DEFINITIONS:
            raise ValueError(f"Unsupported official example template: {self.template}")
        values = (
            self.load_value,
            self.length_m,
            self.width_m,
            self.thickness_m,
            self.feature_diameter_m,
            self.mesh_size_m,
        )
        if any(value <= 0 for value in values):
            raise ValueError("load, dimensions, feature diameter, and mesh size must be positive")
        if self.template in {"corner_bracket", "plate_hole"} and self.feature_diameter_m >= self.width_m:
            raise ValueError("hole diameter must be smaller than model width")
        if self.template == "corner_bracket" and self.length_m <= 2.5 * self.width_m:
            raise ValueError("corner-bracket length must exceed 2.5 times its width")
        if self.template == "pressure_vessel" and self.width_m <= self.length_m:
            raise ValueError("pressure-vessel outer radius must exceed inner radius")
        if self.poissons_ratio is None or not 0 < self.poissons_ratio < 0.5:
            raise ValueError("poissons_ratio must be between 0 and 0.5")


def _configure_plane(mapdl, inputs: OfficialExampleInputs, element: int, keyopt3: int) -> None:
    mapdl.clear()
    mapdl.prep7()
    mapdl.units("SI")
    mapdl.et(1, element, kop3=keyopt3)
    mapdl.mp("EX", 1, inputs.youngs_modulus_pa)
    mapdl.mp("PRXY", 1, inputs.poissons_ratio)
    mapdl.mp("DENS", 1, inputs.density_kg_m3)


def _solve_static(mapdl) -> None:
    mapdl.allsel("ALL")
    mapdl.finish()
    mapdl.run("/SOLU")
    mapdl.antype("STATIC", "NEW")
    mapdl.solve()
    mapdl.finish()
    mapdl.post1()
    mapdl.set("LAST")


def _build_plate_hole(mapdl, inputs: OfficialExampleInputs) -> None:
    _configure_plane(mapdl, inputs, 183, 3)
    mapdl.r(1, inputs.thickness_m)
    plate = mapdl.blc4(width=inputs.length_m, height=inputs.width_m)
    hole = mapdl.cyl4(
        inputs.length_m / 2.0,
        inputs.width_m / 2.0,
        inputs.feature_diameter_m / 2.0,
    )
    area = mapdl.asba(plate, hole)
    mapdl.mopt("EXPND", 0.7)
    mapdl.esize(min(inputs.mesh_size_m, pi * inputs.feature_diameter_m / 32.0))
    mapdl.amesh(area)

    tolerance = max(inputs.mesh_size_m * 0.05, inputs.length_m * 1e-8)
    mapdl.nsel("S", "LOC", "X", -tolerance, tolerance)
    mapdl.d("ALL", "UX", 0.0)
    mapdl.nsel("R", "LOC", "Y", inputs.width_m / 2.0 - tolerance, inputs.width_m / 2.0 + tolerance)
    if mapdl.mesh.n_node < 1:
        raise RuntimeError("Plate support node could not be selected")
    mapdl.d("ALL", "UY", 0.0)
    mapdl.nsel("S", "LOC", "X", inputs.length_m - tolerance, inputs.length_m + tolerance)
    mapdl.cp(5, "UX", "ALL")
    mapdl.nsel("R", "LOC", "Y", inputs.width_m / 2.0 - tolerance, inputs.width_m / 2.0 + tolerance)
    if mapdl.mesh.n_node < 1:
        raise RuntimeError("Plate load node could not be selected")
    mapdl.f("ALL", "FX", inputs.load_value)
    _solve_static(mapdl)


def _build_pressure_vessel(mapdl, inputs: OfficialExampleInputs) -> None:
    _configure_plane(mapdl, inputs, 182, 2)
    inner_radius = inputs.length_m
    outer_radius = inputs.width_m
    mapdl.pcirc(inner_radius, outer_radius, theta1=0, theta2=90)
    mapdl.components["PIPE_PROFILE"] = "AREA"
    mapdl.aesize("ALL", min(inputs.mesh_size_m, (outer_radius - inner_radius) / 3.0))
    mapdl.mshape(0, "2D")
    mapdl.mshkey(1)
    mapdl.cmsel("S", "PIPE_PROFILE")
    mapdl.amesh("ALL")
    tolerance = max(inputs.mesh_size_m * 0.05, outer_radius * 1e-8)
    mapdl.nsel("S", "LOC", "X", -tolerance, tolerance)
    mapdl.components["X_FIXED"] = "NODES"
    mapdl.nsel("S", "LOC", "Y", -tolerance, tolerance)
    mapdl.components["Y_FIXED"] = "NODES"
    mapdl.allsel("ALL")
    mapdl.lsel("S", "RADIUS", vmin=inner_radius - tolerance, vmax=inner_radius + tolerance)
    mapdl.components["PRESSURE_EDGE"] = "LINE"
    mapdl.allsel("ALL")
    mapdl.d("X_FIXED", "UX", 0.0)
    mapdl.d("Y_FIXED", "UY", 0.0)
    mapdl.csys(1)
    mapdl.sfl("PRESSURE_EDGE", "PRES", inputs.load_value)
    _solve_static(mapdl)
    mapdl.csys(0)


def _build_corner_bracket(mapdl, inputs: OfficialExampleInputs) -> None:
    """Create the official tutorial's L-bracket topology in controlled SI units."""

    _configure_plane(mapdl, inputs, 183, 3)
    mapdl.r(1, inputs.thickness_m)
    arm_half_width = inputs.width_m / 2.0
    vertical_length = inputs.length_m * 0.55
    outer_radius = arm_half_width
    hole_radius = inputs.feature_diameter_m / 2.0
    x_end = inputs.length_m - outer_radius
    y_end = -(vertical_length - outer_radius)

    mapdl.rectng(0.0, x_end, -arm_half_width, arm_half_width)
    mapdl.rectng(x_end - 2.0 * arm_half_width, x_end, y_end, -arm_half_width)
    mapdl.cyl4(0.0, 0.0, outer_radius)
    mapdl.cyl4(x_end, y_end, outer_radius)
    mapdl.aadd("ALL")
    bracket_area = int(mapdl.get_value("AREA", 0, "NUM", "MIN"))
    left_hole_area = int(mapdl.cyl4(0.0, 0.0, hole_radius))
    bracket_area = int(mapdl.asba(bracket_area, left_hole_area))
    right_hole_area = int(mapdl.cyl4(x_end, y_end, hole_radius))
    bracket_area = int(mapdl.asba(bracket_area, right_hole_area))
    mapdl.esize(min(inputs.mesh_size_m, hole_radius / 2.0))
    mapdl.amesh(bracket_area)

    nodes = np.asarray(mapdl.mesh.nodes, dtype=float)
    distance_left = np.hypot(nodes[:, 0], nodes[:, 1])
    support_nodes = np.asarray(mapdl.mesh.nnum_all)[np.abs(distance_left - hole_radius) <= max(inputs.mesh_size_m * 0.65, hole_radius * 0.08)]
    if support_nodes.size < 2:
        raise RuntimeError("Corner-bracket support nodes could not be identified")
    mapdl.nsel("NONE")
    for node in support_nodes:
        mapdl.nsel("A", "NODE", vmin=int(node))
    mapdl.d("ALL", "ALL", 0.0)
    mapdl.allsel("ALL")

    distance_right = np.hypot(nodes[:, 0] - x_end, nodes[:, 1] - y_end)
    lower_half = nodes[:, 1] <= y_end + max(inputs.mesh_size_m * 0.1, 1e-9)
    load_nodes = np.asarray(mapdl.mesh.nnum_all)[
        (np.abs(distance_right - hole_radius) <= max(inputs.mesh_size_m * 0.65, hole_radius * 0.08)) & lower_half
    ]
    if load_nodes.size < 2:
        raise RuntimeError("Corner-bracket loaded pin-hole nodes could not be identified")
    node_lookup = {int(number): nodes[index] for index, number in enumerate(np.asarray(mapdl.mesh.nnum_all))}
    load_coordinates = np.asarray([node_lookup[int(node)] for node in load_nodes])
    weights = np.maximum(0.05 * hole_radius, y_end - load_coordinates[:, 1] + 0.05 * hole_radius)
    weights = weights / weights.sum()
    for node, weight in zip(load_nodes, weights):
        mapdl.f(int(node), "FY", -inputs.load_value * float(weight))
    _solve_static(mapdl)


def _build_model(mapdl, inputs: OfficialExampleInputs) -> None:
    if inputs.template == "plate_hole":
        _build_plate_hole(mapdl, inputs)
    elif inputs.template == "pressure_vessel":
        _build_pressure_vessel(mapdl, inputs)
    else:
        _build_corner_bracket(mapdl, inputs)


def _extract_point(mapdl):
    result = mapdl.result
    node_numbers, principal = result.principal_nodal_stress(0)
    equivalent = np.asarray(principal[:, -1], dtype=float)
    displacement_nodes, displacement = result.nodal_displacement(0)
    displacement = np.asarray(displacement, dtype=float)
    displacement_norm = np.linalg.norm(displacement, axis=1)
    finite_stress = np.isfinite(equivalent)
    if not finite_stress.any() or not np.isfinite(displacement_norm).any():
        raise RuntimeError("MAPDL did not return finite stress/displacement results")
    return {
        "stress_nodes": np.asarray(node_numbers),
        "stress": equivalent,
        "displacement_nodes": np.asarray(displacement_nodes),
        "displacement": displacement,
        "displacement_norm": displacement_norm,
        "maximum_stress": float(np.nanmax(equivalent)),
        "maximum_displacement": float(np.nanmax(displacement_norm)),
    }


def _coordinates_for_nodes(mapdl, node_numbers: np.ndarray) -> np.ndarray:
    all_numbers = np.asarray(mapdl.mesh.nnum_all)
    all_coordinates = np.asarray(mapdl.mesh.nodes, dtype=float)
    lookup = {int(number): all_coordinates[index] for index, number in enumerate(all_numbers)}
    return np.asarray([lookup[int(number)] for number in node_numbers], dtype=float)


def _assessment(mapdl, inputs: OfficialExampleInputs, point: dict) -> FailureAssessment:
    stress_index = int(np.nanargmax(point["stress"]))
    displacement_index = int(np.nanargmax(point["displacement_norm"]))
    stress_node = int(point["stress_nodes"][stress_index])
    displacement_node = int(point["displacement_nodes"][displacement_index])
    stress_xyz = _coordinates_for_nodes(mapdl, np.asarray([stress_node]))[0]
    displacement_xyz = _coordinates_for_nodes(mapdl, np.asarray([displacement_node]))[0]
    if inputs.template == "pressure_vessel":
        load_location = f"Uniform internal pressure on radius {inputs.length_m:.6g} m"
        reference_length = inputs.width_m - inputs.length_m
    elif inputs.template == "corner_bracket":
        load_location = "Distributed downward load on the lower half of the right pin hole"
        reference_length = inputs.length_m
    else:
        load_location = "Coupled tensile force on the right plate edge"
        reference_length = inputs.length_m
    return assess_failure(
        force_n=inputs.load_value,
        maximum_stress_pa=point["maximum_stress"],
        reference_strength_pa=inputs.yield_strength_pa,
        maximum_displacement_m=point["maximum_displacement"],
        deformation_reference_length_m=reference_length,
        critical_stress_location=f"MAPDL node {stress_node} near ({stress_xyz[0]:.5g}, {stress_xyz[1]:.5g}) m",
        critical_displacement_location=f"MAPDL node {displacement_node} near ({displacement_xyz[0]:.5g}, {displacement_xyz[1]:.5g}) m",
        load_application_location=load_location,
        load_unit=inputs.load_unit,
    )


def _export_images(mapdl, inputs: OfficialExampleInputs, point: dict, output_dir: Path) -> tuple[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stress_path = output_dir / "stress.png"
    displacement_path = output_dir / "deformation.png"
    stress_xy = _coordinates_for_nodes(mapdl, point["stress_nodes"])[:, :2]
    disp_xyz = _coordinates_for_nodes(mapdl, point["displacement_nodes"])
    stress = point["stress"] / 1e6
    finite = np.isfinite(stress)

    figure, axis = plt.subplots(figsize=(10.5, 6.3))
    triangulation = Triangulation(stress_xy[finite, 0], stress_xy[finite, 1])
    triangles = triangulation.triangles
    vertices = stress_xy[finite][triangles]
    centroids = vertices.mean(axis=1)
    edge_lengths = np.linalg.norm(vertices - np.roll(vertices, 1, axis=1), axis=2)
    if inputs.template == "plate_hole":
        radius = inputs.feature_diameter_m / 2.0
        inside = (
            (centroids[:, 0] >= 0)
            & (centroids[:, 0] <= inputs.length_m)
            & (centroids[:, 1] >= 0)
            & (centroids[:, 1] <= inputs.width_m)
            & (np.hypot(centroids[:, 0] - inputs.length_m / 2.0, centroids[:, 1] - inputs.width_m / 2.0) >= radius)
        )
    elif inputs.template == "pressure_vessel":
        radial = np.hypot(centroids[:, 0], centroids[:, 1])
        inside = (radial >= inputs.length_m) & (radial <= inputs.width_m)
    else:
        arm = inputs.width_m / 2.0
        vertical_length = inputs.length_m * 0.55
        x_end = inputs.length_m - arm
        y_end = -(vertical_length - arm)
        in_shape = (
            ((centroids[:, 0] >= 0) & (centroids[:, 0] <= x_end) & (np.abs(centroids[:, 1]) <= arm))
            | ((centroids[:, 0] >= x_end - 2 * arm) & (centroids[:, 0] <= x_end) & (centroids[:, 1] >= y_end) & (centroids[:, 1] <= -arm))
            | (np.hypot(centroids[:, 0], centroids[:, 1]) <= arm)
            | (np.hypot(centroids[:, 0] - x_end, centroids[:, 1] - y_end) <= arm)
        )
        hole = inputs.feature_diameter_m / 2.0
        outside_holes = (
            (np.hypot(centroids[:, 0], centroids[:, 1]) >= hole)
            & (np.hypot(centroids[:, 0] - x_end, centroids[:, 1] - y_end) >= hole)
        )
        inside = in_shape & outside_holes
    triangulation.set_mask((~inside) | (edge_lengths.max(axis=1) > 3.0 * inputs.mesh_size_m))
    contour = axis.tricontourf(triangulation, stress[finite], levels=24, cmap="turbo")
    maximum_index = int(np.nanargmax(point["stress"]))
    axis.scatter(stress_xy[maximum_index, 0], stress_xy[maximum_index, 1], c="#132f4c", marker="x", s=70)
    axis.set_title(f"MAPDL {OFFICIAL_TEMPLATE_DEFINITIONS[inputs.template]['element_type']} equivalent stress")
    axis.set_xlabel("X (m)")
    axis.set_ylabel("Y (m)")
    axis.set_aspect("equal", adjustable="box")
    figure.colorbar(contour, ax=axis, label="Equivalent stress (MPa)")
    figure.tight_layout()
    figure.savefig(stress_path, dpi=180, bbox_inches="tight")
    plt.close(figure)

    deformed = disp_xyz[:, :2] + point["displacement"][:, :2]
    figure, axis = plt.subplots(figsize=(10.5, 6.3))
    scatter = axis.scatter(deformed[:, 0], deformed[:, 1], c=point["displacement_norm"] * 1000, cmap="turbo", s=17)
    axis.scatter(disp_xyz[:, 0], disp_xyz[:, 1], c="#9bb0c2", s=6, alpha=0.35, label="Undeformed nodes")
    axis.set_title(f"MAPDL {OFFICIAL_TEMPLATE_DEFINITIONS[inputs.template]['element_type']} nodal deformation")
    axis.set_xlabel("X (m)")
    axis.set_ylabel("Y (m)")
    axis.set_aspect("equal", adjustable="box")
    axis.legend(loc="best")
    figure.colorbar(scatter, ax=axis, label="Displacement magnitude (mm)")
    figure.tight_layout()
    figure.savefig(displacement_path, dpi=180, bbox_inches="tight")
    plt.close(figure)
    return stress_path.name, displacement_path.name


def solve_official_example_range(
    mapdl,
    inputs: OfficialExampleInputs,
    load_range: ForceRange,
    output_dir: Path,
) -> SimulationResult:
    """Run all requested load/pressure points through MAPDL."""

    inputs.validate()
    load_range.validate()
    curve: list[dict] = []
    final_inputs = inputs
    final_point = None
    final_assessment = None
    for load_value in load_range.values():
        point_inputs = replace(inputs, load_value=load_value)
        _build_model(mapdl, point_inputs)
        point = _extract_point(mapdl)
        assessment = _assessment(mapdl, point_inputs, point)
        curve.append(
            {
                "force_n": load_value,
                "load_value": load_value,
                "load_unit": point_inputs.load_unit,
                "maximum_stress_pa": point["maximum_stress"],
                "maximum_displacement_m": point["maximum_displacement"],
                "safety_factor": point_inputs.yield_strength_pa / point["maximum_stress"],
                "point_status": "threshold_reached" if point["maximum_stress"] >= point_inputs.yield_strength_pa else "within_reference_strength",
                "failure_status": assessment.failure_status,
                "breakage_assessment": assessment.breakage_assessment,
                "stress_utilization": assessment.stress_utilization,
                "deformation_ratio": assessment.deformation_ratio,
                "large_deformation_warning": assessment.large_deformation_warning,
                "estimated_failure_load_n": assessment.estimated_failure_load_n,
                "estimated_reference_strength_load_n": assessment.estimated_reference_strength_load_n,
                "estimated_deformation_limit_load_n": assessment.estimated_deformation_limit_load_n,
                "governing_screening_load_n": assessment.governing_screening_load_n,
                "governing_screening_criterion": assessment.governing_screening_criterion,
            }
        )
        final_inputs, final_point, final_assessment = point_inputs, point, assessment

    crossing = _first_strength_crossing(curve, inputs.yield_strength_pa)
    estimated = _estimate_linear_threshold_force(curve, inputs.yield_strength_pa)
    threshold = crossing if crossing is not None else estimated
    threshold_reached = any(point["maximum_stress_pa"] >= inputs.yield_strength_pa for point in curve)
    break_status = "threshold_reached" if threshold_reached else "threshold_estimated" if threshold is not None else "not_evaluated"
    stress_image, displacement_image = _export_images(mapdl, final_inputs, final_point, output_dir)
    definition = OFFICIAL_TEMPLATE_DEFINITIONS[inputs.template]
    failure_image = export_failure_assessment_image(
        output_dir,
        template=definition["name"],
        material=inputs.material,
        force_n=final_inputs.load_value,
        maximum_stress_pa=final_point["maximum_stress"],
        maximum_displacement_m=final_point["maximum_displacement"],
        reference_strength_pa=inputs.yield_strength_pa,
        assessment=final_assessment,
        break_force_n=threshold,
        load_unit=final_inputs.load_unit,
    )
    sweep_image = export_force_sweep_image(
        output_dir,
        curve=curve,
        reference_strength_pa=inputs.yield_strength_pa,
        strength_basis=inputs.strength_basis or "reference strength",
        break_force_n=threshold,
        load_label=final_inputs.load_label,
        load_unit=final_inputs.load_unit,
    )
    return SimulationResult(
        case_id=inputs.case_id,
        force_n=final_inputs.load_value,
        load_value=final_inputs.load_value,
        load_type=final_inputs.load_label,
        load_unit=final_inputs.load_unit,
        material=inputs.material,
        beam_length_m=inputs.length_m,
        beam_width_m=inputs.width_m,
        beam_height_m=inputs.thickness_m,
        maximum_stress_pa=final_point["maximum_stress"],
        maximum_displacement_m=final_point["maximum_displacement"],
        safety_factor=inputs.yield_strength_pa / final_point["maximum_stress"],
        status="completed",
        youngs_modulus_pa=inputs.youngs_modulus_pa,
        poissons_ratio=inputs.poissons_ratio,
        density_kg_m3=inputs.density_kg_m3,
        reference_strength_pa=inputs.yield_strength_pa,
        strength_basis=inputs.strength_basis or "reference strength",
        material_model_note=inputs.material_model_note or "",
        stress_image=stress_image,
        displacement_image=displacement_image,
        failure_assessment_image=failure_image,
        sweep_image=sweep_image,
        template=inputs.template,
        model_provenance=definition["provenance"],
        element_type=definition["element_type"],
        official_source_url=definition["source_url"],
        stress_method=definition["stress_method"],
        diameter_m=inputs.feature_diameter_m,
        force_start_n=load_range.start_n,
        force_end_n=load_range.end_n,
        force_increment_n=load_range.effective_increment_n,
        force_steps=len(curve),
        break_force_n=threshold,
        break_status=break_status,
        force_curve=curve,
        **final_assessment.as_result_fields(),
    )
