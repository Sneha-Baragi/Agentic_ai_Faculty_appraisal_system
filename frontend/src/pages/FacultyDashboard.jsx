import { useEffect, useMemo, useState } from "react";
import { useAuth } from "../auth/AuthContext.jsx";
import {
  createActivity,
  createAgentPlan,
  deleteActivity,
  fetchCurrentAppraisal,
  fetchCurrentCycle,
  fetchCurrentReport,
  fetchProfile,
  listActivities,
  listActivityTypes,
  listEvidence,
  answerAgentPlan,
  lockAgentPlan,
  reviseAgentPlan,
  runAppraisal,
  resubmitAppraisal,
  updateActivity,
  updateProfile,
  uploadEvidence,
} from "../api/client.js";

import { TeachingRequirementSection } from "../components/TeachingRequirementSection.jsx";
import { TimetableSection } from "../components/TimetableSection.jsx";
import { AttendanceSection } from "../components/AttendanceSection.jsx";
import { ProjectTeamsSection } from "../components/ProjectTeamsSection.jsx";

const DISCLAIMER = "DEMO/TEST WEIGHTAGES — NOT OFFICIAL UGC";

function SectionHeader({ eyebrow, title, subtitle }) {
  return (
    <div>
      {eyebrow ? <p className="text-xs uppercase tracking-[0.2em] text-accent">{eyebrow}</p> : null}
      <h2 className="font-display mt-1 text-2xl">{title}</h2>
      {subtitle ? <p className="mt-1 text-sm text-slate-600">{subtitle}</p> : null}
    </div>
  );
}

function SectionCard({ children, className = "" }) {
  return (
    <section className={`rounded-lg border border-slate-200 bg-white p-5 shadow-sm ${className}`}>
      {children}
    </section>
  );
}

function Pill({ children, tone = "slate" }) {
  const map = {
    slate: "bg-slate-100 text-slate-700",
    green: "bg-emerald-100 text-emerald-800",
    amber: "bg-amber-100 text-amber-800",
    red: "bg-red-100 text-red-800",
    blue: "bg-sky-100 text-sky-800",
  };
  return (
    <span className={`inline-flex rounded px-2 py-0.5 text-xs font-medium ${map[tone] ?? map.slate}`}>
      {children}
    </span>
  );
}

function ProfileSection({ profile, setProfile }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState({});
  const [error, setError] = useState("");

  useEffect(() => {
    if (profile) setDraft(profile);
  }, [profile]);

  async function onSave() {
    setError("");
    try {
      const patch = {};
      for (const k of ["full_name", "department", "designation", "institution", "employee_code", "joining_date"]) {
        if (draft[k] !== profile?.[k]) patch[k] = draft[k];
      }
      if (Object.keys(patch).length === 0) {
        setEditing(false);
        return;
      }
      const updated = await updateProfile(patch);
      setProfile(updated);
      setEditing(false);
    } catch (err) {
      setError(err.message);
    }
  }

  if (!profile) return <p className="text-sm text-slate-500">Loading profile…</p>;
  const display = editing ? draft : profile;
  const field = (label, key, type = "text") => (
    <label className="block text-sm">
      <span className="block text-slate-500">{label}</span>
      {editing ? (
        <input
          className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
          type={type}
          value={display?.[key] ?? ""}
          onChange={(e) => setDraft({ ...draft, [key]: e.target.value })}
        />
      ) : (
        <span className="block font-medium text-ink">{display?.[key] ?? "—"}</span>
      )}
    </label>
  );

  return (
    <SectionCard>
      <div className="flex items-start justify-between gap-4">
        <SectionHeader eyebrow="Profile" title={`${profile.full_name ?? profile.email ?? "Faculty"}`} />
        <div>
          {!editing ? (
            <button
              onClick={() => setEditing(true)}
              className="rounded border border-slate-300 px-3 py-1.5 text-sm"
            >
              Edit profile
            </button>
          ) : (
            <div className="flex gap-2">
              <button
                onClick={() => {
                  setDraft(profile);
                  setEditing(false);
                  setError("");
                }}
                className="rounded border border-slate-300 px-3 py-1.5 text-sm"
              >
                Cancel
              </button>
              <button
                onClick={onSave}
                className="rounded bg-accent px-3 py-1.5 text-sm font-semibold text-white"
              >
                Save
              </button>
            </div>
          )}
        </div>
      </div>
      {error ? <p className="mt-3 text-sm text-red-700">{error}</p> : null}
      <div className="mt-5 grid gap-4 md:grid-cols-2">
        {field("Full name", "full_name")}
        {field("Employee code", "employee_code")}
        {field("Department", "department")}
        {field("Designation", "designation")}
        {field("Institution", "institution")}
        {field("Joining date", "joining_date", "date")}
      </div>
    </SectionCard>
  );
}

