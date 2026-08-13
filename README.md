# PyAnsys Structural Simulation PoC

This project is a local FastAPI + React application that builds and solves eight
parameter-driven structural templates with Ansys MAPDL through PyMAPDL:

- Cantilever beam
- Ansys corner bracket (official PyMAPDL example adaptation)
- Ansys plate with a hole (official PyMAPDL example adaptation)
- Ansys pressure vessel (official PyMAPDL example adaptation)
- Table frame
- Bolt shank surrogate
- Screw shank surrogate
- Nut annular-section surrogate

Every template supports a start load, end load, and 2-21 requested checks.
Each point is solved by MAPDL. The application returns solver results, a
point-by-point force curve, screening information, images, CSV/JSON files, a
readable model definition, and the final native MAPDL database.

## Important engineering scope

This is a linear-elastic proof of concept, not a certified product failure
model. It can report:

- maximum stress and displacement;
- reference-strength utilization and safety factor;
- the location of the largest reported stress/displacement;
- an estimated load at the selected material's reference strength;
- a warning when displacement exceeds 10% of the model reference dimension.

The reference-strength load is an elastic screening threshold. It is not an
exact physical fracture load. Exact breakage requires validated product CAD,
contacts, boundary conditions, nonlinear material curves, imperfections,
thread/joint details, and an appropriate failure criterion.

## Model origin and official-example provenance

Every runtime model is generated parametrically through PyMAPDL. Three models
adapt official Ansys examples; the original downloaded MIT-licensed source
files are archived under `examples/official_ansys` for traceability. The API
uses adapted functions so it can reuse the warm MAPDL session, accept SI
parameters, and produce the project's standard JSON/CSV/images.

| Dashboard template | Runtime source | MAPDL abstraction |
|---|---|---|
| Cantilever | `app/simulation/cantilever.py` | Rectangular BEAM188 line model |
| Ansys corner bracket | `app/simulation/official_examples.py` | PLANE183 plane-stress model with thickness |
| Ansys plate with hole | `app/simulation/official_examples.py` | PLANE183 plane-stress model with thickness |
| Ansys pressure vessel | `app/simulation/official_examples.py` | PLANE182 plane-strain quarter-annulus model |
| Table frame | `app/simulation/examples.py` | Four-leg/top-member BEAM188 frame |
| Bolt | `app/simulation/examples.py` | Solid circular BEAM188 axial shank |
| Screw | `app/simulation/examples.py` | Solid circular BEAM188 axial shank |
| Nut | `app/simulation/examples.py` | Annular BEAM188 axial section |

The bolt, screw, and nut are deliberately simplified shank/section surrogates.
They do not include threads, preload, heads, washers, contact, friction, or
stress concentration. The table is a beam frame, not a solid/contact assembly.

PLANE183 and PLANE182 are official element formulations built into MAPDL and
selected with the `ET` command; they are not files to download. The downloaded
files are official example source code, retained as modelling provenance. An
official example adaptation is still not a certified design for an arbitrary
real bracket, plate, or vessel.

Two optional downloaded Mechanical examples are present under
`examples/mechanical`:

- `cantilever.mechdat`
- `example_03_simple_bolt_new.mechdat`

They are retained only for separate Mechanical integration experiments. They
are not used by `POST /simulate` and there are no downloaded table, screw, or
nut CAD/Mechanical files in this repository.

After each dashboard/API run, the readable model definition and native MAPDL
database are retained privately inside `output/api/<run_id>` for engineering
audit/debugging. They are not included in the client-facing download links or
public result JSON. The client-facing outputs are the JSON, CSV, stress,
deformation, failure-assessment, and force-sweep files.

MAPDL's working files and solver logs are also retained under:

```text
D:\AnsysProjects\pyansys-poc\mapdl_runs
```

## Requirements

- Windows
- Python 3.11+
- Node.js/npm
- Ansys Student 2026 R1 or a compatible MAPDL installation
- PyMAPDL 0.73.2

Default MAPDL executable:

```text
D:\ANSYS Inc\ANSYS Student\v261\ansys\bin\winx64\MAPDL.exe
```

Optional path overrides:

```powershell
$env:PYANSYS_MAPDL_EXECUTABLE = 'D:\path\to\MAPDL.exe'
$env:PYANSYS_MAPDL_RUN_ROOT = 'D:\AnsysProjects\pyansys-poc\mapdl_runs'
```

## Installation

