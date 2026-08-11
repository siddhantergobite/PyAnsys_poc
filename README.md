# PyAnsys Automation PoC

This repository implements the solver-first proof of concept from the supplied
PyAnsys BRD: launch MAPDL from Python, run bounded structural templates, change
approved inputs without GUI interaction, and export repeatable results.

The current implementation intentionally uses PyMAPDL and the Student-compatible
BEAM188 element. It controls a MAPDL solver session, not an already-open
Mechanical Workbench window. For BEAM188, the stress result is the maximum
extreme-fiber bending stress read from the element SMISC results, while the
displacement is extracted from nodal results.

## Environment

- Windows
- Python 3.11+
- Ansys Student 2026 R1
- PyMAPDL 0.73.2

The default executable is:

```text
D:\ANSYS Inc\ANSYS Student\v261\ansys\bin\winx64\MAPDL.exe
```

You can override it without changing source code:

```powershell
$env:PYANSYS_MAPDL_EXECUTABLE = 'D:\path\to\MAPDL.exe'
$env:PYANSYS_MAPDL_RUN_ROOT = 'D:\AnsysProjects\pyansys-poc\mapdl_runs'
```

## Setup

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Close Workbench and Mechanical before the first local MAPDL launch.

## Run order

Run all commands from the repository root.

### 0. Preflight

Before every local solver test, run:

```powershell
python scripts\00_preflight.py
```

Close Workbench and Mechanical if the preflight reports them. The Student
edition has a limited demo license; an open Mechanical GUI can consume the
license needed by the MAPDL solve. Connectivity alone is not enough to prove
that a structural solve can obtain the license.

### 1. Connectivity

```powershell
python scripts\01_connectivity.py
```

This starts MAPDL, prints its version, writes
`output\connectivity\connectivity.json`, and closes the session.

### 2. Single cantilever

```powershell
python scripts\02_single_cantilever.py
```

Outputs are written to `output\single`:

- `results.csv`
- `results.json`
- `stress.png`
- `deformation.png`

The stress image uses the same BEAM188 extreme-fibre stress values written to
CSV/JSON, in MPa. The deformation image uses the same MAPDL nodal displacement
results written to CSV/JSON, in millimetres. This keeps the legends, displayed
maximums, and downloaded numeric results consistent.

### 3. Batch cases

```powershell
python scripts\03_batch_cantilever.py
```

The five approved cases are defined in `input\cases.csv`. Each case gets its
own folder under `output\batch`, and the aggregate file is
`output\batch\results.csv`.

### 4. Minimal API

Install the requirements, then start the API from the repository root:

```powershell
python -m uvicorn app.api.main:app --host 127.0.0.1 --port 8000
```

Check `http://127.0.0.1:8000/docs`, or submit the approved inputs to
`POST /simulate`. The API returns result values plus URLs for CSV, JSON,
stress, and deformation files. The solver is protected by a single-worker
lock because the Student license and this PoC are intentionally single-job.

The minimal React dashboard is under `frontend`. In a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open the displayed Vite URL, keep the API running on port 8000, and submit the
form. The browser form calls FastAPI; FastAPI calls the reusable PyMAPDL
service; MAPDL solves and returns the artifact links.

### 5. Additional bounded examples

The mandatory BRD template remains the cantilever beam. The repository also
contains four deliberately simplified extension templates so the dashboard can
demonstrate template selection and parameter updates:

- `table`: four-leg beam frame with a centre top load
- `bolt`: solid axial shank surrogate
- `screw`: solid axial shank surrogate
- `nut`: annular axial compression surrogate

These are not validated CAD/contact/thread models. They are PoC examples for
proving that a selected template receives input values, solves, and returns
CSV/JSON/images. Run all four locally with:

```powershell
python scripts\04_example_templates.py
```

The approved demonstration inputs are in `input\example_cases.csv`, and the
aggregate CSV is written to `output\examples\results.csv`. The API exposes the
same templates through `GET /templates`; select one with the `template` field
in `POST /simulate`.

### 6. Controlled materials

The API and dashboard accept five explicit linear-isotropic material cards:

- Structural Steel
- Stainless Steel 304
- Aluminium Alloy 6061-T6
- Titanium Alloy Ti-6Al-4V
- ABS Plastic (TECARAN natural approximation)

Their elastic modulus, Poisson ratio, density, reference strength, basis, and
source are defined once in `app/simulation/materials.py`. Generic wood is
deliberately excluded because its properties depend on species, grain
direction, moisture, and orthotropic behaviour.

Run the complete material acceptance matrix with Mechanical/Workbench closed:

```powershell
python -m unittest discover -s tests -v
python scripts\05_verify_materials.py
```

The real MAPDL report is written to
`output\material_verification\verification.csv`. For the force-controlled
cantilever, bending stress is governed by load and geometry, while displacement
changes with elastic modulus and the safety factor changes with the card's
documented reference strength.

## First-template inputs

The initial BEAM188 template uses SI units and one selected controlled material:

- Force: 100, 250, 500, 750, or 1000 N
- Beam length: 1.0 m
- Rectangular section width: 0.1 m
- Rectangular section height: 0.1 m
- Fixed support at one end
- Distributed force over the opposite end face

The input dataclass validates positive dimensions, valid Poisson ratio, and
positive material properties before MAPDL is launched.

## Controlled material cards

The dashboard and API accept five named, fixed PoC cards:

- Structural Steel
- Stainless Steel 304
- Aluminium Alloy 6061-T6
- Titanium Alloy Ti-6Al-4V
- ABS Plastic

Each card supplies MAPDL with its own elastic modulus, Poisson ratio, and
density. Its named reference strength is used by Python to calculate the
reported safety factor. The same values and strength basis are written to CSV
and JSON so a material change can be audited. Generic wood is deliberately not
included because its structural properties cannot be represented responsibly
without species, grade, grain direction, and moisture data.

Run the exact five-material acceptance matrix with Workbench/Mechanical closed:

```powershell
python scripts\05_verify_materials.py
```

The script solves one 1000 N cantilever per material, compares MAPDL stress and
displacement with beam-reference equations, verifies the safety-factor
arithmetic, checks all four artifacts, and writes
`output\material_verification\verification.csv`.

## BRD boundary

The mandatory PoC is the Python/PyMAPDL workflow and CSV/JSON/image output for
the cantilever. FastAPI and React are later-phase foundations in this local
repository. The additional table/bolt/screw/nut templates are demonstration
extensions; a production workflow would require separately validated geometry,
materials, supports, contacts, load cases, and acceptance tests for each
product.

## Known troubleshooting point

If MAPDL starts but exits during `SOLVE` with `No such feature exists` or
`Maximum licensed number of demo users already reached`, close all Ansys GUI
windows and rerun the preflight. The detailed MAPDL logs are stored under
`D:\AnsysProjects\pyansys-poc\mapdl_runs`.