function CycleCard({ cycle }) {
  return (
    <SectionCard>
      <SectionHeader eyebrow="Cycle" title={cycle?.name ?? "No open cycle"} subtitle={cycle?.academic_year ?? ""} />
      <div className="mt-4 flex flex-wrap gap-4 text-sm">
        <div>
          <p className="text-slate-500">Start</p>
          <p className="font-medium">{cycle?.start_date ?? "—"}</p>
        </div>
        <div>
          <p className="text-slate-500">End</p>
          <p className="font-medium">{cycle?.end_date ?? "—"}</p>
        </div>
        <div>
          <p className="text-slate-500">Status</p>
          <Pill tone={cycle?.status === "open" ? "green" : "slate"}>
            {cycle?.status ?? "n/a"}
          </Pill>
        </div>
      </div>
    </SectionCard>
  );
}

function PlannerSection() {
  const [request, setRequest] = useState("");
  const [plan, setPlan] = useState(null);
  const [answers, setAnswers] = useState({});
  const [error, setError] = useState("");
  async function create() {
    try {
      setError("");
      setPlan(await createAgentPlan({ request }));
    } catch (err) { setError(err.message); }
  }
  async function clarify() {
    try {
      setError("");
      setPlan(await answerAgentPlan(plan.plan_id, answers));
    } catch (err) { setError(err.message); }
  }
  async function revise() {
    try {
      setError("");
      setPlan(await reviseAgentPlan(plan.plan_id, { scope: plan.scope }));
    } catch (err) { setError(err.message); }
  }
  async function lock() {
    try {
      setError("");
      setPlan(await lockAgentPlan(plan.plan_id));
    } catch (err) { setError(err.message); }
  }
  return (
    <SectionCard>
      <SectionHeader eyebrow="Agent planner" title="Plan an appraisal" subtitle="Clarify the request, review the structured plan, then lock it before execution." />
      {!plan ? (
        <div className="mt-4 flex gap-2">
          <input className="min-w-0 flex-1 rounded border border-slate-300 px-3 py-2 text-sm" value={request} onChange={(e) => setRequest(e.target.value)} placeholder="e.g. Prepare my annual appraisal" />
          <button disabled={!request.trim()} onClick={create} className="rounded bg-accent px-3 py-2 text-sm font-semibold text-white disabled:opacity-50">Start planning</button>
        </div>
      ) : (
        <div className="mt-4 space-y-3 text-sm">
          <Pill tone={plan.status === "LOCKED" ? "green" : plan.status === "NEEDS_CLARIFICATION" ? "amber" : "blue"}>{plan.status}</Pill>
          {plan.clarification_questions?.length && plan.status === "NEEDS_CLARIFICATION" ? (
            <div className="space-y-2">
              {plan.clarification_questions.map((question) => <label key={question} className="block"><span className="text-slate-600">{question}</span><input className="mt-1 w-full rounded border border-slate-300 px-3 py-2" value={answers[question] ?? ""} onChange={(e) => setAnswers({ ...answers, [question]: e.target.value })} /></label>)}
              <button onClick={clarify} className="rounded bg-accent px-3 py-2 font-semibold text-white">Submit answers</button>
            </div>
          ) : null}
          <div className="grid gap-2 md:grid-cols-2">
            <label>Cycle<input className="mt-1 w-full rounded border border-slate-300 px-2 py-1" disabled={plan.status === "LOCKED"} value={plan.appraisal_cycle ?? ""} onChange={(e) => setPlan({ ...plan, appraisal_cycle: e.target.value })} /></label>
            <label>Scope<input className="mt-1 w-full rounded border border-slate-300 px-2 py-1" disabled={plan.status === "LOCKED"} value={plan.scope ?? ""} onChange={(e) => setPlan({ ...plan, scope: e.target.value })} /></label>
          </div>
          {plan.status !== "LOCKED" ? <div className="flex gap-2"><button onClick={revise} className="rounded border border-slate-300 px-3 py-2">Save revision</button><button disabled={plan.status === "NEEDS_CLARIFICATION"} onClick={lock} className="rounded bg-accent px-3 py-2 font-semibold text-white disabled:opacity-50">Confirm and lock</button></div> : <p className="font-semibold text-emerald-700">Plan locked. Execution may begin.</p>}
        </div>
      )}
      {error ? <p className="mt-2 text-sm text-red-700">{error}</p> : null}
    </SectionCard>
  );
}

