import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from app.simulation.assessment import (
    add_assessment_footer,
    add_force_response_inset,
    assess_failure,
    export_failure_assessment_image,
    export_force_sweep_image,
)


def make_assessment(*, stress_pa: float, displacement_m: float):
    return assess_failure(
        force_n=1000.0,
        maximum_stress_pa=stress_pa,
        reference_strength_pa=40_000_000.0,
        maximum_displacement_m=displacement_m,
        deformation_reference_length_m=1.0,
        critical_stress_location="element 1",
        critical_displacement_location="node 2",
        load_application_location="free end",
    )


class FailureAssessmentTests(unittest.TestCase):
    def test_result_within_reference_strength(self):
        result = make_assessment(stress_pa=20_000_000.0, displacement_m=0.01)

        self.assertEqual(result.failure_status, "within_reference_strength")
        self.assertEqual(result.breakage_assessment, "not_indicated_at_applied_load")
        self.assertFalse(result.large_deformation_warning)
        self.assertAlmostEqual(result.estimated_failure_load_n, 2000.0)
        self.assertEqual(result.governing_screening_criterion, "reference strength")
        self.assertEqual(len(result.failure_summary), 3)

    def test_reference_strength_exceeded(self):
        result = make_assessment(stress_pa=80_000_000.0, displacement_m=0.01)

        self.assertEqual(result.failure_status, "likely_failure_or_yielding")
        self.assertEqual(result.breakage_assessment, "likely_before_or_at_applied_load")
        self.assertGreaterEqual(result.stress_utilization, 1.0)
        self.assertAlmostEqual(result.estimated_failure_load_n, 500.0)

    def test_large_deformation_is_reported(self):
        result = make_assessment(stress_pa=20_000_000.0, displacement_m=0.2)

        self.assertEqual(result.failure_status, "large_deformation_warning")
        self.assertEqual(
            result.breakage_assessment,
            "not_determinable_due_to_large_deformation",
        )
        self.assertTrue(result.large_deformation_warning)
        self.assertAlmostEqual(result.estimated_deformation_limit_load_n, 500.0)
        self.assertEqual(
            result.governing_screening_criterion,
            "10% deformation validity limit",
        )

    def test_shared_plot_annotations_render_for_a_force_curve(self):
        assessment = make_assessment(stress_pa=80_000_000.0, displacement_m=0.2)
        force_curve = [
            {
                "force_n": 500.0,
                "maximum_stress_pa": 20_000_000.0,
                "maximum_displacement_m": 0.05,
                "failure_status": "within_reference_strength",
            },
            {
                "force_n": 1000.0,
                "maximum_stress_pa": 80_000_000.0,
                "maximum_displacement_m": 0.2,
                "failure_status": "likely_failure_or_yielding",
            },
        ]
        figure = plt.figure(figsize=(8, 5))
        try:
            add_force_response_inset(
                figure,
                position=[0.55, 0.35, 0.35, 0.3],
                force_curve=force_curve,
                reference_strength_pa=40_000_000.0,
                break_force_n=750.0,
                deformation_reference_length_m=1.0,
                response="stress",
            )
            add_assessment_footer(
                figure,
                force_n=1000.0,
                reference_strength_pa=40_000_000.0,
                assessment=assessment,
                break_force_n=750.0,
            )
            self.assertEqual(len(figure.axes), 1)
            self.assertGreaterEqual(len(figure.patches), 1)
        finally:
            plt.close(figure)

    def test_report_images_export_separately(self):
        with TemporaryDirectory() as temporary_directory:
            output_dir = Path(temporary_directory)
            assessment = make_assessment(stress_pa=80_000_000.0, displacement_m=0.2)
            failure_name = export_failure_assessment_image(
                output_dir,
                template="Cantilever beam",
                material="ABS Plastic",
                force_n=1000.0,
                maximum_stress_pa=80_000_000.0,
                maximum_displacement_m=0.2,
                reference_strength_pa=40_000_000.0,
                assessment=assessment,
                break_force_n=500.0,
            )
            sweep_name = export_force_sweep_image(
                output_dir,
                curve=[
                    {"force_n": 500.0, "maximum_stress_pa": 20_000_000.0, "maximum_displacement_m": 0.05, "failure_status": "within_reference_strength"},
                    {"force_n": 1000.0, "maximum_stress_pa": 80_000_000.0, "maximum_displacement_m": 0.2, "failure_status": "likely_failure_or_yielding"},
                ],
                reference_strength_pa=40_000_000.0,
                strength_basis="yield strength",
                break_force_n=750.0,
            )
            self.assertEqual(failure_name, "failure_assessment.png")
            self.assertEqual(sweep_name, "force_sweep.png")
            self.assertGreater((output_dir / failure_name).stat().st_size, 1000)
            self.assertGreater((output_dir / sweep_name).stat().st_size, 1000)


if __name__ == "__main__":
    unittest.main()
