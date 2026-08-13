"""Minimal API for the verified PyAnsys example templates."""

from __future__ import annotations

from contextlib import asynccontextmanager
import threading
import math
import os
from time import perf_counter
from pathlib import Path
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator, model_validator

from app.simulation.cantilever import solve_cantilever_range
from app.simulation.config import CantileverInputs, ForceRange, get_paths
from app.simulation.examples import (
    TEMPLATE_DEFINITIONS,
    ExampleInputs,
    solve_example_range,
)
from app.simulation.mapdl_session import (
    active_api_session_pids,
    close_session,
    launch_session,
    terminate_job_processes,
    terminate_stale_api_sessions,
)
from app.simulation.materials import get_material, material_catalog_payload
from app.simulation.model_artifacts import export_model_artifacts
from app.simulation.official_examples import (
    OFFICIAL_TEMPLATE_DEFINITIONS,
    OfficialExampleInputs,
    solve_official_example_range,
)
from app.simulation.results import write_result_files


OUTPUT_ROOT = get_paths("api_bootstrap").output_root / "api"
OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
RUN_LOCK = threading.Lock()
MAPDL_SESSION = None
MAPDL_JOBNAME = f"api_warm_{os.getpid()}"


def _launch_api_session():
    """Launch the one warm MAPDL process shared by serialized API requests."""

    paths = get_paths(MAPDL_JOBNAME)
    other_api_pids = active_api_session_pids() - {os.getpid()}
    if other_api_pids:
        owners = ", ".join(str(pid) for pid in sorted(other_api_pids))
        raise RuntimeError(
            f"Another PyAnsys API already owns the warm MAPDL session (PID {owners}). "
            "Use the existing backend instead of starting a second one."
        )
    # A force-killed development server cannot execute its lifespan cleanup.
    # Remove only a stale process carrying this API's dedicated MAPDL jobname.
    terminate_job_processes("api_warm")  # legacy pre-PID warm-session name
    terminate_stale_api_sessions()
    terminate_job_processes(MAPDL_JOBNAME)
    return launch_session(paths.mapdl_executable, paths.run_root, MAPDL_JOBNAME)


