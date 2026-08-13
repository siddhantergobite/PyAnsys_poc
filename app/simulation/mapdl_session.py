"""MAPDL launch and shutdown helpers."""

from __future__ import annotations
import re
import time
from pathlib import Path
import psutil
from ansys.mapdl.core import launch_mapdl


def terminate_job_processes(jobname: str) -> None:
    """Terminate only MAPDL processes carrying the exact requested job marker."""

    marker = f"-j {jobname}".lower()
    for process in psutil.process_iter(["name", "cmdline"]):
        try:
            name = (process.info["name"] or "").lower()
            command = " ".join(process.info["cmdline"] or []).lower()
            if name in {"ansys.exe", "mapdl.exe", "mpiexec.exe", "ansyscl.exe"} and marker in command:
                process.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue


def terminate_stale_api_sessions(job_prefix: str = "api_warm_") -> None:
    """Remove orphaned warm MAPDL jobs without touching a live API's job."""

    python_processes: dict[int, str] = {}
    for process in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            if (process.info["name"] or "").lower() == "python.exe":
                python_processes[int(process.info["pid"])] = " ".join(
                    process.info["cmdline"] or []
                ).lower()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    pattern = re.compile(rf"-j\s+{re.escape(job_prefix.lower())}(\d+)")
    stale_jobnames: set[str] = set()
    for process in psutil.process_iter(["name", "cmdline"]):
        try:
            name = (process.info["name"] or "").lower()
            if name not in {"ansys.exe", "mapdl.exe", "mpiexec.exe"}:
                continue
            command = " ".join(process.info["cmdline"] or []).lower()
            match = pattern.search(command)
            if not match:
                continue
            api_pid = int(match.group(1))
            api_command = python_processes.get(api_pid, "")
            if "uvicorn" not in api_command or "app.api.main:app" not in api_command:
                stale_jobnames.add(f"{job_prefix}{api_pid}")
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    for jobname in stale_jobnames:
        terminate_job_processes(jobname)


def active_api_session_pids(job_prefix: str = "api_warm_") -> set[int]:
    """Return live API PIDs that currently own a warm MAPDL process."""

    python_processes: dict[int, str] = {}
    for process in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            if (process.info["name"] or "").lower() == "python.exe":
                python_processes[int(process.info["pid"])] = " ".join(
                    process.info["cmdline"] or []
                ).lower()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    pattern = re.compile(rf"-j\s+{re.escape(job_prefix.lower())}(\d+)")
    owners: set[int] = set()
    for process in psutil.process_iter(["name", "cmdline"]):
        try:
            if (process.info["name"] or "").lower() not in {"ansys.exe", "mapdl.exe"}:
                continue
            command = " ".join(process.info["cmdline"] or []).lower()
            match = pattern.search(command)
            if not match:
                continue
            api_pid = int(match.group(1))
            api_command = python_processes.get(api_pid, "")
            if "uvicorn" in api_command and "app.api.main:app" in api_command:
                owners.add(api_pid)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return owners

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
