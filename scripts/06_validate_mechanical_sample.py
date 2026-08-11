"""Open an official downloaded Mechanical sample and report its analyses.

This is intentionally a validation utility.  It proves that the project-file
workflow works before the web API is switched from its MAPDL-generated model.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

from ansys.mechanical.core import launch_mechanical


ROOT = Path(__file__).resolve().parents[1]
SAMPLES = {
    "cantilever": ROOT / "examples" / "mechanical" / "cantilever.mechdat",
    "bolt": ROOT
    / "examples"
    / "mechanical"
    / "example_03_simple_bolt_new.mechdat",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("sample", choices=sorted(SAMPLES), default="cantilever", nargs="?")
    parser.add_argument(
        "--details",
        action="store_true",
        help="Print the Mechanical object names and runtime types in the loaded sample.",
    )
    parser.add_argument(
        "--probe",
        action="store_true",
        help="Print editable load values and configured result objects.",
    )
    return parser.parse_args()


def escaped_for_mechanical(path: str) -> str:
    return path.replace("\\", "\\\\")


def main() -> int:
    args = parse_args()
    sample_path = SAMPLES[args.sample]
    if not sample_path.is_file():
        raise FileNotFoundError(f"Mechanical sample not found: {sample_path}")

    print(f"Launching Mechanical 2026 R1 for sample: {args.sample}")
    mechanical = launch_mechanical(
        version=261,
        batch=True,
        cleanup_on_exit=False,
        start_timeout=180,
    )

    try:
        project_directory = mechanical.project_directory
        mechanical.upload(
            file_name=str(sample_path),
            file_location_destination=project_directory,
        )
        remote_path = escaped_for_mechanical(
            os.path.join(project_directory, sample_path.name)
        )
        mechanical.run_python_script(f"sample_path=r'{remote_path}'")
        mechanical.run_python_script("ExtAPI.DataModel.Project.Open(sample_path)")

        product = mechanical.version
        count = mechanical.run_python_script("len(ExtAPI.DataModel.AnalysisList)")
        names = mechanical.run_python_script(
            "[analysis.Name for analysis in ExtAPI.DataModel.AnalysisList]"
        )

        print(f"Mechanical product version: {product}")
        print(f"Opened project: {sample_path.name}")
        print(f"Analysis count: {count}")
        print(f"Analyses: {names}")
        if args.details:
            objects = mechanical.run_python_script(
                "'\\n'.join(['{}|{}'.format(obj.Name, obj.GetType().Name) "
                "for obj in ExtAPI.DataModel.Tree.AllObjects])"
            )
            print("Mechanical objects:")
            print(objects)
        if args.probe:
            force_probe = mechanical.run_python_script(
                "force=ExtAPI.DataModel.GetObjectsByName('Nodal Force')[0]\n"
                "'X={}\\nY={}\\nZ={}'.format("
                "force.XComponent.Output.DiscreteValues, "
                "force.YComponent.Output.DiscreteValues, "
                "force.ZComponent.Output.DiscreteValues)"
            )
            result_probe = mechanical.run_python_script(
                "'\\n'.join(['{}|{}'.format(obj.Name, obj.GetType().Name) "
                "for obj in ExtAPI.DataModel.Tree.AllObjects "
                "if obj.GetType().Name in ['TotalDeformation', 'EquivalentStress']])"
            )
            print("Nodal Force component values:")
            print(force_probe)
            print("Configured results:")
            print(result_probe)
        print("VALIDATION PASSED: downloaded Mechanical project opened successfully")
        return 0
    finally:
        mechanical.exit(force=True)


if __name__ == "__main__":
    sys.exit(main())
