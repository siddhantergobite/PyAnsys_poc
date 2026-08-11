"""Beam cantilever template solved directly by MAPDL."""

from __future__ import annotations

from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from .config import CantileverInputs
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


def solve_cantilever(mapdl, inputs: CantileverInputs, output_dir: Path) -> SimulationResult:
    """Build, solve, extract results, and export images for one case."""

    _build_model(mapdl, inputs)
    stress_values = _beam_bending_stress_values(mapdl)
    maximum_stress = _finite_max(stress_values, "beam bending stress")
    displacement_values = np.asarray(
        mapdl.post_processing.nodal_displacement("NORM"), dtype=float
    )
    maximum_displacement = _finite_max(displacement_values, "displacement")
    safety_factor = (
        inputs.yield_strength_pa / maximum_stress if maximum_stress > 0 else None
    )
    stress_image, displacement_image = _export_cantilever_images(
        mapdl, inputs, output_dir, stress_values, displacement_values
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
    )
