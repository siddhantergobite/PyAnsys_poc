"""End-to-end API acceptance test for the warm MAPDL session and downloads."""

from __future__ import annotations

import json
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
API = "http://127.0.0.1:8000"

CASES = {
    "cantilever": dict(length_m=1.0, width_m=0.1, height_m=0.1, diameter_m=0.01, mesh_size_m=0.05),
    "table": dict(length_m=1.2, width_m=0.6, height_m=0.75, diameter_m=0.04, mesh_size_m=0.05),
    "bolt": dict(length_m=0.08, width_m=0.1, height_m=0.1, diameter_m=0.01, mesh_size_m=0.01),
    "screw": dict(length_m=0.06, width_m=0.1, height_m=0.1, diameter_m=0.006, mesh_size_m=0.01),
    "nut": dict(length_m=0.02, width_m=0.1, height_m=0.1, diameter_m=0.014, mesh_size_m=0.005),
}

REQUIRED_FILES = (
    "results.csv", "results.json", "stress.png", "deformation.png",
    "failure_assessment.png", "force_sweep.png", "model_definition.txt", "model.db",
)


def _get(path: str):
    with urlopen(f"{API}{path}", timeout=10) as response:
        return json.load(response)


def _post(payload: dict):
    request = Request(
        f"{API}/simulate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=120) as response:
            return json.load(response)
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"API returned HTTP {error.code}: {detail}") from error


def main() -> None:
    health = _get("/health")
    if not health.get("mapdl_session_warm"):
        raise AssertionError("API health does not report a warm MAPDL session")

    report = []
    for template, dimensions in CASES.items():
        payload = {
            "case_id": f"warm_{template}",
            "template": template,
            "force_start_n": 100.0,
            "force_end_n": 1000.0,
            "force_steps": 3,
            "material": "Structural Steel",
            **dimensions,
        }
        started = time.perf_counter()
        response = _post(payload)
        client_seconds = time.perf_counter() - started
        result = response["result"]
        run_dir = ROOT / "output" / "api" / response["run_id"]
        missing = [name for name in REQUIRED_FILES if not (run_dir / name).is_file()]
        if missing:
            raise AssertionError(f"{template}: missing artifacts {missing}")
        if len(result.get("force_curve") or []) != 3:
            raise AssertionError(f"{template}: expected three MAPDL points")
        if not response.get("mapdl_session_reused"):
            raise AssertionError(f"{template}: MAPDL session was not reported as reused")
        timing = response.get("timing_seconds") or {}
        if timing.get("total", 0) <= 0:
            raise AssertionError(f"{template}: missing server timing")
        report.append({
            "template": template,
            "points": 3,
            "server_seconds": timing["total"],
            "client_seconds": round(client_seconds, 4),
            "database_bytes": (run_dir / "model.db").stat().st_size,
            "status": "passed",
        })
        print(f"PASS {template}: server={timing['total']:.3f}s, client={client_seconds:.3f}s")

    report_path = ROOT / "output" / "api_warm_verification.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"PASS: {len(report)} templates through one warm MAPDL API session")
    print(f"Acceptance report: {report_path}")


if __name__ == "__main__":
    main()
