import unittest

from pydantic import ValidationError

from app.api.main import SimulationRequest
from app.simulation.cantilever import (
    _estimate_linear_threshold_force,
    _first_strength_crossing,
)
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

    def test_api_has_no_arbitrary_upper_cap_on_physical_values(self):
        request = SimulationRequest(
            force_start_n=1.0e9,
            force_end_n=2.0e9,
            length_m=10.0,
            width_m=2.0,
            height_m=3.0,
            diameter_m=1.0,
            mesh_size_m=0.25,
        )

        self.assertEqual(request.force_end_n, 2.0e9)
        self.assertEqual(request.length_m, 10.0)

    def test_zero_geometry_is_still_rejected(self):
        with self.assertRaises(ValidationError):
            SimulationRequest(length_m=0.0)

    def test_crossing_inside_range_is_interpolated(self):
        curve = [
            {"force_n": 100.0, "maximum_stress_pa": 10.0},
            {"force_n": 500.0, "maximum_stress_pa": 50.0},
        ]

        self.assertAlmostEqual(_first_strength_crossing(curve, 40.0), 400.0)

    def test_range_start_above_threshold_does_not_become_threshold(self):
        curve = [
            {"force_n": 500.0, "maximum_stress_pa": 50.0},
            {"force_n": 1000.0, "maximum_stress_pa": 100.0},
        ]

        self.assertIsNone(_first_strength_crossing(curve, 40.0))
        self.assertAlmostEqual(_estimate_linear_threshold_force(curve, 40.0), 400.0)

if __name__ == "__main__":
    unittest.main()
