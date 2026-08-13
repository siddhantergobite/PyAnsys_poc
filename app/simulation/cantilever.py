"""Beam cantilever template solved directly by MAPDL."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from .config import CantileverInputs, ForceRange
from .assessment import (
    FailureAssessment,
    assess_failure,
    export_failure_assessment_image,
    export_force_sweep_image,
)
from .results import SimulationResult


def _finite_max(values: np.ndarray, label: str) -> float:
    values = np.asarray(values, dtype=float)
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        raise RuntimeError(f"MAPDL returned no finite values for {label}")
    return float(np.max(np.abs(finite)))


def _build_model(mapdl, inputs: CantileverInputs) -> None:
    inputs.validate()

    mapdl.clear()
    mapdl.prep7()
    # BEAM188 is available in the installed Ansys Student MAPDL license.
    # It also keeps the first PoC small, fast, and parameter-driven.
    mapdl.et(1, 188)
    # Request transverse shear and intermediate-station stress output so the
    # beam section stresses can be read from BEAM188's SMISC results.
    mapdl.keyopt(1, 4, 1)
    mapdl.keyopt(1, 6, 1)
    mapdl.mp("EX", 1, inputs.youngs_modulus_pa)
    mapdl.mp("PRXY", 1, inputs.poissons_ratio)
    mapdl.mp("DENS", 1, inputs.density_kg_m3)
    mapdl.sectype(1, "BEAM", "RECT")
    mapdl.secdata(inputs.width_m, inputs.height_m)
    mapdl.k(1, 0.0, 0.0, 0.0)
    mapdl.k(2, inputs.length_m, 0.0, 0.0)
    mapdl.l(1, 2)
    mapdl.lesize("ALL", inputs.mesh_size_m)
    mapdl.lmesh("ALL")
    mapdl.allsel("ALL")

    # Fix the x=0 end face.
    mapdl.nsel("S", "LOC", "X", 0.0)
    mapdl.d("ALL", "ALL", 0.0)

    # Apply the force to the free-end node.
    mapdl.nsel("S", "LOC", "X", inputs.length_m)
    mapdl.f("ALL", "FY", -inputs.force_n)
    mapdl.allsel("ALL")
    mapdl.finish()

    mapdl.run("/SOLU")
    mapdl.antype("STATIC")
    mapdl.solve()
    mapdl.finish()
    mapdl.post1()
    mapdl.set("LAST")


def _resolve_existing_model(mapdl, inputs: CantileverInputs) -> None:
    """Replace the cantilever load and solve without rebuilding its mesh."""

    mapdl.finish()
    mapdl.run("/SOLU")
    mapdl.allsel("ALL")
    mapdl.fdele("ALL", "ALL")
    mapdl.nsel("S", "LOC", "X", inputs.length_m)
    mapdl.f("ALL", "FY", -inputs.force_n)
    mapdl.allsel("ALL")
    mapdl.solve()
    mapdl.finish()
    mapdl.post1()
    mapdl.set("LAST")


def _export_images(mapdl, output_dir: Path) -> tuple[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stress_path = output_dir / "stress.png"
    displacement_path = output_dir / "deformation.png"
    # BEAM188 does not store nodal equivalent stress in the same way as a
    # solid element. Plot a supported element stress component instead.
    mapdl.post_processing.plot_element_stress(
        "X",
        option="MAX",
        off_screen=True,
        savefig=str(stress_path),
        background="white",
        show_edges=True,
    )
    mapdl.post_processing.plot_nodal_displacement(
        component="NORM",
        off_screen=True,
        savefig=str(displacement_path),
        background="white",
        show_edges=True,
    )
    return stress_path.name, displacement_path.name


def _export_cantilever_images(
    mapdl,
    inputs: CantileverInputs,
    output_dir: Path,
    stress_values_pa: np.ndarray,
    displacement_norm_m: np.ndarray,
) -> tuple[str, str]:
    """Export clear plots using the same solver values returned in CSV/JSON."""

    output_dir.mkdir(parents=True, exist_ok=True)
    stress_path = output_dir / "stress.png"
    displacement_path = output_dir / "deformation.png"

    stress_mpa = np.asarray(stress_values_pa, dtype=float) / 1.0e6
    element_count = stress_mpa.size
    x_edges = np.linspace(0.0, inputs.length_m, element_count + 1)
    x_centres = (x_edges[:-1] + x_edges[1:]) / 2.0
    maximum_index = int(np.argmax(stress_mpa))

    fig, axis = plt.subplots(figsize=(11, 5.5))
    contour = axis.pcolormesh(
        x_edges,
        [0.0, inputs.height_m],
        stress_mpa.reshape(1, -1),
        shading="flat",
        cmap="turbo",
        vmin=0.0,
        vmax=max(float(np.max(stress_mpa)), 1.0e-12),
    )
    axis.axvline(0.0, color="#132f4c", linewidth=5, label="Fixed support")
    axis.annotate(
        f"Maximum = {stress_mpa[maximum_index]:.3f} MPa",
        xy=(x_centres[maximum_index], inputs.height_m / 2.0),
        xytext=(0.28 * inputs.length_m, 1.16 * inputs.height_m),
        arrowprops={"arrowstyle": "->", "color": "#132f4c", "lw": 1.5},
        color="#132f4c",
        fontsize=11,
        fontweight="bold",
    )
    axis.text(0.0, -0.16 * inputs.height_m, "Fixed end", ha="left", color="#52677d")
    axis.text(
        inputs.length_m,
        -0.16 * inputs.height_m,
        "Free end",
        ha="right",
        color="#52677d",
    )
    axis.set_xlim(0.0, inputs.length_m)
    axis.set_ylim(-0.25 * inputs.height_m, 1.35 * inputs.height_m)
    axis.set_xlabel("Position along beam (m)")
    axis.set_ylabel("Beam section height (m)")
    axis.set_title("MAPDL BEAM188 maximum bending stress", fontweight="bold")
    axis.grid(axis="x", color="#dce5ec", linewidth=0.7, alpha=0.8)
    colorbar = fig.colorbar(contour, ax=axis, pad=0.03)
    colorbar.set_label("Bending stress (MPa)")
    fig.tight_layout()
    fig.savefig(stress_path, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    nodes = np.asarray(mapdl.mesh.nodes, dtype=float)
    displacement_norm_m = np.asarray(displacement_norm_m, dtype=float)
    displacement_y_m = np.asarray(
        mapdl.post_processing.nodal_displacement("Y"), dtype=float
    )
    if not (nodes.shape[0] == displacement_norm_m.size == displacement_y_m.size):
        raise RuntimeError("MAPDL node and displacement arrays have inconsistent sizes")

    order = np.argsort(nodes[:, 0])
    x_nodes = nodes[order, 0]
    displacement_norm_mm = displacement_norm_m[order] * 1.0e3
    displacement_y_mm = displacement_y_m[order] * 1.0e3
    maximum_node = int(np.argmax(displacement_norm_mm))

    fig, axis = plt.subplots(figsize=(11, 5.5))
    axis.axhline(0.0, color="#8da1b4", linestyle="--", linewidth=1.2, label="Undeformed")
    axis.plot(
        x_nodes,
        displacement_y_mm,
        color="#315f89",
        linewidth=2.2,
        label="Deformed centreline",
    )
    points = axis.scatter(
        x_nodes,
        displacement_y_mm,
        c=displacement_norm_mm,
        cmap="turbo",
        s=38,
        zorder=3,
    )
    axis.scatter([0.0], [0.0], marker="s", s=90, color="#132f4c", label="Fixed support")
    axis.annotate(
        f"Maximum = {displacement_norm_mm[maximum_node]:.4f} mm",
        xy=(x_nodes[maximum_node], displacement_y_mm[maximum_node]),
        xytext=(0.55 * inputs.length_m, 0.58 * float(np.min(displacement_y_mm))),
        arrowprops={"arrowstyle": "->", "color": "#132f4c", "lw": 1.5},
        color="#132f4c",
        fontsize=11,
        fontweight="bold",
    )
    axis.set_xlabel("Position along beam (m)")
    axis.set_ylabel("Vertical displacement (mm)")
    axis.set_title("MAPDL nodal deformation", fontweight="bold")
    axis.grid(color="#dce5ec", linewidth=0.7, alpha=0.8)
    axis.legend(loc="lower left")
    colorbar = fig.colorbar(points, ax=axis, pad=0.03)
    colorbar.set_label("Total displacement (mm)")
    fig.tight_layout()
    fig.savefig(displacement_path, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    return stress_path.name, displacement_path.name


def _beam_bending_stress_values(mapdl) -> np.ndarray:
    """Return BEAM188 extreme-fibre bending stress values in pascals.

    BEAM188 stores the extreme-fiber bending stresses in the SMISC result
    table. The indices match the official PyMAPDL BEAM188 reporting example.
    """

    mapdl.etable("SByT", "SMISC", 32)
    mapdl.etable("SByB", "SMISC", 33)
    top = np.asarray(mapdl.get_array("ELEM", "", "ETAB", "SByT"), dtype=float)
    bottom = np.asarray(mapdl.get_array("ELEM", "", "ETAB", "SByB"), dtype=float)
    if top.size != bottom.size or top.size == 0:
        raise RuntimeError("MAPDL returned inconsistent beam bending stress arrays")
    return np.maximum(np.abs(top), np.abs(bottom))


def _beam_max_bending_stress(mapdl) -> float:
    """Return the maximum BEAM188 bending stress in pascals."""

    return _finite_max(_beam_bending_stress_values(mapdl), "beam bending stress")


def _extract_point(mapdl, inputs: CantileverInputs) -> tuple[np.ndarray, np.ndarray, float, float]:
    """Read the solver values for the currently solved MAPDL beam."""

    stress_values = _beam_bending_stress_values(mapdl)
    displacement_values = np.asarray(
        mapdl.post_processing.nodal_displacement("NORM"), dtype=float
    )
    return (
        stress_values,
        displacement_values,
        _finite_max(stress_values, "beam bending stress"),
        _finite_max(displacement_values, "displacement"),
    )


def _cantilever_locations(
    mapdl,
    inputs: CantileverInputs,
    stress_values: np.ndarray,
    displacement_values: np.ndarray,
) -> tuple[str, str, str]:
    """Describe the critical solver locations for the assessment report."""

    stress_index = int(np.argmax(np.abs(np.asarray(stress_values, dtype=float))))
    element_count = max(int(np.asarray(stress_values).size), 1)
    stress_x = inputs.length_m * (stress_index + 0.5) / element_count
    if stress_index == 0:
        stress_region = "near the fixed support"
    elif stress_index == element_count - 1:
        stress_region = "near the free end"
    else:
        stress_region = "along the beam span"
    stress_location = (
        f"BEAM188 element {stress_index + 1} near x={stress_x:.4g} m ({stress_region})"
    )

    nodes = np.asarray(mapdl.mesh.nodes, dtype=float)
    displacement_values = np.asarray(displacement_values, dtype=float)
    node_index = int(np.argmax(np.abs(displacement_values)))
    node_x = float(nodes[node_index, 0])
    displacement_location = f"MAPDL node near x={node_x:.4g} m (largest displacement)"
    load_location = f"FY load applied at the free-end node set x={inputs.length_m:.4g} m"
    return stress_location, displacement_location, load_location


def _cantilever_assessment(
    mapdl,
    inputs: CantileverInputs,
    stress_values: np.ndarray,
    displacement_values: np.ndarray,
    maximum_stress: float,
    maximum_displacement: float,
):
    stress_location, displacement_location, load_location = _cantilever_locations(
        mapdl, inputs, stress_values, displacement_values
    )
    assessment = assess_failure(
        force_n=inputs.force_n,
        maximum_stress_pa=maximum_stress,
        reference_strength_pa=inputs.yield_strength_pa,
        maximum_displacement_m=maximum_displacement,
        deformation_reference_length_m=inputs.length_m,
        critical_stress_location=stress_location,
        critical_displacement_location=displacement_location,
        load_application_location=load_location,
    )
    return assessment


def _first_strength_crossing(
    curve: list[dict[str, float | str]], reference_strength_pa: float
) -> float | None:
    """Linearly interpolate the first force at the reference-strength crossing.

    This is a linear-elastic *threshold* estimate, not a claim of real-world
    fracture. Physical failure needs a validated nonlinear/material model.
    """

    for index, point in enumerate(curve):
        stress = float(point["maximum_stress_pa"])
        force = float(point["force_n"])
        if stress < reference_strength_pa:
            continue
        if index == 0:
            # The crossing is below the requested range.  Returning the first
            # sampled force would incorrectly report the range start as the
            # material threshold; let the linear estimate recover the actual
            # below-range crossing instead.
            return None
        previous = curve[index - 1]
        previous_stress = float(previous["maximum_stress_pa"])
        previous_force = float(previous["force_n"])
        if stress == previous_stress:
            return force
        ratio = (reference_strength_pa - previous_stress) / (stress - previous_stress)
        return previous_force + ratio * (force - previous_force)
    return None


def _linear_reference_threshold_force(
    force_n: float, stress_pa: float, reference_strength_pa: float
) -> float | None:
    """Estimate the force at the material reference strength.

    All current PoC templates are linear elastic. Stress therefore scales with
    force, allowing a threshold estimate even when the requested force sweep
    does not reach the reference strength. This is not a physical fracture
    prediction.
    """

    if force_n <= 0 or stress_pa <= 0 or reference_strength_pa <= 0:
        return None
    return force_n * reference_strength_pa / stress_pa


def _estimate_linear_threshold_force(
    curve: list[dict[str, float | str]], reference_strength_pa: float
) -> float | None:
    """Estimate a threshold from the first nonzero elastic result."""

    for point in curve:
        threshold = _linear_reference_threshold_force(
            float(point["force_n"]),
            float(point["maximum_stress_pa"]),
            reference_strength_pa,
        )
        if threshold is not None:
            return threshold
    return None


def solve_cantilever(mapdl, inputs: CantileverInputs, output_dir: Path) -> SimulationResult:
    """Build, solve, extract results, and export images for one case."""

    _build_model(mapdl, inputs)
    stress_values, displacement_values, maximum_stress, maximum_displacement = _extract_point(
        mapdl, inputs
    )
    safety_factor = (
        inputs.yield_strength_pa / maximum_stress if maximum_stress > 0 else None
    )
    assessment = _cantilever_assessment(
        mapdl,
        inputs,
        stress_values,
        displacement_values,
        maximum_stress,
        maximum_displacement,
    )
    break_force_n = _linear_reference_threshold_force(
        inputs.force_n, maximum_stress, inputs.yield_strength_pa
    )
    break_status = (
        "threshold_reached"
        if break_force_n is not None and maximum_stress >= inputs.yield_strength_pa
        else "threshold_estimated"
        if break_force_n is not None
        else "not_evaluated"
    )
    stress_image, displacement_image = _export_cantilever_images(
        mapdl,
        inputs,
        output_dir,
        stress_values,
        displacement_values,
    )
    failure_image = export_failure_assessment_image(
        output_dir,
        template="Cantilever beam",
        material=inputs.material,
        force_n=inputs.force_n,
        maximum_stress_pa=maximum_stress,
        maximum_displacement_m=maximum_displacement,
        reference_strength_pa=inputs.yield_strength_pa,
        assessment=assessment,
        break_force_n=break_force_n,
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
        break_force_n=break_force_n,
        break_status=break_status,
        failure_assessment_image=failure_image,
        **assessment.as_result_fields(),
    )


def solve_cantilever_range(
    mapdl, inputs: CantileverInputs, force_range: ForceRange, output_dir: Path
) -> SimulationResult:
    """Solve every requested force point and retain the final spatial result.

    The final force produces the existing spatial stress/deformation images.
    Separate force-sweep and failure-assessment images are generated so each
    report remains readable.
    """

    inputs.validate()
    force_range.validate()
    curve: list[dict[str, float | str]] = []
    final_inputs = inputs
    final_stress_values = np.array([])
    final_displacement_values = np.array([])
    final_stress = 0.0
    final_displacement = 0.0

    for point_index, force_n in enumerate(force_range.values()):
        point_inputs = replace(inputs, force_n=force_n)
        if point_index == 0:
            _build_model(mapdl, point_inputs)
        else:
            _resolve_existing_model(mapdl, point_inputs)
        stress_values, displacement_values, maximum_stress, maximum_displacement = _extract_point(
            mapdl, point_inputs
        )
        safety_factor = (
            point_inputs.yield_strength_pa / maximum_stress if maximum_stress > 0 else None
        )
        curve.append(
            {
                "force_n": force_n,
                "maximum_stress_pa": maximum_stress,
                "maximum_displacement_m": maximum_displacement,
                "safety_factor": safety_factor if safety_factor is not None else "",
                "point_status": "threshold_reached"
                if maximum_stress >= point_inputs.yield_strength_pa
                else "within_reference_strength",
            }
        )
        point_assessment = _cantilever_assessment(
            mapdl,
            point_inputs,
            stress_values,
            displacement_values,
            maximum_stress,
            maximum_displacement,
        )
        curve[-1].update(
            {
                "failure_status": point_assessment.failure_status,
                "breakage_assessment": point_assessment.breakage_assessment,
                "stress_utilization": (
                    point_assessment.stress_utilization
                    if point_assessment.stress_utilization is not None
                    else ""
                ),
                "deformation_ratio": (
                    point_assessment.deformation_ratio
                    if point_assessment.deformation_ratio is not None
                    else ""
                ),
                "large_deformation_warning": point_assessment.large_deformation_warning,
                "estimated_failure_load_n": (
                    point_assessment.estimated_failure_load_n
                    if point_assessment.estimated_failure_load_n is not None
                    else ""
                ),
                "estimated_reference_strength_load_n": (
                    point_assessment.estimated_reference_strength_load_n
                    if point_assessment.estimated_reference_strength_load_n is not None
                    else ""
                ),
                "estimated_deformation_limit_load_n": (
                    point_assessment.estimated_deformation_limit_load_n
                    if point_assessment.estimated_deformation_limit_load_n is not None
                    else ""
                ),
                "governing_screening_load_n": (
                    point_assessment.governing_screening_load_n
                    if point_assessment.governing_screening_load_n is not None
                    else ""
                ),
                "governing_screening_criterion": point_assessment.governing_screening_criterion,
            }
        )
        final_inputs = point_inputs
        final_stress_values = stress_values
        final_displacement_values = displacement_values
        final_stress = maximum_stress
        final_displacement = maximum_displacement

    crossing_force_n = _first_strength_crossing(curve, inputs.yield_strength_pa)
    estimated_force_n = _estimate_linear_threshold_force(curve, inputs.yield_strength_pa)
    break_force_n = crossing_force_n if crossing_force_n is not None else estimated_force_n
    threshold_reached = any(
        float(point["maximum_stress_pa"]) >= inputs.yield_strength_pa
        for point in curve
    )
    if threshold_reached:
        break_status = "threshold_reached"
    elif estimated_force_n is not None:
        break_status = "threshold_estimated"
    else:
        break_status = "not_evaluated"
    final_safety_factor = inputs.yield_strength_pa / final_stress if final_stress > 0 else None
    final_assessment = _cantilever_assessment(
        mapdl,
        final_inputs,
        final_stress_values,
        final_displacement_values,
        final_stress,
        final_displacement,
    )
    stress_image, displacement_image = _export_cantilever_images(
        mapdl,
        final_inputs,
        output_dir,
        final_stress_values,
        final_displacement_values,
    )
    failure_image = export_failure_assessment_image(
        output_dir,
        template="Cantilever beam",
        material=inputs.material,
        force_n=final_inputs.force_n,
        maximum_stress_pa=final_stress,
        maximum_displacement_m=final_displacement,
        reference_strength_pa=inputs.yield_strength_pa,
        assessment=final_assessment,
        break_force_n=break_force_n,
    )
    sweep_image = export_force_sweep_image(
        output_dir,
        curve=curve,
        reference_strength_pa=inputs.yield_strength_pa,
        strength_basis=inputs.strength_basis or "reference strength",
        break_force_n=break_force_n,
    )
    return SimulationResult(
        case_id=inputs.case_id,
        force_n=final_inputs.force_n,
        material=inputs.material,
        beam_length_m=inputs.length_m,
        beam_width_m=inputs.width_m,
        beam_height_m=inputs.height_m,
        maximum_stress_pa=final_stress,
        maximum_displacement_m=final_displacement,
        safety_factor=final_safety_factor,
        status="completed",
        youngs_modulus_pa=inputs.youngs_modulus_pa,
        poissons_ratio=inputs.poissons_ratio,
        density_kg_m3=inputs.density_kg_m3,
        reference_strength_pa=inputs.yield_strength_pa,
        strength_basis=inputs.strength_basis or "reference strength",
        material_model_note=inputs.material_model_note or "",
        stress_image=stress_image,
        displacement_image=displacement_image,
        force_start_n=force_range.start_n,
        force_end_n=force_range.end_n,
        force_steps=len(curve),
        break_force_n=break_force_n,
        break_status=break_status,
        force_curve=curve,
        failure_assessment_image=failure_image,
        sweep_image=sweep_image,
        **final_assessment.as_result_fields(),
    )
