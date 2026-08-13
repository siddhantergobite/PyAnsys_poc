import unittest

from app.simulation.config import CantileverInputs
from app.simulation.examples import ExampleInputs
from app.simulation.model_artifacts import _model_details


class ModelArtifactTests(unittest.TestCase):
    def test_cantilever_definition_identifies_parameter_built_model(self):
        text = "\n".join(_model_details(CantileverInputs()))

        self.assertIn("generated parametrically", text)
        self.assertIn("BEAM188", text)
        self.assertIn("SMISC 32/33", text)

    def test_axial_definition_states_product_limitations(self):
        text = "\n".join(_model_details(ExampleInputs(template="bolt")))

        self.assertIn("force divided by BEAM188 section area", text)
        self.assertIn("do not include threads", text)


if __name__ == "__main__":
    unittest.main()