Run from the repository root:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

cd frontend
npm install
cd ..
```

Close Workbench and Mechanical before launching this application when using a
Student license, because another Ansys process can consume the available
license.

## Run backend and frontend

Open terminal 1 in the repository root:

```powershell
python -m uvicorn app.api.main:app --host 127.0.0.1 --port 8000
```

Wait for `Application startup complete`. API startup pre-warms MAPDL once, so
startup can take several seconds. Subsequent simulations reuse that solver.

Open terminal 2:

```powershell
cd frontend
npm run dev
```

Open the Vite URL, normally `http://localhost:5173`.

Useful endpoints:

- API health: `http://127.0.0.1:8000/health`
- Swagger UI: `http://127.0.0.1:8000/docs`
- Templates: `GET /templates`
- Material cards: `GET /materials`
- Simulation: `POST /simulate`

Do not start a second backend on port 8000. If PowerShell reports error 10048,
the existing backend is already listening. Find it with:

```powershell
Get-NetTCPConnection -LocalPort 8000 -State Listen
```

The application also detects a live warm MAPDL session owned by another API
process and refuses to launch a second solver, protecting the Student license.

## API request

All new clients should send a load range:

```json
{
  "case_id": "api_case",
  "template": "cantilever",
  "force_start_n": 100,
  "force_end_n": 3000,
  "force_increment_n": 100,
  "length_m": 1.0,
  "width_m": 0.1,
  "height_m": 0.1,
  "diameter_m": 0.01,
  "mesh_size_m": 0.05,
  "material": "Structural Steel"
}
```

The solver evaluates `100, 200, 300, ...` and always includes the requested
end load. If the increment does not divide the range exactly, the end load is
added as the final point. This behavior applies to every model template.

For backward compatibility, `force_n` is still accepted and is mapped to one
MAPDL evaluation point:

```json
{
  "case_id": "legacy_case",
  "template": "cantilever",
  "force_n": 3000,
  "length_m": 1.0,
  "width_m": 0.1,
  "height_m": 0.1,
  "mesh_size_m": 0.05,
  "material": "Structural Steel"
}
```

Physical inputs must be positive and finite. There is no arbitrary upper force
or geometry cap, but very large/small values can exceed the validity of the
linear model or practical solver/license limits.

## Output files

Each API run is written under `output/api/<run_id>` and exposed through
`/artifacts/<run_id>/...`:

- `results.json`: complete run and force-curve data;
- `results.csv`: one row per load point;
- `stress.png`: final-load stress result;
- `deformation.png`: final-load displacement result;
- `failure_assessment.png`: separate screening report;
- `force_sweep.png`: separate stress/displacement response chart;
- `model_definition.txt`: private readable runtime model definition;
- `model.db`: private native final MAPDL model database.

The JSON response also contains:

```json
{
  "timing_seconds": {
    "queue": 0.0,
    "simulation_and_artifacts": 0.0,
    "total": 0.0
  },
  "mapdl_session_reused": true
}
```

## Performance

The API keeps one MAPDL process warm and serializes requests with a lock,
which is appropriate for the local Student-license PoC. Within a force sweep,
the model is built and meshed once. Later points replace the nodal load and
perform a fresh MAPDL solve on the existing mesh. Result images are generated
once for the final load.

Measured locally on the current machine:

- Previous observed request: about 20.11 seconds.
- Optimized 5-point bolt sweep: about 6.64 seconds, including all artifacts and
  the two model downloads.
- Optimized legacy one-point cantilever request: about 5.64 seconds.

Times depend on the machine, antivirus, material/model size, mesh density, and
number of checks. A request can also wait in the queue if another solve is in
progress. Use `timing_seconds` rather than client-side network timing to locate
the delay.

## Materials

Controlled cards are defined once in `app/simulation/materials.py`:

- Structural Steel
- Stainless Steel 304
- Aluminium Alloy 6061-T6
- Titanium Alloy Ti-6Al-4V
- ABS Plastic

These are application-owned cards sourced from the URLs recorded in
`app/simulation/materials.py`; they are not automatically fetched from MAPDL.
The UI therefore labels them **Application material card - properties sent to
MAPDL**. Elastic modulus, Poisson ratio, and density are supplied to MAPDL with
`MP,EX`, `MP,PRXY`, and `MP,DENS`. Reference strength remains in the
application's screening layer for safety factor and threshold estimates. JSON
records `material_source_url` and `material_data_origin` for auditability.
Generic wood is excluded because species, grade, moisture, grain direction,
and orthotropic properties are required.

