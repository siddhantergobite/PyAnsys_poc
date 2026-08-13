"""Export auditable definitions of the parameter-built MAPDL templates."""

from __future__ import annotations

from pathlib import Path


def _template_name(inputs) -> str:
    template = getattr(inputs, "template", "cantilever")
    return {
        "cantilever": "Cantilever beam",
        "corner_bracket": "Ansys corner bracket (official example adaptation)",
        "plate_hole": "Ansys plate with a hole (official example adaptation)",
        "pressure_vessel": "Ansys pressure vessel (official example adaptation)",
        "table": "Table frame",
        "bolt": "Bolt shank surrogate",
        "screw": "Screw shank surrogate",
        "nut": "Nut annular-section surrogate",
    }[template]


def _model_details(inputs) -> list[str]:
    template = getattr(inputs, "template", "cantilever")
    is_official = template in {"corner_bracket", "plate_hole", "pressure_vessel"}
    final_load = getattr(inputs, "load_value", getattr(inputs, "force_n", 0.0))
    load_unit = getattr(inputs, "load_unit", "N")
    common = [
        f"Template: {_template_name(inputs)} ({template})",
        "Construction: generated parametrically by Python/PyMAPDL; no CAD file is imported",
        f"MAPDL element: {('PLANE182' if template == 'pressure_vessel' else 'PLANE183') if is_official else 'BEAM188'}",
        f"Material: {inputs.material}",
        f"Elastic modulus: {inputs.youngs_modulus_pa:.12g} Pa",
        f"Poisson ratio: {inputs.poissons_ratio:.12g}",
        f"Density: {inputs.density_kg_m3:.12g} kg/m^3",
        f"Reference strength: {inputs.yield_strength_pa:.12g} Pa ({inputs.strength_basis})",
        f"Final applied load: {final_load:.12g} {load_unit}",
        f"Mesh target size: {inputs.mesh_size_m:.12g} m",
    ]
    if template == "cantilever":
        common.extend([
            f"Geometry: length={inputs.length_m:.12g} m, rectangular width={inputs.width_m:.12g} m, height={inputs.height_m:.12g} m",
            "Boundary condition: all DOFs fixed at x=0",
            f"Load: FY at free-end node set x={inputs.length_m:.12g} m",
            "Stress result: BEAM188 extreme-fibre bending stress from SMISC 32/33",
        ])
    elif template == "corner_bracket":
        common.extend([
            "Element: PLANE183, plane stress with thickness",
            "Topology: L-shaped corner bracket with two pin holes",
            "Support/load: left pin fixed; distributed load on lower half of right pin hole",
            "Source: official PyMAPDL corner-bracket example adaptation",
        ])
    elif template == "plate_hole":
        common.extend([
            "Element: PLANE183, plane stress with thickness",
            "Topology: rectangular plate with central circular hole",
            "Support/load: left edge restrained; coupled tensile force on right edge",
            "Source: official PyMAPDL plate-with-hole example adaptation",
        ])
    elif template == "pressure_vessel":
        common.extend([
            "Element: PLANE182, plane strain",
            "Topology: quarter annulus",
            "Support/load: symmetry constraints; internal pressure on inner radius",
            "Source: official PyMAPDL 2D pressure-vessel example adaptation",
        ])
    elif template == "table":
        common.extend([
            f"Geometry: top length={inputs.length_m:.12g} m, top width={inputs.width_m:.12g} m, leg height={inputs.height_m:.12g} m, circular member diameter={inputs.diameter_m:.12g} m",
            "Boundary condition: all DOFs fixed at the four z=0 support nodes",
            f"Load: FZ at top-centre node z={inputs.height_m:.12g} m",
            "Stress result: BEAM188 extreme-fibre bending stress from SMISC 32/33",
        ])
    else:
        section = "annular CTUBE (inner radius = 0.55 x outer radius)" if template == "nut" else "solid circular CSOLID"
        direction = "compression" if template == "nut" else "tension"
        common.extend([
            f"Geometry: length={inputs.length_m:.12g} m, nominal diameter={inputs.diameter_m:.12g} m, {section}",
            "Boundary condition: all DOFs fixed at x=0",
            f"Load: axial FX {direction} at x={inputs.length_m:.12g} m",
            "Stress result: nominal axial force divided by BEAM188 section area",
        ])
    common.extend([
        "",
        "Important limitations:",
        "- Linear isotropic, small-deformation screening model.",
        "- Bolt/screw/nut templates do not include threads, preload, head geometry, contact, friction, or stress concentration.",
        "- The table template does not include joint/contact details or solid members.",
        "- Reference-strength crossing is not an exact physical fracture prediction.",
        "",
        "Source code:",
        "- app/simulation/cantilever.py (cantilever)",
        "- app/simulation/examples.py (table, bolt, screw, nut)",
        "- app/simulation/official_examples.py (official example adaptations)",
    ])
    return common


def export_model_artifacts(mapdl, inputs, output_dir: Path) -> tuple[str, str]:
    """Write a readable definition and the actual final MAPDL model database."""

    output_dir.mkdir(parents=True, exist_ok=True)
    definition_path = output_dir / "model_definition.txt"
    database_path = output_dir / "model.db"
    definition_path.write_text("\n".join(_model_details(inputs)) + "\n", encoding="utf-8")

    # Save only model data: geometry, mesh, material, constraints, and final
    # load. Result arrays remain in results.json/results.csv and the PNG files.
    mapdl.finish()
    mapdl.save(str(database_path.with_suffix("")), "db", "MODEL")
    if not database_path.is_file():
        raise RuntimeError("MAPDL did not create the requested model.db artifact")
    return definition_path.name, database_path.name
