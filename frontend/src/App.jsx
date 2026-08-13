import { useEffect, useState } from "react";

const API_BASE = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000";

const MODEL_OPTIONS = {
  cantilever: {
    name: "Cantilever beam",
    description: "BRD Phase 1 reference model",
  },
  corner_bracket: {
    name: "Ansys corner bracket",
    description: "Official PyMAPDL PLANE183 example adaptation",
    provenance: "Official example adaptation",
  },
  plate_hole: {
    name: "Ansys plate with a hole",
    description: "Official PyMAPDL PLANE183 stress-concentration example adaptation",
    provenance: "Official example adaptation",
  },
  pressure_vessel: {
    name: "Ansys pressure vessel",
    description: "Official PyMAPDL PLANE182 plane-strain example adaptation",
    provenance: "Official example adaptation",
  },
  table: {
    name: "Table frame",
    description: "Four-leg frame with a centre top load",
  },
  bolt: {
    name: "Bolt",
    description: "Simplified axial shank example",
  },
  screw: {
    name: "Screw",
    description: "Simplified axial shank example",
  },
  nut: {
    name: "Nut",
    description: "Simplified annular compression example",
  },
};

const FAILURE_STATUS_LABELS = {
  likely_failure_or_yielding: "Likely yielding / failure",
  large_deformation_warning: "Large-deformation warning",
  within_reference_strength: "Within reference strength",
  not_evaluated: "Not evaluated",
};

const initialForm = {
  case_id: "dashboard_case",
  template: "cantilever",
  force_start_n: 100,
  force_end_n: 1000,
  force_increment_n: 100,
  length_m: 1,
  width_m: 0.1,
  height_m: 0.1,
  diameter_m: 0.01,
  mesh_size_m: 0.05,
  material: "Structural Steel",
};

const MODEL_DEFAULTS = {
  cantilever: { force_start_n: 100, force_end_n: 1000, force_increment_n: 100, length_m: 1, width_m: 0.1, height_m: 0.1, diameter_m: 0.01, mesh_size_m: 0.05 },
  corner_bracket: { force_start_n: 1000, force_end_n: 5000, force_increment_n: 1000, length_m: 0.3, width_m: 0.08, height_m: 0.008, diameter_m: 0.025, mesh_size_m: 0.008 },
  plate_hole: { force_start_n: 1000, force_end_n: 5000, force_increment_n: 1000, length_m: 0.4, width_m: 0.1, height_m: 0.001, diameter_m: 0.03, mesh_size_m: 0.01 },
  pressure_vessel: { force_start_n: 1e6, force_end_n: 5e6, force_increment_n: 1e6, length_m: 0.175, width_m: 0.2, height_m: 0.01, diameter_m: 0.03, mesh_size_m: 0.006 },
  table: { force_start_n: 100, force_end_n: 1000, force_increment_n: 100, length_m: 1, width_m: 0.1, height_m: 0.1, diameter_m: 0.01, mesh_size_m: 0.05 },
  bolt: { force_start_n: 100, force_end_n: 1000, force_increment_n: 100, length_m: 1, width_m: 0.1, height_m: 0.1, diameter_m: 0.01, mesh_size_m: 0.05 },
  screw: { force_start_n: 100, force_end_n: 1000, force_increment_n: 100, length_m: 1, width_m: 0.1, height_m: 0.1, diameter_m: 0.01, mesh_size_m: 0.05 },
  nut: { force_start_n: 100, force_end_n: 1000, force_increment_n: 100, length_m: 1, width_m: 0.1, height_m: 0.1, diameter_m: 0.01, mesh_size_m: 0.05 },
};

