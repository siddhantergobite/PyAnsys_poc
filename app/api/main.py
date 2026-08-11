"""Minimal API for the verified PyAnsys example templates."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator, model_validator

from app.simulation.cantilever import solve_cantilever_range
from app.simulation.config import CantileverInputs, ForceRange, get_paths
from app.simulation.examples import TEMPLATE_DEFINITIONS, ExampleInputs, solve_example
from app.simulation.mapdl_session import close_session, launch_session
from app.simulation.materials import get_material, material_catalog_payload
from app.simulation.results import write_result_files


OUTPUT_ROOT = get_paths("api_bootstrap").output_root / "api"
OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
RUN_LOCK = threading.Lock()

app = FastAPI(title="PyAnsys Structural PoC", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/artifacts", StaticFiles(directory=OUTPUT_ROOT), name="artifacts")


class SimulationRequest(BaseModel):
    """Bounded example inputs; units are SI."""

    case_id: str = Field(default="api_case", pattern=r"^[A-Za-z0-9_-]{1,32}$")
    template: Literal["cantilever", "table", "bolt", "screw", "nut"] = "cantilever"
    # ``force_n`` remains accepted for existing API clients. New cantilever
    # runs use the bounded start/end/steps force sweep below.
    force_n: float | None = Field(default=None, gt=0, le=100000)
    force_start_n: float = Field(default=100.0, gt=0, le=100000)
    force_end_n: float = Field(default=1000.0, gt=0, le=100000)
    force_steps: int = Field(default=5, ge=2, le=21)
    length_m: float = Field(default=1.0, gt=0, le=2.0)
    width_m: float = Field(default=0.1, gt=0, le=1.5)
    height_m: float = Field(default=0.1, gt=0, le=1.5)
    diameter_m: float = Field(default=0.01, gt=0, le=0.25)
    mesh_size_m: float = Field(default=0.05, gt=0, le=0.5)
    material: str = "Structural Steel"

    @field_validator("material")
    @classmethod
    def validate_material(cls, value: str) -> str:
        get_material(value)
        return value

    @model_validator(mode="before")
    @classmethod
    def map_legacy_force(cls, values):
        """Allow the earlier single-force API payload without changing clients."""

        if not isinstance(values, dict):
            return values
        if values.get("force_n") is None or "force_start_n" in values or "force_end_n" in values:
            return values
        mapped = dict(values)
        mapped["force_start_n"] = mapped["force_n"]
        mapped["force_end_n"] = mapped["force_n"]
        mapped["force_steps"] = 2
        return mapped

    @model_validator(mode="after")
    def validate_force_range(self):
        ForceRange(self.force_start_n, self.force_end_n, self.force_steps).validate()
        return self


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "solver": "PyMAPDL"}


@app.get("/templates")
def templates() -> dict:
    """Return the intentionally supported model templates."""

    return {
        "cantilever": {
            "name": "Cantilever beam",
            "description": "Mandatory BRD Phase 1 beam template",
        },
        **TEMPLATE_DEFINITIONS,
    }


@app.get("/materials")
def materials() -> dict[str, list[dict]]:
    """Return the exact material cards accepted by the solver."""

    return {"materials": material_catalog_payload()}


@app.post("/simulate")
def simulate(request: SimulationRequest) -> dict:
    """Run one controlled MAPDL job and return result file URLs."""

    run_id = f"{request.case_id}_{uuid4().hex[:8]}"
    jobname = f"api_{uuid4().hex[:8]}"
    paths = get_paths(run_id)
    output_dir = OUTPUT_ROOT / run_id
    if request.template == "cantilever":
        inputs = CantileverInputs(
            case_id=request.case_id,
            force_n=request.force_end_n,
            length_m=request.length_m,
            width_m=request.width_m,
            height_m=request.height_m,
            mesh_size_m=request.mesh_size_m,
            material=request.material,
        )
    else:
        inputs = ExampleInputs(
            template=request.template,
            case_id=request.case_id,
            force_n=request.force_n or request.force_end_n,
            length_m=request.length_m,
            width_m=request.width_m,
            height_m=request.height_m,
            diameter_m=request.diameter_m,
            mesh_size_m=request.mesh_size_m,
            material=request.material,
        )
    mapdl = None

    with RUN_LOCK:
        try:
            inputs.validate()
            mapdl = launch_session(paths.mapdl_executable, paths.run_root, jobname)
            if request.template == "cantilever":
                result = solve_cantilever_range(
                    mapdl,
                    inputs,
                    ForceRange(
                        start_n=request.force_start_n,
                        end_n=request.force_end_n,
                        steps=request.force_steps,
                    ),
                    output_dir,
                )
            else:
                result = solve_example(mapdl, inputs, output_dir)
            write_result_files(result, output_dir)
        except Exception as exc:  # surface solver failures as API errors
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        finally:
            if mapdl is not None:
                close_session(mapdl, jobname)

    relative = f"/artifacts/{run_id}"
    files = {
        "csv": f"{relative}/results.csv",
        "json": f"{relative}/results.json",
        "stress_image": f"{relative}/stress.png",
        "deformation_image": f"{relative}/deformation.png",
    }
    if result.sweep_image:
        files["force_sweep_image"] = f"{relative}/force_sweep.png"

    return {
        "run_id": run_id,
        "result": result.as_dict(),
        "files": files,
    }