function ActivityForm({ onSubmit, onCancel, initial, types }) {
  const [form, setForm] = useState(
    initial ?? { category: "research", activity_type: "publications", title: "", description: "", date: "", extras: {} }
  );
  const catTypes = types?.[form.category] ?? [];
  const detailFields = {
    research: [
      { key: "venue", label: "Journal, publisher, or venue" },
      { key: "year", label: "Publication year", type: "number" },
      { key: "authors", label: "Authors" },
    ],
    teaching: [
      { key: "course_code", label: "Course code" },
      { key: "hours", label: "Teaching hours", type: "number" },
      { key: "pedagogy", label: "Pedagogy or learning method" },
    ],
    administrative: [
      { key: "role", label: "Role" },
      { key: "body", label: "Committee or institutional body" },
      { key: "hours", label: "Hours contributed", type: "number" },
    ],
  }[form.category] ?? [];

  return (
    <div className="mt-4 rounded-lg border border-dashed border-slate-300 bg-slate-50 p-4 text-sm">
      <div className="grid gap-3 md:grid-cols-2">
        <label className="block">
          <span className="text-slate-500">Category</span>
          <select
            className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
            value={form.category}
            onChange={(e) =>
              setForm({
                ...form,
                category: e.target.value,
                activity_type: (types?.[e.target.value]?.[0]) ?? "",
              })
            }
          >
            {Object.keys(types ?? {}).map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </label>
        <label className="block">
          <span className="text-slate-500">Activity type</span>
          <select
            className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
            value={form.activity_type}
            onChange={(e) => setForm({ ...form, activity_type: e.target.value })}
          >
            {catTypes.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </label>
        <label className="block md:col-span-2">
          <span className="text-slate-500">Title</span>
          <input
            className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
            value={form.title}
            onChange={(e) => setForm({ ...form, title: e.target.value })}
          />
        </label>
        <label className="block md:col-span-2">
          <span className="text-slate-500">Description</span>
          <textarea
            className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
            rows={2}
            value={form.description ?? ""}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
          />
        </label>
        <label className="block">
          <span className="text-slate-500">Activity date</span>
          <input
            className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
            type="date"
            value={form.date ?? ""}
            onChange={(e) => setForm({ ...form, date: e.target.value })}
          />
        </label>
        {detailFields.map((field) => (
          <label className="block" key={field.key}>
            <span className="text-slate-500">{field.label}</span>
            <input
              className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
              type={field.type ?? "text"}
              value={form.extras?.[field.key] ?? ""}
              onChange={(e) =>
                setForm({
                  ...form,
                  extras: { ...form.extras, [field.key]: field.type === "number" ? Number(e.target.value) : e.target.value },
                })
              }
            />
          </label>
        ))}
      </div>
      <div className="mt-4 flex justify-end gap-2">
        <button onClick={onCancel} className="rounded border border-slate-300 px-3 py-1.5">
          Cancel
        </button>
        <button
          onClick={() => onSubmit(form)}
          className="rounded bg-accent px-3 py-1.5 font-semibold text-white"
          disabled={!form.title || !form.activity_type}
        >
          {initial ? "Save changes" : "Add activity"}
        </button>
      </div>
    </div>
  );
}

function EvidenceRow({ ev }) {
  const vTone = ev.validation_status === "valid" ? "green" : ev.validation_status === "invalid" ? "red" : "amber";
  const eTone =
    ev.extraction_status === "extracted"
      ? "green"
      : ev.extraction_status === "failed"
      ? "red"
      : ev.extraction_status === "pending" || ev.extraction_status === "extracting"
      ? "amber"
      : "slate";
  return (
    <li className="rounded border border-slate-200 bg-slate-50 p-3 text-sm">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="truncate font-medium text-ink">{ev.original_filename ?? "evidence"}</p>
          <p className="text-xs text-slate-500">
            {new Date(ev.upload_timestamp ?? 0).toLocaleString()} · {ev.file_size ?? 0} bytes
          </p>
        </div>
        <div className="flex flex-col items-end gap-1">
          <Pill tone={vTone}>validation: {ev.validation_status}</Pill>
          <Pill tone={eTone}>extraction: {ev.extraction_status}</Pill>
        </div>
      </div>
    </li>
  );
}

function ActivityItem({ act, evidence, onEdit, onDelete, onUpload }) {
  const [editing, setEditing] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const fileInputId = `up-${act.id}`;

  const actEvidence = useMemo(
    () => (evidence ?? []).filter((e) => e.activity_id === act.id),
    [evidence, act.id]
  );

  async function handleUpload(file) {
    setUploadError("");
    try {
      await uploadEvidence(act.id, file);
      onUpload();
    } catch (err) {
      setUploadError(err.message);
    }
  }

  return (
    <li className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <Pill tone="blue">{act.category}</Pill>
            <Pill>{act.activity_type ?? "—"}</Pill>
            {act.rubric_code ? <Pill tone="amber">rubric: {act.rubric_code}</Pill> : null}
          </div>
          <h4 className="mt-2 font-semibold text-ink">{act.title}</h4>
          {act.description ? <p className="mt-1 whitespace-pre-wrap text-sm text-slate-600">{act.description}</p> : null}
          <p className="mt-2 text-xs text-slate-500">
            Created: {act.created_at ?? "—"} · Evidence: {actEvidence.length}
          </p>
        </div>
        <div className="flex flex-col items-end gap-1">
          <div className="flex gap-2">
            <button onClick={() => setEditing((v) => !v)} className="text-xs underline">
              {editing ? "Cancel edit" : "Edit"}
            </button>
            <button
              onClick={() => {
                if (confirm("Delete this activity and its evidence?")) onDelete(act.id);
              }}
              className="text-xs text-red-700 underline"
            >
              Delete
            </button>
          </div>
          <div>
            <label htmlFor={fileInputId} className="cursor-pointer text-xs underline">
              Upload evidence
            </label>
            <input
              id={fileInputId}
              className="hidden"
              type="file"
              accept=".pdf,.docx,.xlsx,.png,.jpg,.jpeg"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) handleUpload(f);
                e.target.value = "";
              }}
            />
          </div>
        </div>
      </div>
      {uploadError ? <p className="mt-2 text-xs text-red-700">{uploadError}</p> : null}
      {editing ? (
        <ActivityForm
          initial={{
            category: act.category,
            activity_type: act.activity_type,
            title: act.title,
            description: act.description,
            date: act.date?.slice?.(0, 10) ?? "",
            extras: {},
          }}
          onSubmit={(f) => {
            onEdit(act.id, f);
            setEditing(false);
          }}
          onCancel={() => setEditing(false)}
          types={{ research: [act.activity_type], teaching: [act.activity_type], administrative: [act.activity_type] }}
        />
      ) : null}
      {actEvidence.length > 0 ? (
        <ul className="mt-3 space-y-2">
          {actEvidence.map((e) => (
            <EvidenceRow key={e.id} ev={e} />
          ))}
        </ul>
      ) : null}
    </li>
  );
}