function App() {
  const [form, setForm] = useState(initialForm);
  const [materials, setMaterials] = useState([]);
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const isCantilever = form.template === "cantilever";
  const isTable = form.template === "table";
  const isOfficialPlane = ["corner_bracket", "plate_hole", "pressure_vessel"].includes(form.template);
  const isAxial = !isCantilever && !isTable && !isOfficialPlane;
  const isPressure = form.template === "pressure_vessel";
  const isPlateHole = form.template === "plate_hole";
  const isBracket = form.template === "corner_bracket";
  const loadName = isPressure
    ? "pressure"
    : form.template === "table"
    ? "vertical load"
    : form.template === "nut"
      ? "compressive load"
      : isAxial
        ? "tensile load"
        : "force";

  useEffect(() => {
    fetch(`${API_BASE}/materials`)
      .then((response) => {
        if (!response.ok) throw new Error("Could not load materials");
        return response.json();
      })
      .then((payload) => setMaterials(payload.materials ?? []))
      .catch(() => setMaterials([]));
  }, []);

  const update = (event) => {
    const { name, value } = event.target;
    if (name === "template") {
      setForm((current) => ({ ...current, template: value, ...MODEL_DEFAULTS[value] }));
      return;
    }
    setForm((current) => ({
      ...current,
      [name]: ["case_id", "material", "template"].includes(name) ? value : Number(value),
    }));
  };

  const runSimulation = async (event) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    setResult(null);

    try {
      const response = await fetch(`${API_BASE}/simulate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail ?? "Simulation failed");
      setResult(payload);
    } catch (caught) {
      setError(caught.message || "Could not connect to the API");
    } finally {
      setBusy(false);
    }
  };

  const fileUrl = (path) => `${API_BASE}${path}`;
  const simulation = result?.result;
  const selectedModel = MODEL_OPTIONS[form.template];

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">
            <svg viewBox="0 0 40 40" role="presentation">
              <path className="mark-ring" d="M20 3.5 34.3 11.7v16.6L20 36.5 5.7 28.3V11.7Z" />
              <path className="mark-line" d="m11.5 25.5 6.2-11 5.2 8.5 5.6-8.5" />
              <circle cx="11.5" cy="25.5" r="2" /><circle cx="17.7" cy="14.5" r="2" /><circle cx="22.9" cy="23" r="2" /><circle cx="28.5" cy="14.5" r="2" />
            </svg>
          </span>
          <div><strong>PyAnsys Structural</strong><span>Parameter-driven simulation</span></div>
        </div>
      </header>

      <div className="page">
        <section className="welcome-row">
          <div>
            <p className="eyebrow">Controlled engineering run</p>
            <h1>Structural simulation dashboard</h1>
            <p className="intro">Select an approved example, update its inputs, and receive solver results as CSV, JSON, and images.</p>
          </div>
          <div className="model-badge">
            <span className="model-icon">▰</span>
            <div><small>ACTIVE MODEL</small><strong>{selectedModel.name}</strong><span>{selectedModel.description}</span></div>
          </div>
        </section>

        <section className="dashboard-grid">
          <form className="panel input-panel" onSubmit={runSimulation}>
            <div className="panel-heading"><div><span className="section-kicker">01 / INPUTS</span><h2>Simulation setup</h2></div><span className="template-tag">{selectedModel.provenance ?? "PoC template"}</span></div>

            <div className="field-group">
              <h3>Model selection</h3>
              <label>Model template<select name="template" value={form.template} onChange={update}>{Object.entries(MODEL_OPTIONS).map(([key, model]) => <option key={key} value={key}>{model.name}</option>)}</select></label>
              <p className="field-help">{selectedModel.description}. Enter positive finite values; practical solver errors are reported if a model cannot be solved.</p>
              <label>Case ID<input name="case_id" value={form.case_id} onChange={update} /></label>
            </div>

            <div className="field-group">
              <h3>{isAxial && form.template === "nut" ? "Compression and material" : "Load and material"}</h3>
              <div className="range-grid">
                <label>Start {loadName}<span className="unit">{isPressure ? "Pa" : "N"}</span><input name="force_start_n" type="number" step="any" value={form.force_start_n} onChange={update} /></label>
                <label>End {loadName}<span className="unit">{isPressure ? "Pa" : "N"}</span><input name="force_end_n" type="number" step="any" value={form.force_end_n} onChange={update} /></label>
                <label className="range-steps">Load increment<span className="unit">{isPressure ? "Pa" : "N"}</span><input name="force_increment_n" type="number" min="0.000001" step="any" value={form.force_increment_n} onChange={update} /></label>
              </div>
              <p className="field-help">MAPDL solves start, then each requested increment, and includes the end load. The dashboard also estimates the selected material&apos;s reference-strength load. It is an elastic screening threshold, not a physical fracture prediction.</p>
              <label>Material<select name="material" value={form.material} onChange={update}>{materials.length ? materials.map((material) => <option key={material.name} value={material.name}>{material.name}</option>) : <option>Structural Steel</option>}</select></label>
              {materials.find((material) => material.name === form.material) && <p className="field-help material-help">Application-sourced engineering properties are sent to MAPDL; reference strength is used by the application&apos;s screening layer.</p>}
            </div>

            <div className="field-group">
              <h3>{isTable ? "Table dimensions" : isPressure ? "Vessel dimensions" : "Model dimensions"} <span>metres</span></h3>
              <div className="field-grid">
                <label>{isPressure ? "Inner radius" : isTable ? "Top length" : "Length"}<input name="length_m" type="number" step="any" value={form.length_m} onChange={update} /></label>
                {isAxial ? <label>Diameter<input name="diameter_m" type="number" step="any" value={form.diameter_m} onChange={update} /></label> : <label>{isPressure ? "Outer radius" : isTable ? "Top width" : "Width"}<input name="width_m" type="number" step="any" value={form.width_m} onChange={update} /></label>}
                {!isAxial && !isPressure && <label>{isTable ? "Leg height" : isOfficialPlane ? "Thickness" : "Height"}<input name="height_m" type="number" step="any" value={form.height_m} onChange={update} /></label>}
                {(isPlateHole || isBracket) && <label>Hole diameter<input name="diameter_m" type="number" step="any" value={form.diameter_m} onChange={update} /></label>}
                {isTable && <label>Leg diameter<input name="diameter_m" type="number" step="any" value={form.diameter_m} onChange={update} /></label>}
                <label>Mesh size<input name="mesh_size_m" type="number" step="any" value={form.mesh_size_m} onChange={update} /></label>
              </div>
            </div>

            <div className="form-footer"><p>Inputs are checked by FastAPI before MAPDL starts.</p><button disabled={busy}>{busy ? "Solving with MAPDL…" : "Run simulation"}<span>→</span></button></div>
            {error && <p className="error">{error}</p>}
          </form>

          <section className="panel results-panel">
            <div className="panel-heading"><div><span className="section-kicker">02 / OUTPUTS</span><h2>Latest result</h2></div>{simulation && <span className="complete-tag"><i /> Completed</span>}</div>
            {!simulation && !busy && <div className="empty-state"><div className="empty-icon">∿</div><h3>Ready for a controlled run</h3><p>Select an example, set its inputs, and start the local MAPDL solver. Results will appear here.</p></div>}
            {busy && <div className="empty-state loading-state"><div className="loader" /><h3>MAPDL is solving</h3><p>The local solver is meshing and evaluating the selected example. Keep this page open.</p></div>}
            {simulation && <>
              <div className="result-summary"><p className="result-case">Run ID <strong>{result.run_id}</strong><span className="result-template">{MODEL_OPTIONS[simulation.template]?.name ?? simulation.template}</span>{result.timing_seconds?.total != null && <span className="result-template">{result.timing_seconds.total.toFixed(2)} s</span>}</p><div className="metrics"><Metric label="Maximum stress" value={`${(simulation.maximum_stress_pa / 1e6).toFixed(3)} MPa`} tone="blue" /><Metric label="Maximum displacement" value={`${(simulation.maximum_displacement_m * 1000).toFixed(4)} mm`} tone="orange" /><Metric label="Safety factor" value={simulation.safety_factor?.toFixed(3) ?? "—"} tone="green" /></div></div>
              {simulation.force_curve?.length > 1 && <div className="sweep-summary"><strong>{simulation.load_type === "internal pressure" ? "Pressure" : "Load"} sweep: {simulation.force_start_n.toFixed(0)}–{simulation.force_end_n.toFixed(0)} {simulation.load_unit ?? "N"} · {simulation.force_steps} MAPDL checks</strong>{simulation.break_force_n != null ? <span className={simulation.break_status === "threshold_reached" ? "threshold-hit" : "threshold-clear"}>Reference-strength threshold ≈ {simulation.break_force_n.toFixed(0)} {simulation.load_unit ?? "N"}{simulation.break_status === "threshold_estimated" ? " (estimated)" : ""}</span> : <span className="threshold-clear">Reference-strength threshold unavailable</span>}</div>}
              <div className="material-card"><div><span className="section-kicker">APPLICATION MATERIAL CARD · PROPERTIES SENT TO MAPDL</span><h3>{simulation.material}</h3><p>{simulation.material_model_note}</p></div><dl><div><dt>Elastic modulus</dt><dd>{(simulation.youngs_modulus_pa / 1e9).toFixed(3)} GPa</dd></div><div><dt>Poisson ratio</dt><dd>{simulation.poissons_ratio.toFixed(2)}</dd></div><div><dt>Density</dt><dd>{simulation.density_kg_m3.toFixed(0)} kg/m³</dd></div><div><dt>Reference strength</dt><dd>{(simulation.reference_strength_pa / 1e6).toFixed(1)} MPa</dd></div></dl><small>Safety-factor basis: {simulation.strength_basis}{simulation.material_source_url && <> · <a href={simulation.material_source_url} target="_blank" rel="noreferrer">Material-data source</a></>}</small></div>
              <div className="output-section"><div><span className="section-kicker">FILES</span><h3>Download results</h3></div><div className="links"><a className="primary-link" href={fileUrl(result.files.csv)} target="_blank" rel="noreferrer">CSV results <span>↓</span></a><a href={fileUrl(result.files.json)} target="_blank" rel="noreferrer">View JSON</a><a href={fileUrl(result.files.stress_image)} target="_blank" rel="noreferrer">Stress image</a><a href={fileUrl(result.files.deformation_image)} target="_blank" rel="noreferrer">Deformation image</a>{result.files.failure_assessment_image && <a href={fileUrl(result.files.failure_assessment_image)} target="_blank" rel="noreferrer">Failure assessment</a>}{result.files.force_sweep_image && <a href={fileUrl(result.files.force_sweep_image)} target="_blank" rel="noreferrer">Force sweep</a>}</div></div>
              <div className={`failure-card failure-${simulation.failure_status ?? "not_evaluated"}`}><div className="failure-card-heading"><div><span className="section-kicker">DYNAMIC FAILURE SCREEN</span><h3>{FAILURE_STATUS_LABELS[simulation.failure_status] ?? simulation.failure_status ?? "Not evaluated"}</h3></div>{simulation.governing_screening_load_n != null && <strong>{simulation.governing_screening_criterion === "reference strength" ? "Material threshold" : "Model-validity warning"} ≈ {simulation.governing_screening_load_n.toFixed(0)} N</strong>}</div><ul>{(simulation.failure_summary ?? []).slice(0, 3).map((line, index) => <li key={`${simulation.run_id}-summary-${index}`}>{line}</li>)}</ul><p>Screening only: this identifies likely yielding, excessive deformation, or a reference-strength crossing. It does not prove exact physical fracture.</p></div>
              {simulation.force_curve?.length <= 1 && simulation.break_force_n != null && <div className="sweep-summary"><strong>Reference-strength threshold</strong><span className={simulation.break_status === "threshold_reached" ? "threshold-hit" : "threshold-clear"}>threshold ≈ {simulation.break_force_n.toFixed(0)} N{simulation.break_status === "threshold_estimated" ? " (estimated)" : ""}</span></div>}
              <p className="method-note">{simulation.model_provenance === "official_ansys_example_adaptation" ? `Stress method: ${simulation.stress_method}. This is a parameterized adaptation of the linked official Ansys example, solved by MAPDL; it is still a linear-elastic screening model, not a certified product design.` : simulation.template === "cantilever" ? `Stress method: ${simulation.stress_method}. The threshold is a linear-elastic reference-strength crossing, not a physical fracture prediction.` : `Stress method: ${simulation.stress_method}. The threshold is estimated from the linear-elastic result; this is a simplified PoC template, not a validated production product model.`}</p>
            </>}
          </section>
        </section>
        <footer className="footer-note"><span>PyAnsys Structural Automation</span><span>Local API: {API_BASE}</span><span>Official adaptations: Bracket / Plate-hole / Pressure vessel · Surrogates: Table / Bolt / Screw / Nut</span></footer>
      </div>
    </main>
  );
}

function Metric({ label, value, tone }) { return <div className={`metric metric-${tone}`}><span>{label}</span><strong>{value}</strong></div>; }

export default App;
