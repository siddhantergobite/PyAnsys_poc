import unittest

from pydantic import ValidationError

from app.api.main import SimulationRequest, templates
from app.simulation.official_examples import (
    OFFICIAL_TEMPLATE_DEFINITIONS,
    OfficialExampleInputs,
)


class OfficialExampleTests(unittest.TestCase):
    def test_official_templates_are_ordered_after_cantilever(self):
        names = list(templates())
        self.assertEqual(
            names[:4],
            ["cantilever", "corner_bracket", "plate_hole", "pressure_vessel"],
        )

    def test_api_accepts_all_official_template_names(self):
        for template in OFFICIAL_TEMPLATE_DEFINITIONS:
            with self.subTest(template=template):
                self.assertEqual(SimulationRequest(template=template).template, template)

    def test_plate_hole_validates_hole_size(self):
        with self.assertRaises(ValueError):
            OfficialExampleInputs(
                template="plate_hole", width_m=0.1, feature_diameter_m=0.1
            ).validate()

    def test_pressure_vessel_uses_pressure_units_and_radius_order(self):
        inputs = OfficialExampleInputs(
            template="pressure_vessel", length_m=0.175, width_m=0.2
        )
        inputs.validate()
        self.assertEqual(inputs.load_unit, "Pa")
        with self.assertRaises(ValueError):
            OfficialExampleInputs(
                template="pressure_vessel", length_m=0.2, width_m=0.175
            ).validate()

    def test_unknown_template_stays_rejected_at_api_boundary(self):
        with self.assertRaises(ValidationError):
            SimulationRequest(template="unofficial")


if __name__ == "__main__":
    unittest.main()