function ActivitiesSection({
  cycle,
  activities,
  setActivities,
  evidence,
  setEvidence,
  types,
}) {
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");

  async function refresh() {
    const [acts, evs] = await Promise.all([listActivities(), listEvidence()]);
    setActivities(acts);
    setEvidence(evs);
  }

  async function onCreate(form) {
    setError("");
    try {
      await createActivity(form);
      setCreating(false);
      await refresh();
    } catch (err) {
      setError(err.message);
    }
  }

  async function onEdit(id, form) {
    setError("");
    try {
      await updateActivity(id, form);
      await refresh();
    } catch (err) {
      setError(err.message);
    }
  }

  async function onDelete(id) {
    setError("");
    try {
      await deleteActivity(id);
      await refresh();
    } catch (err) {
      setError(err.message);
    }
  }

  const groups = useMemo(() => {
    const g = { research: [], teaching: [], administrative: [] };
    for (const a of activities ?? []) g[a.category]?.push(a);
    return g;
  }, [activities]);

  if (!cycle) {
    return (
      <SectionCard>
        <SectionHeader eyebrow="Activities" title="No open cycle" subtitle="Wait for an admin to open a cycle." />
      </SectionCard>
    );
  }

  return (
    <SectionCard>
      <div className="flex items-start justify-between gap-4">
        <SectionHeader
          eyebrow="Activities"
          title={`${(activities ?? []).length} activities`}
          subtitle="Add, edit, or delete. Upload evidence for each activity."
        />
        {!creating ? (
          <button
            onClick={() => setCreating(true)}
            className="rounded bg-accent px-3 py-1.5 text-sm font-semibold text-white"
          >
            Add activity
          </button>
        ) : (
          <button onClick={() => setCreating(false)} className="text-sm underline">
            Cancel add
          </button>
        )}
      </div>
      {error ? <p className="mt-3 text-sm text-red-700">{error}</p> : null}
      {creating ? (
        <ActivityForm onSubmit={onCreate} onCancel={() => setCreating(false)} types={types} />
      ) : null}
      <div className="mt-6 space-y-6">
        {["research", "teaching", "administrative"].map((cat) => (
          <div key={cat}>
            <div className="mb-2 flex items-center justify-between">
              <h3 className="text-sm font-semibold uppercase tracking-widest text-slate-500">{cat}</h3>
              <span className="text-xs text-slate-500">{groups[cat].length} items</span>
            </div>
            <ul className="space-y-3">
              {groups[cat].map((a) => (
                <ActivityItem
                  key={a.id}
                  act={a}
                  evidence={evidence}
                  onEdit={onEdit}
                  onDelete={onDelete}
                  onUpload={refresh}
                />
              ))}
              {groups[cat].length === 0 ? (
                <li className="rounded-lg border border-dashed border-slate-300 p-4 text-center text-sm text-slate-400">
                  No {cat} activities yet.
                </li>
              ) : null}
            </ul>
          </div>
        ))}
      </div>
    </SectionCard>
  );
}

