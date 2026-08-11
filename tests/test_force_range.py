import unittest

from pydantic import ValidationError

from app.api.main import SimulationRequest
from app.simulation.config import ForceRange


class ForceRangeTests(unittest.TestCase):
    def test_values_are_evenly_spaced_and_inclusive(self):
        force_range = ForceRange(start_n=100.0, end_n=500.0, steps=5)

        self.assertEqual(force_range.values(), (100.0, 200.0, 300.0, 400.0, 500.0))

    def test_equal_legacy_force_has_one_evaluation_point(self):
        force_range = ForceRange(start_n=250.0, end_n=250.0, steps=2)

        self.assertEqual(force_range.values(), (250.0,))

    def test_invalid_range_is_rejected(self):
        with self.assertRaises(ValueError):
            ForceRange(start_n=500.0, end_n=100.0, steps=5).validate()

    def test_api_maps_legacy_single_force_to_a_single_point_range(self):
        request = SimulationRequest(force_n=750.0)

        self.assertEqual(request.force_start_n, 750.0)
        self.assertEqual(request.force_end_n, 750.0)
        self.assertEqual(request.force_steps, 2)

    def test_api_rejects_descending_range(self):
        with self.assertRaises(ValidationError):
            SimulationRequest(force_start_n=800.0, force_end_n=100.0, force_steps=5)


if __name__ == "__main__":
    unittest.main()
