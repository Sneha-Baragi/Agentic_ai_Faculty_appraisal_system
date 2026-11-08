import { useEffect, useState } from "react";
import {
  createAdministrativeResponsibility,
  fetchAdministrativeResponsibilities,
  listEvidence,
  uploadEvidence,
} from "../api/client.js";

const EMPTY_FORM = {
  role: "",
  organizational_unit: "",
  description: "",
  start_date: "",
  end_date: "",
  evidence_reference: "",
};

function Detail({ label, value }) {
  return (
    <div>
      <dt className="text-xs text-muted">{label}</dt>
      <dd className="mt-0.5 break-words text-sm font-medium text-ink">{value || "—"}</dd>
    </div>
  );
}

export function AdministrativeResponsibilitiesSection() {
  const [responsibilities, setResponsibilities] = useState([]);
  const [evidenceByActivity, setEvidenceByActivity] = useState({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [uploadingActivityId, setUploadingActivityId] = useState(null);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);

  async function loadResponsibilities() {
    try {
      setLoading(true);
      setError("");
      const [items, itemsEvidence] = await Promise.all([
        fetchAdministrativeResponsibilities(),
        listEvidence(),
      ]);

      const grouped = {};
      for (const item of itemsEvidence) {
        const activityId = item.activity_id;
        if (!activityId) continue;
        grouped[activityId] = grouped[activityId] || [];
        grouped[activityId].push(item);
      }

      setResponsibilities(items);
      setEvidenceByActivity(grouped);
    } catch (err) {
      setError(err.message || "Failed to load administrative responsibilities.");
    } finally {
      setLoading(false);
    }
  }

  async function handleEvidenceUpload(activityId, file) {
    if (!file) return;
    setUploadingActivityId(activityId);
    setError("");
    try {
      await uploadEvidence(activityId, file);
      await loadResponsibilities();
      setSuccess("Evidence uploaded successfully.");
    } catch (err) {
      setError(err.message || "Failed to upload evidence.");
    } finally {
      setUploadingActivityId(null);
    }
  }

  useEffect(() => {
    loadResponsibilities();
  }, []);

  function updateField(event) {
    const { name, value } = event.target;
    setForm((current) => ({ ...current, [name]: value }));
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setSaving(true);
    setError("");
    setSuccess("");
    const payload = {
      role: form.role.trim(),
      organizational_unit: form.organizational_unit.trim() || null,
      description: form.description.trim() || null,
      start_date: form.start_date || null,
      end_date: form.end_date || null,
      evidence_reference: form.evidence_reference.trim() || null,
    };

    try {
      await createAdministrativeResponsibility(payload);
      setForm(EMPTY_FORM);
      setShowForm(false);
      setSuccess("Administrative responsibility added.");
      await loadResponsibilities();
    } catch (err) {
      setError(err.message || "Failed to add administrative responsibility.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="ui-card h-full p-5 sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="ui-eyebrow">Institutional service</p>
          <h2 className="mt-1 text-lg font-semibold text-ink">Administrative responsibilities</h2>
        </div>
        <button
          type="button"
          onClick={() => {
            setSuccess("");
            setError("");
            setShowForm(true);
          }}
          className="ui-button-primary"
        >
          + Add Responsibility
        </button>
      </div>

      {success ? <p role="status" className="mt-4 rounded-md border border-success/20 bg-success/5 px-3 py-2 text-sm text-success">{success}</p> : null}
      {error ? <p role="alert" className="mt-4 rounded-md border border-danger/20 bg-danger/5 px-3 py-2 text-sm text-danger">{error}</p> : null}

      {loading ? (
        <p className="py-6 text-sm text-muted" aria-live="polite">Loading administrative responsibilities…</p>
      ) : responsibilities.length === 0 && !error ? (
        <p className="ui-card-subtle mt-4 border-dashed p-6 text-center text-sm text-text-secondary">
          No administrative responsibilities have been added for this appraisal cycle.
        </p>
      ) : responsibilities.length > 0 ? (
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          {responsibilities.map((item) => (
            <article key={item.id} className="ui-card-subtle p-4">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <h3 className="font-semibold text-ink">{item.role}</h3>
                <div className="flex flex-wrap items-center gap-2">
                  <span className="rounded-full bg-surface px-2.5 py-1 text-xs font-medium text-text-secondary">
                    {item.academic_year || "Academic year not set"}
                  </span>
                  <label
                    className="cursor-pointer rounded-full border border-primary/30 bg-primary/5 px-2.5 py-1 text-[11px] font-semibold text-primary hover:bg-primary/10 disabled:cursor-not-allowed disabled:opacity-50"
                    aria-label={`Upload evidence for ${item.role}`}
                  >
                    {uploadingActivityId === item.id ? "Uploading…" : "+ Evidence"}
                    <input
                      type="file"
                      accept=".pdf,.docx,.xlsx,.png,.jpg,.jpeg"
                      className="hidden"
                      onChange={(event) => {
                        const file = event.target.files?.[0];
                        if (file) {
                          handleEvidenceUpload(item.id, file);
                        }
                        event.target.value = "";
                      }}
                    />
                  </label>
                </div>
              </div>
              {item.description ? <p className="mt-2 text-sm leading-5 text-text-secondary">{item.description}</p> : null}
              <dl className="mt-4 grid gap-x-4 gap-y-3 sm:grid-cols-2">
                <Detail label="Organizational unit" value={item.organizational_unit} />
                <Detail label="Start date" value={item.start_date} />
                <Detail label="End date" value={item.end_date} />
                <Detail label="Evidence reference" value={item.evidence_reference} />
              </dl>

              {(evidenceByActivity[item.id] || []).length > 0 ? (
                <div className="mt-4 rounded-md border border-border bg-surface p-3">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-text-secondary">Attached evidence</p>
                  <ul className="mt-2 space-y-2 text-sm text-ink">
                    {(evidenceByActivity[item.id] || []).map((entry) => (
                      <li key={entry.id} className="flex flex-wrap items-center justify-between gap-2 rounded border border-border bg-white px-2.5 py-2">
                        <span className="truncate">{entry.original_filename || "Evidence file"}</span>
                        <span className="rounded-full bg-success/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-success">
                          {entry.validation_status || "pending"}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </article>
          ))}
        </div>
      ) : null}

      {showForm ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/35 p-4 backdrop-blur-[2px]">
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="administrative-responsibility-title"
            className="ui-card max-h-[90vh] w-full max-w-xl overflow-y-auto p-6 shadow-xl"
          >
            <div className="flex items-start justify-between gap-4">
              <h3 id="administrative-responsibility-title" className="font-display text-xl font-semibold text-ink">Add responsibility</h3>
              <button
                type="button"
                aria-label="Close form"
                onClick={() => setShowForm(false)}
                className="ui-button-secondary min-h-8 px-2 py-1 text-xs"
              >
                Close
              </button>
            </div>
            <form onSubmit={handleSubmit} className="mt-5 space-y-4">
              <label className="block text-sm font-medium text-text-secondary">
                Responsibility name
                <input
                  name="role"
                  required
                  maxLength={200}
                  value={form.role}
                  onChange={updateField}
                  className="ui-input mt-1 font-normal"
                  placeholder="e.g. Sports Coordinator"
                />
              </label>
              <label className="block text-sm font-medium text-text-secondary">
                Organizational unit
                <input
                  name="organizational_unit"
                  maxLength={300}
                  value={form.organizational_unit}
                  onChange={updateField}
                  className="ui-input mt-1 font-normal"
                />
              </label>
              <label className="block text-sm font-medium text-text-secondary">
                Description
                <textarea
                  name="description"
                  value={form.description}
                  onChange={updateField}
                  rows={3}
                  className="ui-input mt-1 font-normal"
                />
              </label>
              <div className="grid gap-4 sm:grid-cols-2">
                <label className="block text-sm font-medium text-text-secondary">
                  Start date
                  <input
                    name="start_date"
                    type="date"
                    value={form.start_date}
                    onChange={updateField}
                    className="ui-input mt-1 font-normal"
                  />
                </label>
                <label className="block text-sm font-medium text-text-secondary">
                  End date
                  <input
                    name="end_date"
                    type="date"
                    min={form.start_date || undefined}
                    value={form.end_date}
                    onChange={updateField}
                    className="ui-input mt-1 font-normal"
                  />
                </label>
              </div>
              <label className="block text-sm font-medium text-text-secondary">
                Evidence reference
                <input
                  name="evidence_reference"
                  maxLength={1000}
                  value={form.evidence_reference}
                  onChange={updateField}
                  className="ui-input mt-1 font-normal"
                  placeholder="Report or document reference"
                />
              </label>
              {error ? <p role="alert" className="text-sm text-danger">{error}</p> : null}
              <div className="flex justify-end gap-2 border-t border-border pt-4">
                <button
                  type="button"
                  onClick={() => setShowForm(false)}
                  className="ui-button-secondary"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={saving}
                  className="ui-button-primary"
                >
                  {saving ? "Adding…" : "Add Responsibility"}
                </button>
              </div>
            </form>
          </div>
        </div>
      ) : null}
    </section>
  );
}