function ScoreBreakdown({ score }) {
  if (!score) return null;
  const items = score.score_breakdown?.line_items ?? [];
  const cats = [
    { key: "research_score", label: "Research", tone: "blue" },
    { key: "teaching_score", label: "Teaching", tone: "green" },
    { key: "administrative_score", label: "Administrative", tone: "amber" },
  ];
  return (
    <div>
      <div className="grid gap-3 md:grid-cols-4">
        <div className="rounded-lg border border-accent/30 bg-accent/5 p-4">
          <p className="text-xs uppercase tracking-widest text-slate-500">Total score</p>
          <p className="font-display mt-1 text-3xl text-accent">{score.total_score?.toFixed?.(2) ?? score.total_score ?? 0}</p>
        </div>
        {cats.map((c) => (
          <div key={c.key} className="rounded-lg border border-slate-200 bg-white p-4">
            <p className="text-xs uppercase tracking-widest text-slate-500">{c.label}</p>
            <p className="font-display mt-1 text-2xl text-ink">
              {(score.score_breakdown?.[c.key] ?? 0)?.toFixed?.(2) ?? score.score_breakdown?.[c.key] ?? 0}
            </p>
          </div>
        ))}
      </div>
      {items.length > 0 ? (
        <div className="mt-5 rounded-lg border border-slate-200 bg-white">
          <div className="border-b border-slate-100 px-4 py-2 text-sm font-semibold text-ink">Score breakdown</div>
          <ul className="divide-y divide-slate-100 text-sm">
            {items.map((it, i) => (
              <li key={`${it.activity_id}-${i}`} className="flex flex-wrap items-center justify-between gap-2 px-4 py-2">
                <div className="min-w-0">
                  <Pill tone="slate">{it.rubric_code ?? "—"}</Pill>
                  <span className="ml-2 text-slate-700">Activity {it.activity_id?.slice?.(0, 8) ?? it.activity_id}</span>
                </div>
                <div className="flex flex-col items-end">
                  <span className="font-semibold text-accent">{it.points?.toFixed?.(2) ?? it.points ?? 0}</span>
                  <span className="text-xs text-slate-500">
                    evidence: {(it.evidence_ids ?? []).map((e) => e?.slice?.(0, 6) ?? e).join(", ") || "none"}
                  </span>
                </div>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}

function ReportView({ report }) {
  if (!report) return null;
  const rating = report.rating_recommendation;
  return (
    <div className="mt-5 rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="text-xs uppercase tracking-widest text-slate-500">Report version {report.version_number}</p>
          <p className="text-slate-600">Status: {report.status}</p>
        </div>
        <Pill tone={rating === "A" || rating === "B" ? "green" : rating === "C" ? "amber" : "slate"}>
          {report.approval_status === "approved" || report.approval_status === "published" ? "Final Rating" : "Recommended Rating"}: {rating ?? "—"}
        </Pill>
      </div>
      <div className="mt-3 overflow-hidden rounded border border-slate-200 bg-white">
        <iframe
          title="report"
          className="h-80 w-full bg-white"
          srcDoc={report.html ?? ""}
        />
      </div>
    </div>
  );
}

function AppraisalSection({ cycleOpen, onRun, appraisal, report, busy, setBusy }) {
  async function handleRun() {
    setBusy(true);
    try {
      await onRun();
    } finally {
      setBusy(false);
    }
  }
  async function handleResubmit() {
    setBusy(true);
    try {
      await resubmitAppraisal();
      await onRun();
    } finally {
      setBusy(false);
    }
  }
  const score = appraisal?.score ?? null;
  const approval = appraisal?.approval_status ?? "not_generated";
  const approvalDetails = report?.json?.approval ?? {};
  const approvalMessage = {
    awaiting_review: "Your appraisal is waiting for HOD review.",
    approved: "Your appraisal has been approved by the HOD.",
    rejected: "Your appraisal was rejected.",
    changes_requested: "Please make the requested changes.",
  }[approval];
  return (
    <SectionCard>
      <div className="flex items-start justify-between gap-4">
        <SectionHeader
          eyebrow="Appraisal"
          title="Run & review"
          subtitle={DISCLAIMER}
        />
        <button
          disabled={!cycleOpen || busy}
          onClick={handleRun}
          className="rounded bg-accent px-3 py-1.5 text-sm font-semibold text-white disabled:opacity-60"
        >
          {busy ? "Running…" : "Run Appraisal"}
        </button>
        {approval === "changes_requested" ? (
          <button disabled={busy} onClick={handleResubmit} className="rounded border border-accent px-3 py-1.5 text-sm font-semibold text-accent disabled:opacity-60">
            {busy ? "Resubmitting…" : "Resubmit for Review"}
          </button>
        ) : null}
      </div>
      <div className="mt-4 flex flex-wrap gap-2 text-sm">
        <Pill tone={approval === "approved" ? "green" : approval === "rejected" ? "red" : approval === "changes_requested" ? "amber" : "slate"}>
          Approval status: {approval.replaceAll("_", " ")}
        </Pill>
        {score?.scoring_engine_version ? <Pill tone="blue">Engine v{score.scoring_engine_version}</Pill> : null}
      </div>
      {approvalMessage ? (
        <div className="mt-4 rounded border border-slate-200 bg-slate-50 px-3 py-2 text-sm">
          <p className="font-semibold text-ink">{approvalMessage}</p>
          {approvalDetails.reason ? <p className="mt-1 text-slate-600">Comment: {approvalDetails.reason}</p> : null}
          {approvalDetails.reviewer ? <p className="mt-1 text-slate-500">Reviewer: {approvalDetails.reviewer}</p> : null}
        </div>
      ) : null}
      {score ? <div className="mt-5"><ScoreBreakdown score={score} /></div> : null}
      <ReportView report={report} />
      <div className="mt-4 rounded border border-amber-200 bg-amber-50 px-3 py-2 text-sm">{DISCLAIMER}</div>
    </SectionCard>
  );
}

export default function FacultyDashboard() {
  const { user, logout } = useAuth();
  const [profile, setProfile] = useState(null);
  const [cycle, setCycle] = useState(null);
  const [activities, setActivities] = useState([]);
  const [evidence, setEvidence] = useState([]);
  const [types, setTypes] = useState({});
  const [appraisal, setAppraisal] = useState(null);
  const [report, setReport] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function refreshAll() {
    try {
      const [p, c, a, e, t, ap, rp] = await Promise.all([
        fetchProfile(),
        fetchCurrentCycle().catch(() => null),
        listActivities().catch(() => []),
        listEvidence().catch(() => []),
        listActivityTypes().catch(() => ({})),
        fetchCurrentAppraisal().catch(() => null),
        fetchCurrentReport().catch(() => null),
      ]);
      setProfile(p);
      setCycle(c);
      setActivities(a);
      setEvidence(e);
      setTypes(t);
      setAppraisal(ap);
      setReport(rp);
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => {
    refreshAll();
  }, []);

  return (
    <main className="mx-auto max-w-6xl px-6 py-10">
      <header className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.2em] text-accent">Faculty workspace</p>
          <h1 className="font-display mt-1 text-3xl">Appraisal dashboard</h1>
          <p className="mt-2 text-sm text-slate-600">{user?.email}</p>
        </div>
        <button onClick={logout} className="text-sm underline">
          Sign out
        </button>
      </header>
      <p className="mt-4 rounded border border-amber-200 bg-amber-50 px-3 py-2 text-sm">
        {DISCLAIMER}
      </p>
      {error ? <p className="mt-3 text-sm text-red-700">Error: {error}</p> : null}

      <div className="mt-8 grid gap-4 lg:grid-cols-5">
        <div className="space-y-4 lg:col-span-2">
          <ProfileSection profile={profile} setProfile={setProfile} />
          <CycleCard cycle={cycle} />
        </div>
        <div className="space-y-4 lg:col-span-3">
          <TeachingRequirementSection refresh={activities} />
          <AppraisalSection
            cycleOpen={!!cycle && cycle.status === "open"}
            onRun={async () => {
              await runAppraisal();
              await refreshAll();
            }}
            appraisal={appraisal}
            report={report}
            busy={busy}
            setBusy={setBusy}
          />
        </div>
      </div>

      <div className="mt-6 space-y-6">
        <TimetableSection onTimetableChange={refreshAll} />
        <AttendanceSection onAttendanceMarked={refreshAll} />
        <ProjectTeamsSection />
      </div>

      <div className="mt-6"><PlannerSection /></div>

      <div className="mt-6">
        <ActivitiesSection
          cycle={cycle}
          activities={activities}
          setActivities={setActivities}
          evidence={evidence}
          setEvidence={setEvidence}
          types={types}
        />
      </div>
    </main>
  );
}
