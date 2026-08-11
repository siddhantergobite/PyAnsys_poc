"""Fast checks for the controlled material catalogue and API boundary."""

from __future__ import annotations

import unittest

from pydantic import ValidationError

from app.api.main import SimulationRequest
from app.simulation.config import CantileverInputs
from app.simulation.examples import ExampleInputs
from app.simulation.materials import MATERIAL_NAMES, get_material


EXPECTED_NAMES = (
    "Structural Steel",
    "Stainless Steel 304",
    "Aluminium Alloy 6061-T6",
    "Titanium Alloy Ti-6Al-4V",
    "ABS Plastic",
)


class MaterialCatalogueTests(unittest.TestCase):
    def test_exact_bounded_catalogue(self) -> None:
        self.assertEqual(MATERIAL_NAMES, EXPECTED_NAMES)

    def test_every_card_has_valid_solver_properties(self) -> None:
        for name in MATERIAL_NAMES:
            with self.subTest(material=name):
                card = get_material(name)
                self.assertGreater(card.youngs_modulus_pa, 0)
                self.assertGreater(card.density_kg_m3, 0)
                self.assertGreater(card.reference_strength_pa, 0)
                self.assertGreater(card.poissons_ratio, 0)
                self.assertLess(card.poissons_ratio, 0.5)
                self.assertTrue(card.strength_basis)
                self.assertTrue(card.source_url.startswith("https://"))

    def test_cantilever_input_resolves_selected_card(self) -> None:
        for name in MATERIAL_NAMES:
            with self.subTest(material=name):
                card = get_material(name)
                inputs = CantileverInputs(material=name)
                inputs.validate()
                self.assertEqual(inputs.youngs_modulus_pa, card.youngs_modulus_pa)
                self.assertEqual(inputs.poissons_ratio, card.poissons_ratio)
                self.assertEqual(inputs.density_kg_m3, card.density_kg_m3)
                self.assertEqual(inputs.yield_strength_pa, card.reference_strength_pa)

    def test_example_input_resolves_selected_card(self) -> None:
        inputs = ExampleInputs(template="bolt", material="Aluminium Alloy 6061-T6")
        inputs.validate()
        self.assertEqual(inputs.youngs_modulus_pa, 68.9e9)
        self.assertEqual(inputs.density_kg_m3, 2700.0)

    def test_api_accepts_every_card_and_rejects_unknown_names(self) -> None:
        for name in MATERIAL_NAMES:
            with self.subTest(material=name):
                self.assertEqual(SimulationRequest(material=name).material, name)
        with self.assertRaises(ValidationError):
            SimulationRequest(material="Wood")


if __name__ == "__main__":
    unittest.main()