def _session_is_alive(mapdl) -> bool:
    try:
        return bool(mapdl is not None and mapdl.is_alive)
    except Exception:
        return False


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Pre-warm MAPDL once and release it when the API shuts down."""

    global MAPDL_SESSION
    MAPDL_SESSION = _launch_api_session()
    try:
        yield
    finally:
        if MAPDL_SESSION is not None:
            close_session(MAPDL_SESSION, MAPDL_JOBNAME)
            MAPDL_SESSION = None


app = FastAPI(title="PyAnsys Structural PoC", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/artifacts", StaticFiles(directory=OUTPUT_ROOT), name="artifacts")


class SimulationRequest(BaseModel):
    """Positive finite example inputs in SI units."""

    case_id: str = Field(default="api_case", pattern=r"^[A-Za-z0-9_-]{1,32}$")
    template: Literal[
        "cantilever", "corner_bracket", "plate_hole", "pressure_vessel",
        "table", "bolt", "screw", "nut",
    ] = "cantilever"
    # ``force_n`` remains accepted for existing API clients. New runs use an
    # explicit start/end/increment sweep for every supported template.
    # Physical values intentionally have no arbitrary upper cap. The solver
    # still requires positive, finite values; a zero-length or zero-section
    # model is not a valid structural model.
    force_n: float | None = Field(default=None, gt=0)
    force_start_n: float = Field(default=100.0, gt=0)
    force_end_n: float = Field(default=1000.0, gt=0)
    force_increment_n: float = Field(default=100.0, gt=0)
    force_steps: int | None = Field(default=None, ge=2, le=1001)
    length_m: float = Field(default=1.0, gt=0)
    width_m: float = Field(default=0.1, gt=0)
    height_m: float = Field(default=0.1, gt=0)
    diameter_m: float = Field(default=0.01, gt=0)
    mesh_size_m: float = Field(default=0.05, gt=0)
    material: str = "Structural Steel"

    @field_validator("material")
    @classmethod
    def validate_material(cls, value: str) -> str:
        get_material(value)
        return value

    @field_validator(
        "force_n",
        "force_start_n",
        "force_end_n",
        "force_increment_n",
        "length_m",
        "width_m",
        "height_m",
        "diameter_m",
        "mesh_size_m",
    )
    @classmethod
    def validate_finite_number(cls, value):
        if value is not None and not math.isfinite(value):
            raise ValueError("must be a finite number")
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
        mapped["force_increment_n"] = mapped["force_n"]
        return mapped

    @model_validator(mode="before")
    @classmethod
    def map_legacy_steps_to_increment(cls, values):
        """Translate the previous evenly-spaced API contract."""

        if not isinstance(values, dict):
            return values
        if "force_increment_n" in values or "force_steps" not in values:
            return values
        mapped = dict(values)
        start = float(mapped.get("force_start_n", 100.0))
        end = float(mapped.get("force_end_n", 1000.0))
        steps = int(mapped["force_steps"])
        mapped["force_increment_n"] = (end - start) / (steps - 1) if end > start else 1.0
        return mapped

    @model_validator(mode="after")
    def validate_force_range(self):
        ForceRange(self.force_start_n, self.force_end_n, self.force_increment_n).validate()
        return self


@app.get("/health")
def health() -> dict[str, str | bool]:
    return {
        "status": "ok",
        "solver": "PyMAPDL",
        "mapdl_session_warm": _session_is_alive(MAPDL_SESSION),
    }


@app.get("/templates")
def templates() -> dict:
    """Return the intentionally supported model templates."""

    return {
        "cantilever": {
            "name": "Cantilever beam",
            "description": "Mandatory BRD Phase 1 beam template",
            "provenance": "brd_reference_model",
            "element_type": "BEAM188",
        },
        **OFFICIAL_TEMPLATE_DEFINITIONS,
        **TEMPLATE_DEFINITIONS,
    }


@app.get("/materials")
def materials() -> dict[str, list[dict]]:
    """Return the exact material cards accepted by the solver."""

    return {"materials": material_catalog_payload()}


@app.post("/simulate")
def simulate(request: SimulationRequest) -> dict:
    """Run one controlled MAPDL job and return result file URLs."""

    request_started = perf_counter()
    run_id = f"{request.case_id}_{uuid4().hex[:8]}"
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
    elif request.template in OFFICIAL_TEMPLATE_DEFINITIONS:
        inputs = OfficialExampleInputs(
            template=request.template,
            case_id=request.case_id,
            load_value=request.force_end_n,
            length_m=request.length_m,
            width_m=request.width_m,
            thickness_m=request.height_m,
            feature_diameter_m=request.diameter_m,
            mesh_size_m=request.mesh_size_m,
            material=request.material,
        )
    else:
        inputs = ExampleInputs(
            template=request.template,
            case_id=request.case_id,
            force_n=request.force_end_n,
            length_m=request.length_m,
            width_m=request.width_m,
            height_m=request.height_m,
            diameter_m=request.diameter_m,
            mesh_size_m=request.mesh_size_m,
            material=request.material,
        )
    with RUN_LOCK:
        lock_acquired = perf_counter()
        try:
            global MAPDL_SESSION
            inputs.validate()
            if not _session_is_alive(MAPDL_SESSION):
                MAPDL_SESSION = _launch_api_session()
            if request.template == "cantilever":
                result = solve_cantilever_range(
                    MAPDL_SESSION,
                    inputs,
                    ForceRange(
                        start_n=request.force_start_n,
                        end_n=request.force_end_n,
                        increment_n=request.force_increment_n,
                    ),
                    output_dir,
                )
            elif request.template in OFFICIAL_TEMPLATE_DEFINITIONS:
                result = solve_official_example_range(
                    MAPDL_SESSION,
                    inputs,
                    ForceRange(
                        start_n=request.force_start_n,
                        end_n=request.force_end_n,
                        increment_n=request.force_increment_n,
                    ),
                    output_dir,
                )
            else:
                result = solve_example_range(
                    MAPDL_SESSION,
                    inputs,
                    ForceRange(
                        start_n=request.force_start_n,
                        end_n=request.force_end_n,
                        increment_n=request.force_increment_n,
                    ),
                    output_dir,
                )
            # Keep these artifacts inside the private run directory for
            # internal audit/debugging, but do not expose their filenames in
            # the public result JSON or download manifest.
            export_model_artifacts(MAPDL_SESSION, inputs, output_dir)
            material_card = get_material(request.material)
            result.material_source_url = material_card.source_url
            result.material_data_origin = "application_catalog_external_reference"
            result.threshold_load_value = result.break_force_n
            result.threshold_load_unit = result.load_unit
            write_result_files(result, output_dir)
        except Exception as exc:  # surface solver failures as API errors
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    relative = f"/artifacts/{run_id}"
    files = {
        "csv": f"{relative}/results.csv",
        "json": f"{relative}/results.json",
        "stress_image": f"{relative}/stress.png",
        "deformation_image": f"{relative}/deformation.png",
    }
    if result.failure_assessment_image:
        files["failure_assessment_image"] = f"{relative}/{result.failure_assessment_image}"
    if result.sweep_image:
        files["force_sweep_image"] = f"{relative}/{result.sweep_image}"
    # The readable MAPDL definition and native database are retained inside
    # the run directory for internal audit/debugging, but are intentionally
    # not published as user-facing download links.
    completed = perf_counter()
    return {
        "run_id": run_id,
        "result": result.as_dict(),
        "files": files,
        "timing_seconds": {
            "queue": round(lock_acquired - request_started, 4),
            "simulation_and_artifacts": round(completed - lock_acquired, 4),
            "total": round(completed - request_started, 4),
        },
        "mapdl_session_reused": True,
    }