## Stress and displacement methods

- Cantilever and table stress: BEAM188 extreme-fibre section stress extracted
  from MAPDL SMISC 32/33.
- Official bracket and plate stress: PLANE183 MAPDL nodal equivalent stress.
- Official pressure-vessel stress: PLANE182 MAPDL nodal equivalent stress.
- Bolt/screw/nut stress: nominal axial `force / section area` for the exact
  BEAM188 section used by MAPDL.
- All template displacements: MAPDL nodal displacement results.
- Safety factor: selected material reference strength divided by maximum
  reported stress.

The axial stress formula is exact for these uniform one-dimensional shank
surrogates, but it does not model real thread-root or contact stress.

## Failure screening fields

Results include:

- `failure_status`
- `breakage_assessment`
- `stress_utilization`
- `deformation_ratio`
- `large_deformation_warning`
- `critical_stress_location`
- `critical_displacement_location`
- `estimated_reference_strength_load_n`
- `estimated_deformation_limit_load_n`
- `governing_screening_load_n`
- `governing_screening_criterion`
- `failure_summary`

`break_force_n` is retained for API compatibility, but it means the estimated
reference-strength crossing, not guaranteed fracture. If the crossing is
outside the selected load range, the sweep image labels it as above/below range
without changing the plotted axis.
For the pressure vessel, the range and threshold values are pressure in Pa;
use `load_value`, `load_unit`, `threshold_load_value`, and
`threshold_load_unit`. The legacy `force_n`/`break_force_n` property names are
retained only for response compatibility.

## Validation and acceptance tests

Deterministic Python tests:

```powershell
python -m unittest discover -s tests -v
```

Frontend production build:

```powershell
cd frontend
npm run build
```

Real MAPDL range verification for the original five templates:

```powershell
python scripts\08_verify_all_template_ranges.py
```

The three official adaptations were additionally acceptance-tested through the
API with two load points. Each returned the intended PLANE183/PLANE182 type,
finite stress/displacement, JSON/CSV/PNG artifacts, and a 2.0 response ratio
when the linear load/pressure was doubled. Private `model.db` and
`model_definition.txt` artifacts are retained on disk but are not public
downloads.

Report:

```text
output\range_verification\verification.json
```

Real MAPDL template/material matrix, 25 combinations:

```powershell
python scripts\09_verify_model_material_matrix.py
```

Report:

```text
output\model_material_matrix\verification.json
```

End-to-end warm-session API verification (start the backend first):

```powershell
python scripts\10_verify_api_warm_session.py
```

Report: `output\api_warm_verification.json`.

Additional scripts:

- `scripts/00_preflight.py`: environment/license preflight;
- `scripts/01_connectivity.py`: launch/connectivity check;
- `scripts/02_single_cantilever.py`: single cantilever;
- `scripts/03_batch_cantilever.py`: CSV cantilever batch;
- `scripts/04_example_templates.py`: single-load extension examples;
- `scripts/05_verify_materials.py`: five-material cantilever references;
- `scripts/06_validate_mechanical_sample.py`: optional Mechanical sample check;
- `scripts/07_run_downloaded_cantilever.py`: optional downloaded Mechanical test.
- `scripts/08_verify_all_template_ranges.py`: all-template range acceptance;
- `scripts/09_verify_model_material_matrix.py`: all template/material pairs;
- `scripts/10_verify_api_warm_session.py`: warm API, timing, and downloads.

## Troubleshooting

### Port 8000 already in use

Use the existing backend, or stop its current owning PID before starting one
replacement process:

```powershell
$connection = Get-NetTCPConnection -LocalPort 8000 -State Listen
Stop-Process -Id $connection.OwningProcess -Force
```

### MAPDL license unavailable

Close Workbench/Mechanical and run:

```powershell
python scripts\00_preflight.py
```

Errors such as `No such feature exists` or `Maximum licensed number of demo
users already reached` are license/session issues, not structural results.

### API startup appears slow

The backend intentionally launches MAPDL during startup. Wait for `Application
startup complete`; this startup cost is paid once and then reused.

### Large deformation warning

Do not interpret the linear displacement or extrapolated reference-strength
load as quantitatively reliable after the model leaves its small-deformation
scope. Use a validated nonlinear analysis for production decisions.
