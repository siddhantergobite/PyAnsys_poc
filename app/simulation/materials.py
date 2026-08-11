"""Controlled material cards for the bounded structural PoC.

The solver accepts only these named cards.  Values are SI and are intentionally
kept here so the API, scripts, solver, and UI cannot silently disagree.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class MaterialProperties:
    name: str
    youngs_modulus_pa: float
    poissons_ratio: float
    density_kg_m3: float
    reference_strength_pa: float
    strength_basis: str
    model_note: str
    source_url: str

    def as_dict(self) -> dict:
        return asdict(self)


MATERIAL_CATALOG: dict[str, MaterialProperties] = {
    "Structural Steel": MaterialProperties(
        name="Structural Steel",
        youngs_modulus_pa=200.0e9,
        poissons_ratio=0.30,
        density_kg_m3=7850.0,
        reference_strength_pa=250.0e6,
        strength_basis="yield strength",
        model_note="Linear isotropic PoC baseline material.",
        source_url="https://www.ansys.com/products/materials/granta-selector/materials-data-for-simulation",
    ),
    "Stainless Steel 304": MaterialProperties(
        name="Stainless Steel 304",
        youngs_modulus_pa=193.0e9,
        poissons_ratio=0.29,
        density_kg_m3=8000.0,
        reference_strength_pa=210.0e6,
        strength_basis="0.2% proof strength",
        model_note="Typical annealed/flat-product values; linear isotropic PoC card.",
        source_url="https://www.thyssenkrupp-materials.co.uk/stainless-steel-304-14301.html/index.html",
    ),
    "Aluminium Alloy 6061-T6": MaterialProperties(
        name="Aluminium Alloy 6061-T6",
        youngs_modulus_pa=68.9e9,
        poissons_ratio=0.33,
        density_kg_m3=2700.0,
        reference_strength_pa=276.0e6,
        strength_basis="tensile yield strength",
        model_note="Typical 6061-T6 values; linear isotropic PoC card.",
        source_url="https://www.glemco.com/capabilities/material-expertise/aluminum-6061-t6/",
    ),
    "Titanium Alloy Ti-6Al-4V": MaterialProperties(
        name="Titanium Alloy Ti-6Al-4V",
        youngs_modulus_pa=114.0e9,
        poissons_ratio=0.33,
        density_kg_m3=4430.0,
        reference_strength_pa=827.0e6,
        strength_basis="0.2% proof strength",
        model_note="Typical annealed bar values; linear isotropic PoC card.",
        source_url="https://maher.com/media/pdfs/ti-6al-4v-datasheet-rev-01.pdf",
    ),
    "ABS Plastic": MaterialProperties(
        name="ABS Plastic",
        youngs_modulus_pa=2.758e9,
        poissons_ratio=0.35,
        density_kg_m3=1020.0,
        reference_strength_pa=40.0e6,
        strength_basis="tensile yield strength at 23 C",
        model_note="TECARAN natural ABS approximation; linear isotropic, short-term PoC card.",
        source_url="https://ipiplastics.com/pages/abs-natural",
    ),
}

MATERIAL_NAMES = tuple(MATERIAL_CATALOG)


def get_material(name: str) -> MaterialProperties:
    """Return one approved material card or reject the input clearly."""

    try:
        return MATERIAL_CATALOG[name]
    except KeyError as exc:
        supported = ", ".join(MATERIAL_NAMES)
        raise ValueError(f"Unsupported material '{name}'. Supported: {supported}") from exc


def material_catalog_payload() -> list[dict]:
    """Return JSON-ready material metadata for the dashboard."""

    return [material.as_dict() for material in MATERIAL_CATALOG.values()]
