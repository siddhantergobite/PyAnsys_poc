"""MAPDL launch and shutdown helpers."""

from __future__ import annotations

import time
from pathlib import Path

import psutil
from ansys.mapdl.core import launch_mapdl


def launch_session(executable: Path, run_location: Path, jobname: str):
    """Launch a clean local MAPDL session for one PoC case."""

    executable = Path(executable)
    run_location = Path(run_location)
    if not executable.is_file():
        raise FileNotFoundError(f"MAPDL executable was not found: {executable}")

    run_location.mkdir(parents=True, exist_ok=True)
    # Do not request distributed-memory parallelism here.  The Student
    # installation is intended to use shared-memory MAPDL (SMP); explicitly
    # requesting DMP can make MAPDL ask for a license feature unavailable to
    # the Student edition.
    return launch_mapdl(
        exec_file=str(executable),
        run_location=str(run_location),
        jobname=jobname,
        override=True,
        timeout=120,
        cleanup_on_exit=True,
        remove_temp_dir_on_exit=False,
        additional_switches="-smp",
        loglevel="WARNING",
    )


def close_session(mapdl, jobname: str) -> None:
    """Close MAPDL and remove only the matching PoC solver process."""

    try:
        mapdl.exit(force=True)
    finally:
        marker = f"-j {jobname}".lower()
        for _ in range(10):
            matches = []
            for process in psutil.process_iter(["name", "cmdline"]):
                try:
                    name = (process.info["name"] or "").lower()
                    command = " ".join(process.info["cmdline"] or []).lower()
                    if name in {"ansys.exe", "mapdl.exe", "mpiexec.exe"} and marker in command:
                        matches.append(process)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            if not matches:
                return
            for process in matches:
                try:
                    process.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            time.sleep(0.2)
