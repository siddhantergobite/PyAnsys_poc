"""Run the official downloaded cantilever Mechanical project.

This acceptance script proves the project-based path end to end:
open MECHDAT, update its existing Nodal Force, solve its existing analysis,
read its existing results, and export Mechanical result images.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

from ansys.mechanical.core import launch_mechanical


ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "examples" / "mechanical" / "cantilever.mechdat"
OUTPUT = ROOT / "output" / "mechanical_sample"


def escaped(path: str | Path) -> str:
    return str(path).replace("\\", "\\\\")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", type=float, default=1000.0)
    args = parser.parse_args()
    if args.force <= 0:
        raise ValueError("Force must be positive")
    if not SAMPLE.is_file():
        raise FileNotFoundError(SAMPLE)

    OUTPUT.mkdir(parents=True, exist_ok=True)
    stress_path = OUTPUT / "stress.png"
    deformation_path = OUTPUT / "deformation.png"

    print("Launching Mechanical 2026 R1...")
    mechanical = launch_mechanical(
        version=261,
        batch=True,
        cleanup_on_exit=False,
        start_timeout=180,
    )
    try:
        project_directory = mechanical.project_directory
        mechanical.upload(str(SAMPLE), project_directory)
        remote_sample = os.path.join(project_directory, SAMPLE.name)
        mechanical.run_python_script(f"sample_path=r'{escaped(remote_sample)}'")
        mechanical.run_python_script("ExtAPI.DataModel.Project.Open(sample_path)")
        print("Opened official downloaded project: cantilever.mechdat")

        script = f"""
force = ExtAPI.DataModel.GetObjectsByName('Nodal Force')[0]
force.YComponent.Output.SetDiscreteValue(0, Quantity('-{args.force:g} [N]'))
analysis = ExtAPI.DataModel.AnalysisList[0]
analysis.Solution.Solve(True)
analysis.Solution.EvaluateAllResults()
deformation = ExtAPI.DataModel.GetObjectsByName('Total Deformation')[0]
stress = ExtAPI.DataModel.GetObjectsByName('Equivalent Stress')[0]
stress.Activate()
Graphics.Camera.SetFit()
settings = Ansys.Mechanical.Graphics.GraphicsImageExportSettings()
settings.Background = Ansys.Mechanical.DataModel.Enums.GraphicsBackgroundType.White
settings.Width = 1280
settings.Height = 720
settings.CurrentGraphicsDisplay = False
Graphics.ExportImage(r'{escaped(stress_path)}', Ansys.Mechanical.DataModel.Enums.GraphicsImageExportFormat.PNG, settings)
deformation.Activate()
Graphics.Camera.SetFit()
Graphics.ExportImage(r'{escaped(deformation_path)}', Ansys.Mechanical.DataModel.Enums.GraphicsImageExportFormat.PNG, settings)
'{{}}|{{}}'.format(stress.Maximum, deformation.Maximum)
"""
        values = mechanical.run_python_script(script)
        print(f"Mechanical results (stress | deformation): {values}")
        print(f"Stress image: {stress_path}")
        print(f"Deformation image: {deformation_path}")
        if not stress_path.is_file() or not deformation_path.is_file():
            raise RuntimeError("Mechanical did not export both result images")
        print("ACCEPTANCE PASSED: downloaded project changed, solved, and exported")
        return 0
    finally:
        mechanical.exit(force=True)


if __name__ == "__main__":
    sys.exit(main())
