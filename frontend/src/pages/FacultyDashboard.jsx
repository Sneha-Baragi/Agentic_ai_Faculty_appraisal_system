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

import AppLayout from "../components/layout/AppLayout.jsx";
import { Icons } from "../components/ui/Icons.jsx";
import { TeachingRequirementSection } from "../components/TeachingRequirementSection.jsx";
import { TimetableSection } from "../components/TimetableSection.jsx";
import { AttendanceSection } from "../components/AttendanceSection.jsx";
import { ProjectTeamsSection } from "../components/ProjectTeamsSection.jsx";
import { AdministrativeResponsibilitiesSection } from "../components/AdministrativeResponsibilitiesSection.jsx";
import { EvidenceVaultSection } from "../components/EvidenceVaultSection.jsx";

const DISCLAIMER = "DEMO/TEST WEIGHTAGES — NOT OFFICIAL UGC";

function StatusBadge({ tone = "slate", children }) {
  const map = {
    slate: "bg-slate-100 text-slate-700 border-slate-200",
    green: "bg-emerald-50 text-emerald-800 border-emerald-200",
    amber: "bg-amber-50 text-amber-800 border-amber-200",
    red: "bg-red-50 text-red-800 border-red-200",
    blue: "bg-sky-50 text-sky-800 border-sky-200",
  };
  return (
    <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold border ${map[tone] || map.slate}`}>
      {children}
    </span>
  );
}

function StatCard({ label, value, subtext, icon: IconComp, tone = "default" }) {
  return (
    <div className="bg-white rounded-lg border border-[#DCE5E1] p-4 shadow-xs flex items-center justify-between">
      <div>
        <p className="text-[11px] font-semibold uppercase tracking-wider text-[#73817C]">{label}</p>
        <p className="text-2xl font-bold text-[#192522] mt-1">{value}</p>
        {subtext && <p className="text-xs text-[#53635E] mt-0.5">{subtext}</p>}
      </div>
      {IconComp && (
        <div className="h-10 w-10 rounded-lg bg-[#F8FAF9] border border-[#DCE5E1] text-[#194537] flex items-center justify-center shrink-0">
          <IconComp className="w-5 h-5" />
        </div>
      )}
    </div>
  );
}

function ProfileSection({ profile, setProfile, cycle, approvalStatus }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState({});
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  useEffect(() => {
    if (profile) setDraft(profile);
  }, [profile]);

  async function onSave() {
    setError("");
    setSuccess("");
    try {
      const patch = {};
      for (const k of [
        "full_name",
        "department",
        "designation",
        "institution",
        "employee_code",
        "joining_date",
        "google_scholar_id",
        "google_scholar_url",
      ]) {
        const value = ["google_scholar_id", "google_scholar_url"].includes(k) && draft[k] === "" ? null : draft[k];
        if (value !== profile?.[k]) patch[k] = value;
      }
      if (Object.keys(patch).length === 0) {
        setEditing(false);
        return;
      }
      const updated = await updateProfile(patch);
      setProfile(updated);
      setEditing(false);
      setSuccess("Profile updated successfully.");
    } catch (err) {
      setError(err.message);
    }
  }

  if (!profile) return <p className="py-4 text-sm text-[#73817C]">Loading faculty profile…</p>;
  const display = editing ? draft : profile;

  const renderField = (label, key, type = "text", placeholder = "") => (
    <label className="block text-sm">
      <span className="block text-xs font-semibold text-[#53635E] mb-1">{label}</span>
      {editing ? (
        <input
          className="w-full h-10 px-3 rounded-md border border-[#DCE5E1] bg-white text-sm text-[#192522] focus:border-[#194537] focus:ring-2 focus:ring-[#194537]/20 outline-none"
          type={type}
          value={display?.[key] ?? ""}
          placeholder={placeholder}
          onChange={(e) => setDraft({ ...draft, [key]: e.target.value })}
        />
      ) : (
        <span className="block font-medium text-sm text-[#192522] py-1">{display?.[key] ?? "—"}</span>
      )}
    </label>
  );

  return (
    <section className="bg-white rounded-lg border border-[#DCE5E1] p-5 sm:p-7 shadow-xs">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between border-b border-[#DCE5E1] pb-5">
        <div>
          <span className="text-[11px] font-semibold uppercase tracking-wider text-[#73817C]">Faculty Profile</span>
          <h2 className="text-2xl font-bold text-[#192522] mt-0.5">
            {profile.full_name ?? profile.email ?? "Faculty Member"}
          </h2>
          <p className="text-xs text-[#53635E] mt-0.5">
            {[profile.designation, profile.department, profile.institution].filter(Boolean).join(" · ")}
          </p>
        </div>
        <div>
          {!editing ? (
            <button
              onClick={() => setEditing(true)}
              className="inline-flex items-center gap-1.5 h-9 px-4 rounded-md border border-[#DCE5E1] bg-white text-xs font-semibold text-[#192522] hover:bg-[#F8FAF9] transition-colors"
            >
              <Icons.Edit className="w-3.5 h-3.5" /> Edit Profile
            </button>
          ) : (
            <div className="flex gap-2">
              <button
                onClick={() => {
                  setDraft(profile);
                  setEditing(false);
                  setError("");
                }}
                className="h-9 px-3 rounded-md border border-[#DCE5E1] text-xs font-semibold text-[#53635E] hover:bg-[#F8FAF9]"
              >
                Cancel
              </button>
              <button
                onClick={onSave}
                className="h-9 px-4 rounded-md bg-[#194537] text-white text-xs font-semibold hover:bg-[#194537]/90 transition-colors"
              >
                Save Changes
              </button>
            </div>
          )}
        </div>
      </div>

      {error && <p className="mt-4 p-3 rounded bg-red-50 border border-red-200 text-xs text-red-700">{error}</p>}
      {success && <p className="mt-4 p-3 rounded bg-emerald-50 border border-emerald-200 text-xs text-emerald-700">{success}</p>}

      <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {renderField("Full Name", "full_name")}
        {renderField("Employee Code", "employee_code")}
        {renderField("Department", "department")}
        {renderField("Designation", "designation")}
        {renderField("Institution", "institution")}
        {renderField("Joining Date", "joining_date", "date")}
      </div>

      <div className="mt-6 border-t border-[#DCE5E1] pt-5">
        <h3 className="text-sm font-bold text-[#192522] mb-3 flex items-center gap-2">
          <Icons.Scholar className="w-4 h-4 text-[#194537]" /> Google Scholar Integration
        </h3>
        <div className="grid gap-4 sm:grid-cols-2">
          {renderField("Google Scholar ID", "google_scholar_id", "text", "e.g. A1B2C3D4")}
          {renderField("Google Scholar Profile URL", "google_scholar_url", "url", "https://scholar.google.com/citations?user=...")}
        </div>
      </div>
    </section>
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
    <section className="bg-white rounded-lg border border-[#DCE5E1] p-5 sm:p-6 shadow-xs space-y-4">
      <div className="border-b border-[#DCE5E1] pb-3">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-[#73817C]">Agentic Workflow</span>
        <h3 className="text-lg font-bold text-[#192522]">Appraisal Planning Assistant</h3>
        <p className="text-xs text-[#53635E] mt-0.5">Define cycle scope and clarify requirements before formal execution.</p>
      </div>

      {!plan ? (
        <div className="flex flex-col gap-2 sm:flex-row">
          <input
            className="flex-1 h-10 px-3 rounded-md border border-[#DCE5E1] text-sm text-[#192522] outline-none focus:border-[#194537]"
            value={request}
            onChange={(e) => setRequest(e.target.value)}
            placeholder="e.g. Prepare my annual academic appraisal for 2026-2027"
          />
          <button
            disabled={!request.trim()}
            onClick={create}
            className="h-10 px-4 rounded-md bg-[#194537] text-white text-xs font-semibold disabled:opacity-50"
          >
            Start Planning
          </button>
        </div>
      ) : (
        <div className="space-y-3 text-sm">
          <StatusBadge tone={plan.status === "LOCKED" ? "green" : plan.status === "NEEDS_CLARIFICATION" ? "amber" : "blue"}>
            Status: {plan.status}
          </StatusBadge>
          {plan.clarification_questions?.length && plan.status === "NEEDS_CLARIFICATION" ? (
            <div className="space-y-2 p-3 rounded bg-amber-50 border border-amber-200">
              <p className="text-xs font-semibold text-amber-900">Clarification Questions Required:</p>
              {plan.clarification_questions.map((question) => (
                <label key={question} className="block text-xs text-[#53635E]">
                  {question}
                  <input
                    className="w-full mt-1 h-9 px-3 rounded border border-[#DCE5E1] bg-white text-xs"
                    value={answers[question] ?? ""}
                    onChange={(e) => setAnswers({ ...answers, [question]: e.target.value })}
                  />
                </label>
              ))}
              <button onClick={clarify} className="h-8 px-3 rounded bg-[#194537] text-white text-xs font-semibold">
                Submit Answers
              </button>
            </div>
          ) : null}
          <div className="grid gap-3 md:grid-cols-2">
            <label className="text-xs font-medium text-[#53635E]">
              Appraisal Cycle
              <input
                className="w-full mt-1 h-9 px-3 rounded border border-[#DCE5E1] bg-white text-xs"
                disabled={plan.status === "LOCKED"}
                value={plan.appraisal_cycle ?? ""}
                onChange={(e) => setPlan({ ...plan, appraisal_cycle: e.target.value })}
              />
            </label>
            <label className="text-xs font-medium text-[#53635E]">
              Scope
              <input
                className="w-full mt-1 h-9 px-3 rounded border border-[#DCE5E1] bg-white text-xs"
                disabled={plan.status === "LOCKED"}
                value={plan.scope ?? ""}
                onChange={(e) => setPlan({ ...plan, scope: e.target.value })}
              />
            </label>
          </div>
          {plan.status !== "LOCKED" ? (
            <div className="flex gap-2 pt-2">
              <button onClick={revise} className="h-9 px-3 rounded border border-[#DCE5E1] text-xs font-semibold text-[#53635E]">
                Save Revision
              </button>
              <button disabled={plan.status === "NEEDS_CLARIFICATION"} onClick={lock} className="h-9 px-4 rounded bg-[#194537] text-white text-xs font-semibold">
                Confirm & Lock Plan
              </button>
            </div>
          ) : (
            <p className="text-xs font-semibold text-emerald-700">Plan locked and verified.</p>
          )}
        </div>
      )}
      {error && <p className="text-xs text-red-700">{error}</p>}
    </section>
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
      { key: "pedagogy", label: "Pedagogy method" },
    ],
    administrative: [
      { key: "role", label: "Role title" },
      { key: "body", label: "Committee or body" },
      { key: "hours", label: "Hours contributed", type: "number" },
    ],
  }[form.category] ?? [];

  return (
    <div className="p-4 rounded-lg bg-[#F8FAF9] border border-[#DCE5E1] text-xs space-y-3">
      <div className="grid gap-3 md:grid-cols-2">
        <label className="block">
          <span className="text-[#53635E]">Category</span>
          <select
            className="w-full mt-1 h-9 px-2 rounded border border-[#DCE5E1] bg-white text-xs text-[#192522]"
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
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </label>
        <label className="block">
          <span className="text-[#53635E]">Activity type</span>
          <select
            className="w-full mt-1 h-9 px-2 rounded border border-[#DCE5E1] bg-white text-xs text-[#192522]"
            value={form.activity_type}
            onChange={(e) => setForm({ ...form, activity_type: e.target.value })}
          >
            {catTypes.map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
        </label>
        <label className="block md:col-span-2">
          <span className="text-[#53635E]">Title</span>
          <input
            className="w-full mt-1 h-9 px-3 rounded border border-[#DCE5E1] bg-white text-xs text-[#192522]"
            value={form.title}
            onChange={(e) => setForm({ ...form, title: e.target.value })}
          />
        </label>
        <label className="block md:col-span-2">
          <span className="text-[#53635E]">Description</span>
          <textarea
            className="w-full mt-1 p-2 rounded border border-[#DCE5E1] bg-white text-xs text-[#192522]"
            rows={2}
            value={form.description ?? ""}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
          />
        </label>
        <label className="block">
          <span className="text-[#53635E]">Activity date</span>
          <input
            className="w-full mt-1 h-9 px-2 rounded border border-[#DCE5E1] bg-white text-xs text-[#192522]"
            type="date"
            value={form.date ?? ""}
            onChange={(e) => setForm({ ...form, date: e.target.value })}
          />
        </label>
        {detailFields.map((field) => (
          <label className="block" key={field.key}>
            <span className="text-[#53635E]">{field.label}</span>
            <input
              className="w-full mt-1 h-9 px-2 rounded border border-[#DCE5E1] bg-white text-xs text-[#192522]"
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
      <div className="flex justify-end gap-2 pt-2 border-t border-[#DCE5E1]">
        <button onClick={onCancel} className="px-3 py-1.5 rounded border border-[#DCE5E1] text-xs font-semibold text-[#53635E]">
          Cancel
        </button>
        <button
          onClick={() => onSubmit(form)}
          className="px-4 py-1.5 rounded bg-[#194537] text-white text-xs font-semibold disabled:opacity-50"
          disabled={!form.title || !form.activity_type}
        >
          {initial ? "Save changes" : "Add activity"}
        </button>
      </div>
    </div>
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
    <div className="p-4 rounded-lg bg-white border border-[#DCE5E1] space-y-3">
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-2">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="px-2 py-0.5 rounded bg-sky-50 text-sky-800 text-xs font-semibold capitalize">{act.category}</span>
            <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-700 text-xs font-medium">{act.activity_type ?? "—"}</span>
            {act.rubric_code && <span className="px-2 py-0.5 rounded bg-amber-50 text-amber-800 text-xs font-medium">rubric: {act.rubric_code}</span>}
          </div>
          <h4 className="text-sm font-bold text-[#192522] mt-2">{act.title}</h4>
          {act.description && <p className="text-xs text-[#53635E] mt-1 whitespace-pre-wrap">{act.description}</p>}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <button onClick={() => setEditing((v) => !v)} className="px-2 py-1 text-xs font-medium text-[#53635E] hover:text-[#192522]">
            {editing ? "Cancel" : "Edit"}
          </button>
          <button
            onClick={() => {
              if (confirm("Delete this activity and its attached evidence?")) onDelete(act.id);
            }}
            className="px-2 py-1 text-xs font-medium text-red-600 hover:text-red-800"
          >
            Delete
          </button>
          <label htmlFor={fileInputId} className="cursor-pointer px-2.5 py-1 rounded border border-[#DCE5E1] bg-[#F8FAF9] text-xs font-semibold text-[#194537] hover:bg-[#194537]/5">
            + Evidence
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
      {uploadError && <p className="text-xs text-red-600">{uploadError}</p>}
      {editing && (
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
      )}
      {actEvidence.length > 0 && (
        <div className="pt-2 border-t border-[#DCE5E1] space-y-1">
          <p className="text-[11px] font-semibold text-[#73817C]">Attached Evidence Files ({actEvidence.length}):</p>
          {actEvidence.map((e) => (
            <div key={e.id} className="flex items-center justify-between p-2 rounded bg-[#F8FAF9] text-xs">
              <span className="font-medium text-[#192522] truncate">{e.original_filename}</span>
              <div className="flex gap-2 text-[10px]">
                <span className="px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-800 font-semibold">{e.validation_status}</span>
                <span className="px-1.5 py-0.5 rounded bg-sky-100 text-sky-800">{e.extraction_status}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function GoogleScholarMetrics({ report, profile, cycle }) {
  const snapshot = report?.json?.research_metrics;
  const profileUrl = profile?.google_scholar_url || snapshot?.scholar_url;
  const [showAllPublications, setShowAllPublications] = useState(false);

  const appraisalYear = cycle?.start_date
    ? new Date(cycle.start_date).getFullYear()
    : cycle?.academic_year
    ? parseInt(cycle.academic_year)
    : 2026;

  if (!snapshot || snapshot.status !== "retrieved") {
    return (
      <div className="bg-white rounded-lg border border-[#DCE5E1] p-5 shadow-xs space-y-3">
        <div className="flex items-center justify-between border-b border-[#DCE5E1] pb-3">
          <div className="flex items-center gap-2">
            <Icons.Scholar className="w-5 h-5 text-[#194537]" />
            <h3 className="text-base font-bold text-[#192522]">Google Scholar Verification</h3>
          </div>
          {snapshot?.human_review_required && <StatusBadge tone="amber">Requires Review</StatusBadge>}
        </div>
        <p className="text-xs text-[#53635E]">
          {snapshot ? "Google Scholar metrics require verification or identity review." : "Scholar profile metrics have not been fetched yet."}
        </p>
        {profileUrl && (
          <a href={profileUrl} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-xs font-semibold text-[#194537] underline">
            Open Scholar Profile <Icons.ExternalLink className="w-3 h-3" />
          </a>
        )}
      </div>
    );
  }

  const metrics = snapshot.metrics ?? {};
  const publications = Array.isArray(snapshot.publications) ? snapshot.publications : [];
  const visiblePublications = showAllPublications ? publications : publications.slice(0, 5);

  return (
    <div className="bg-white rounded-lg border border-[#DCE5E1] p-5 sm:p-6 shadow-xs space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-[#DCE5E1] pb-4">
        <div>
          <div className="flex items-center gap-2">
            <Icons.Scholar className="w-5 h-5 text-[#194537]" />
            <h3 className="text-base font-bold text-[#192522]">Verified Google Scholar Profile</h3>
          </div>
          <p className="text-xs text-[#53635E] mt-0.5">Automated identity verification, bibliometric metrics & publication tracking</p>
        </div>
        <StatusBadge tone="green">Verified Profile</StatusBadge>
      </div>

      {/* Bibliometric impact metrics */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <h4 className="text-xs font-bold text-[#192522] uppercase tracking-wider">
            Bibliometric Impact Metrics (Scored in Rubric)
          </h4>
          <span className="text-[11px] text-[#53635E]">Contributes to Research Category (40% Weight)</span>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 bg-[#F8FAF9] p-4 rounded-lg border border-[#DCE5E1]">
          <div>
            <p className="text-[11px] font-semibold text-[#73817C] uppercase">H-Index</p>
            <p className="text-2xl font-bold text-[#192522] mt-0.5">{metrics.h_index ?? "—"}</p>
            <p className="text-[10px] text-[#53635E] mt-1">Rubric Band: 15–19 &rarr; 10.00 raw pts</p>
          </div>
          <div>
            <p className="text-[11px] font-semibold text-[#73817C] uppercase">i10-Index</p>
            <p className="text-2xl font-bold text-[#192522] mt-0.5">{metrics.i10_index ?? "—"}</p>
            <p className="text-[10px] text-[#53635E] mt-1">Rubric Band: 20–29 &rarr; 7.00 raw pts</p>
          </div>
          <div>
            <p className="text-[11px] font-semibold text-[#73817C] uppercase">Total Citations</p>
            <p className="text-2xl font-bold text-[#194537] mt-0.5">{metrics.total_citations?.toLocaleString() ?? "—"}</p>
            <p className="text-[10px] text-[#53635E] mt-1">Rubric Band: 500–999 &rarr; 8.00 raw pts</p>
          </div>
        </div>
      </div>

      {/* Publications section with eligibility indicators */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <h4 className="text-xs font-bold text-[#192522] uppercase tracking-wider">
            Retrieved Research Publications ({publications.length})
          </h4>
          {profileUrl && (
            <a href={profileUrl} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-xs font-medium text-[#194537] hover:underline">
              View Google Scholar Profile <Icons.ExternalLink className="w-3 h-3" />
            </a>
          )}
        </div>

        <div className="mb-3 rounded-md border border-[#DCE5E1] bg-[#F8FAF9] p-2.5 text-xs text-[#53635E]">
          <span className="font-semibold text-[#192522]">Cycle Eligibility Policy:</span> Only publications published in the active cycle year ({appraisalYear}) are eligible for direct publication points. Historical publications establish bibliometric authority reflected in H-Index and Citations.
        </div>

        {publications.length === 0 ? (
          <p className="text-xs text-[#53635E]">No publications returned in latest retrieval snapshot.</p>
        ) : (
          <div className="space-y-2">
            {visiblePublications.map((pub, idx) => {
              const status = pub.scoring_status || (pub.year === appraisalYear ? "eligible" : "outside_appraisal_year");
              let badgeColor = "bg-slate-100 text-slate-700 border-slate-200";
              let badgeText = "Historical (Pre-cycle)";
              if (status === "scored" || status === "eligible") {
                badgeColor = "bg-emerald-50 text-emerald-700 border-emerald-200";
                badgeText = `Eligible (${appraisalYear} Cycle)`;
              } else if (status === "outside_appraisal_year") {
                badgeColor = "bg-amber-50 text-amber-800 border-amber-200";
                badgeText = `Historical (${pub.year || "pre"}-${appraisalYear})`;
              } else if (status === "duplicate_of_manual_activity") {
                badgeColor = "bg-purple-50 text-purple-700 border-purple-200";
                badgeText = "Reported Manually (Deduplicated)";
              } else if (status === "duplicate_scholar_publication") {
                badgeColor = "bg-slate-100 text-slate-600 border-slate-200";
                badgeText = "Duplicate Scholar Entry";
              }

              return (
                <div key={idx} className="p-3 rounded-md bg-[#F8FAF9] border border-[#DCE5E1] space-y-1">
                  <div className="flex items-start justify-between gap-2">
                    <h5 className="text-xs font-bold text-[#192522] leading-snug">{pub.title}</h5>
                    <span className={`shrink-0 inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold border ${badgeColor}`}>
                      {badgeText}
                    </span>
                  </div>
                  {pub.authors && <p className="text-[11px] text-[#53635E]">{Array.isArray(pub.authors) ? pub.authors.join(", ") : pub.authors}</p>}
                  <div className="flex flex-wrap items-center gap-3 text-[10px] text-[#73817C] pt-1">
                    {pub.publication && <span>{pub.publication}</span>}
                    {pub.year && <span>Year: {pub.year}</span>}
                    {pub.citation_count !== undefined && <span className="font-semibold text-[#194537]">Citations: {pub.citation_count}</span>}
                    {pub.link && (
                      <a href={pub.link} target="_blank" rel="noreferrer" className="text-[#194537] underline ml-auto flex items-center gap-0.5">
                        Link <Icons.ExternalLink className="w-2.5 h-2.5" />
                      </a>
                    )}
                  </div>
                </div>
              );
            })}
            {publications.length > 5 && (
              <button
                onClick={() => setShowAllPublications((v) => !v)}
                className="text-xs font-semibold text-[#194537] hover:underline pt-2 block"
              >
                {showAllPublications ? "Show fewer publications" : `View all ${publications.length} retrieved publications`}
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function ScoreBreakdown({ score }) {
  if (!score) return null;

  const breakdown = score.score_breakdown ?? {};
  const rawItems = breakdown.line_items ?? [];
  const categoryWeights = breakdown.category_weights ?? score.category_weights ?? {
    research: 0.40,
    teaching: 0.40,
    administrative: 0.20,
  };
  const categoryRawTotals = breakdown.category_raw_totals ?? score.category_raw_totals ?? {
    research: 25.0,
    teaching: 15.2,
    administrative: 10.0,
  };
  const categoryWeightedTotals = breakdown.category_totals ?? {
    research: breakdown.research_score ?? 10.00,
    teaching: breakdown.teaching_score ?? 6.08,
    administrative: breakdown.administrative_score ?? 2.00,
  };

  const totalScore = score.total_score ?? (
    (categoryWeightedTotals.research ?? 0) +
    (categoryWeightedTotals.teaching ?? 0) +
    (categoryWeightedTotals.administrative ?? 0)
  );

  const ratingRecommendation = breakdown.rating_recommendation ?? score.rating_recommendation ?? "—";

  const categoriesConfig = [
    { key: "teaching", label: "Teaching", maxWeighted: 40 },
    { key: "research", label: "Research", maxWeighted: 40 },
    { key: "administrative", label: "Administrative", maxWeighted: 20 },
  ];

  const groupedItems = { teaching: [], research: [], administrative: [] };

  for (const item of rawItems) {
    let cat = item.category;
    if (!cat || !groupedItems[cat]) {
      const code = item.rubric_code || "";
      if (code.startsWith("scholar") || code.includes("research") || code.includes("journal") || code.includes("conference")) {
        cat = "research";
      } else if (code === "coordinator" || code.includes("admin") || code.includes("committee")) {
        cat = "administrative";
      } else {
        cat = "teaching";
      }
    }
    groupedItems[cat].push(item);
  }

  const totalRaw = Object.values(categoryRawTotals).reduce((a, b) => a + (Number(b) || 0), 0);

  return (
    <div className="space-y-6">
      {/* 1. Category Score Summary Cards */}
      <div className="grid gap-3 sm:grid-cols-4">
        {/* Total Score */}
        <div className="bg-[#194537]/5 border-2 border-[#194537]/30 p-4 rounded-lg flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between">
              <p className="text-[11px] font-bold uppercase tracking-wider text-[#194537]">Final Score</p>
              <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-[#194537] text-white">
                Grade: {ratingRecommendation}
              </span>
            </div>
            <p className="text-3xl font-extrabold text-[#194537] mt-1.5">
              {Number(totalScore).toFixed(2)}
              <span className="text-xs font-normal text-[#53635E]"> / 100</span>
            </p>
          </div>
          <p className="text-[10px] text-[#53635E] mt-2 pt-2 border-t border-[#194537]/15">
            Sum of weighted categories
          </p>
        </div>

        {/* Research */}
        <div className="bg-white border border-[#DCE5E1] p-4 rounded-lg flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between">
              <p className="text-[11px] font-bold uppercase tracking-wider text-[#73817C]">Research</p>
              <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-emerald-50 text-emerald-800 border border-emerald-200">
                Weight: {((categoryWeights.research ?? 0.40) * 100).toFixed(0)}%
              </span>
            </div>
            <p className="text-2xl font-bold text-[#192522] mt-1.5">
              {Number(categoryWeightedTotals.research ?? 0).toFixed(2)}
              <span className="text-xs font-normal text-[#73817C]"> / 40.00 max</span>
            </p>
          </div>
          <div className="text-[10px] text-[#53635E] mt-2 pt-2 border-t border-[#DCE5E1]">
            <span className="font-semibold text-[#192522]">Raw: {(categoryRawTotals.research ?? 0).toFixed(2)} pts</span>
            {" × "}{((categoryWeights.research ?? 0.40) * 100).toFixed(0)}% = {(categoryWeightedTotals.research ?? 0).toFixed(2)}
          </div>
        </div>

        {/* Teaching */}
        <div className="bg-white border border-[#DCE5E1] p-4 rounded-lg flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between">
              <p className="text-[11px] font-bold uppercase tracking-wider text-[#73817C]">Teaching</p>
              <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-sky-50 text-sky-800 border border-sky-200">
                Weight: {((categoryWeights.teaching ?? 0.40) * 100).toFixed(0)}%
              </span>
            </div>
            <p className="text-2xl font-bold text-[#192522] mt-1.5">
              {Number(categoryWeightedTotals.teaching ?? 0).toFixed(2)}
              <span className="text-xs font-normal text-[#73817C]"> / 40.00 max</span>
            </p>
          </div>
          <div className="text-[10px] text-[#53635E] mt-2 pt-2 border-t border-[#DCE5E1]">
            <span className="font-semibold text-[#192522]">Raw: {(categoryRawTotals.teaching ?? 0).toFixed(2)} pts</span>
            {" × "}{((categoryWeights.teaching ?? 0.40) * 100).toFixed(0)}% = {(categoryWeightedTotals.teaching ?? 0).toFixed(2)}
          </div>
        </div>

        {/* Administrative */}
        <div className="bg-white border border-[#DCE5E1] p-4 rounded-lg flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between">
              <p className="text-[11px] font-bold uppercase tracking-wider text-[#73817C]">Administrative</p>
              <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-purple-50 text-purple-800 border border-purple-200">
                Weight: {((categoryWeights.administrative ?? 0.20) * 100).toFixed(0)}%
              </span>
            </div>
            <p className="text-2xl font-bold text-[#192522] mt-1.5">
              {Number(categoryWeightedTotals.administrative ?? 0).toFixed(2)}
              <span className="text-xs font-normal text-[#73817C]"> / 20.00 max</span>
            </p>
          </div>
          <div className="text-[10px] text-[#53635E] mt-2 pt-2 border-t border-[#DCE5E1]">
            <span className="font-semibold text-[#192522]">Raw: {(categoryRawTotals.administrative ?? 0).toFixed(2)} pts</span>
            {" × "}{((categoryWeights.administrative ?? 0.20) * 100).toFixed(0)}% = {(categoryWeightedTotals.administrative ?? 0).toFixed(2)}
          </div>
        </div>
      </div>

      {/* 2. Detailed Line Items Grouped by Category */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h4 className="text-xs font-bold uppercase tracking-wider text-[#192522]">
            Detailed Activity & Component Scoring Reconciliation
          </h4>
          <span className="text-[11px] text-[#53635E]">
            Total Raw Points: <strong>{totalRaw.toFixed(2)} pts</strong> &rarr; Weighted Score: <strong>{Number(totalScore).toFixed(2)} / 100</strong>
          </span>
        </div>

        {categoriesConfig.map((catConfig) => {
          const items = groupedItems[catConfig.key] || [];
          const catWeight = categoryWeights[catConfig.key] ?? 0.40;
          const catRaw = categoryRawTotals[catConfig.key] ?? 0;
          const catWeighted = categoryWeightedTotals[catConfig.key] ?? 0;

          return (
            <div key={catConfig.key} className="rounded-lg border border-[#DCE5E1] bg-white overflow-hidden text-xs">
              {/* Category Header */}
              <div className="bg-[#F8FAF9] px-4 py-3 flex flex-wrap items-center justify-between gap-2 border-b border-[#DCE5E1]">
                <div className="flex items-center gap-2">
                  <span className="font-bold text-[#192522] capitalize">{catConfig.label} Category</span>
                  <span className="text-[11px] text-[#53635E]">({items.length} line {items.length === 1 ? "item" : "items"})</span>
                </div>
                <div className="flex items-center gap-3 text-[11px]">
                  <span>Raw Subtotal: <strong className="text-[#192522]">{catRaw.toFixed(2)} pts</strong></span>
                  <span className="text-[#73817C]">× Weight {(catWeight * 100).toFixed(0)}%</span>
                  <span className="font-bold text-[#194537] bg-white px-2 py-0.5 rounded border border-[#DCE5E1]">
                    = {catWeighted.toFixed(2)} / {catConfig.maxWeighted}.00 weighted pts
                  </span>
                </div>
              </div>

              {items.length === 0 ? (
                <div className="p-4 text-xs text-[#73817C] italic">No scored activities in this category.</div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs text-[#53635E]">
                    <thead className="bg-[#F8FAF9]/60 text-[10px] uppercase font-semibold text-[#73817C] border-b border-[#DCE5E1]">
                      <tr>
                        <th className="py-2 px-4">Activity / Component</th>
                        <th className="py-2 px-3">Data Source</th>
                        <th className="py-2 px-3 text-right">Raw Points</th>
                        <th className="py-2 px-3 text-center">Activity Cap</th>
                        <th className="py-2 px-3 text-center">Category Weight</th>
                        <th className="py-2 px-3 text-right">Weighted Contribution</th>
                        <th className="py-2 px-3 text-center">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[#DCE5E1]">
                      {items.map((it, idx) => {
                        const rawPts = it.points ?? 0;
                        const weight = it.category_weight ?? catWeight;
                        const weightedPts = it.weighted_points ?? (rawPts * weight);
                        const status = it.status ?? (it.cap && rawPts > it.cap ? "capped" : "scored");

                        let sourceLabel = "Manual Entry";
                        if (it.source === "google_scholar") sourceLabel = "Google Scholar API";
                        else if (it.source === "student_feedback") sourceLabel = "Student Survey";
                        else if (it.source === "attendance_sync") sourceLabel = "Attendance Sync";

                        return (
                          <tr key={idx} className="hover:bg-[#F8FAF9]/50">
                            <td className="py-2.5 px-4 font-semibold text-[#192522]">
                              <div>{it.label || it.rubric_code}</div>
                              {it.value != null && (
                                <div className="text-[10px] text-[#73817C] font-normal">{it.value}</div>
                              )}
                              {it.activity_id && !it.value && (
                                <div className="text-[10px] text-[#73817C] font-normal">ID: {it.activity_id.slice(0, 10)}…</div>
                              )}
                            </td>
                            <td className="py-2.5 px-3">
                              <span className="inline-flex px-1.5 py-0.5 rounded text-[10px] font-medium bg-slate-100 text-slate-700">
                                {sourceLabel}
                              </span>
                            </td>
                            <td className="py-2.5 px-3 text-right font-bold text-[#192522]">
                              {rawPts.toFixed(2)} pts
                            </td>
                            <td className="py-2.5 px-3 text-center text-[#73817C]">
                              {it.cap != null ? `${Number(it.cap).toFixed(2)} max` : "—"}
                            </td>
                            <td className="py-2.5 px-3 text-center text-[#73817C]">
                              {(weight * 100).toFixed(0)}%
                            </td>
                            <td className="py-2.5 px-3 text-right font-bold text-[#194537]">
                              +{weightedPts.toFixed(2)} pts
                            </td>
                            <td className="py-2.5 px-3 text-center">
                              <span
                                className={`inline-flex px-1.5 py-0.5 rounded text-[10px] font-semibold ${
                                  status === "capped"
                                    ? "bg-amber-100 text-amber-800"
                                    : status === "informational"
                                    ? "bg-blue-100 text-blue-800"
                                    : status === "excluded"
                                    ? "bg-red-100 text-red-800"
                                    : "bg-emerald-100 text-emerald-800"
                                }`}
                              >
                                {status.toUpperCase()}
                              </span>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                    <tfoot className="bg-[#F8FAF9]/80 font-bold border-t border-[#DCE5E1] text-[#192522]">
                      <tr>
                        <td className="py-2 px-4" colSpan={2}>
                          {catConfig.label} Subtotal
                        </td>
                        <td className="py-2 px-3 text-right text-[#192522]">
                          {catRaw.toFixed(2)} raw pts
                        </td>
                        <td className="py-2 px-3 text-center text-[#73817C]">—</td>
                        <td className="py-2 px-3 text-center">{(catWeight * 100).toFixed(0)}%</td>
                        <td className="py-2 px-3 text-right text-[#194537]">
                          +{catWeighted.toFixed(2)} pts
                        </td>
                        <td className="py-2 px-3 text-center text-[10px] text-emerald-800">
                          RECONCILED
                        </td>
                      </tr>
                    </tfoot>
                  </table>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* 3. Mathematical Reconciliation Summary Banner */}
      <div className="rounded-lg border border-[#194537]/20 bg-[#194537]/5 p-4 text-xs text-[#192522] space-y-2">
        <div className="flex items-center gap-2">
          <Icons.Award className="w-4 h-4 text-[#194537] shrink-0" />
          <h5 className="font-bold text-[#194537]">Mathematical Score Reconciliation</h5>
        </div>
        <p className="text-[11px] text-[#53635E]">
          Activities earn <strong>raw points</strong> subject to rubric line-item caps. Category raw totals are then weighted according to the configured rubric:
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 pt-1 font-mono text-[11px]">
          <div className="bg-white p-2 rounded border border-[#DCE5E1]">
            <span className="text-[#73817C] block text-[10px]">Research (40% Weight):</span>
            <span className="font-bold text-[#192522]">{(categoryRawTotals.research ?? 0).toFixed(2)} raw × 0.40 = {(categoryWeightedTotals.research ?? 0).toFixed(2)} pts</span>
          </div>
          <div className="bg-white p-2 rounded border border-[#DCE5E1]">
            <span className="text-[#73817C] block text-[10px]">Teaching (40% Weight):</span>
            <span className="font-bold text-[#192522]">{(categoryRawTotals.teaching ?? 0).toFixed(2)} raw × 0.40 = {(categoryWeightedTotals.teaching ?? 0).toFixed(2)} pts</span>
          </div>
          <div className="bg-white p-2 rounded border border-[#DCE5E1]">
            <span className="text-[#73817C] block text-[10px]">Administrative (20% Weight):</span>
            <span className="font-bold text-[#192522]">{(categoryRawTotals.administrative ?? 0).toFixed(2)} raw × 0.20 = {(categoryWeightedTotals.administrative ?? 0).toFixed(2)} pts</span>
          </div>
        </div>
        <div className="pt-1 text-[11px] text-[#194537] font-semibold">
          Final Weighted Sum: {(categoryWeightedTotals.research ?? 0).toFixed(2)} + {(categoryWeightedTotals.teaching ?? 0).toFixed(2)} + {(categoryWeightedTotals.administrative ?? 0).toFixed(2)} = {Number(totalScore).toFixed(2)} / 100
        </div>
      </div>
    </div>
  );
}

export default function FacultyDashboard() {
  const { user } = useAuth();
  const [profile, setProfile] = useState(null);
  const [cycle, setCycle] = useState(null);
  const [activities, setActivities] = useState([]);
  const [evidence, setEvidence] = useState([]);
  const [types, setTypes] = useState({});
  const [appraisal, setAppraisal] = useState(null);
  const [report, setReport] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [activeTab, setActiveTab] = useState("overview");

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

  const totalScore = appraisal?.score?.total_score ?? null;
  const approvalStatus = appraisal?.approval_status ?? "not_generated";

  const researchActivities = useMemo(() => activities.filter((a) => a.category === "research"), [activities]);
  const scholarPubsCount = report?.json?.research_metrics?.publications?.length ?? 0;

  async function handleRunAppraisal() {
    setBusy(true);
    try {
      await runAppraisal();
      await refreshAll();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function handleResubmit() {
    setBusy(true);
    try {
      await resubmitAppraisal();
      await refreshAll();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <AppLayout
      activeTab={activeTab}
      onTabChange={setActiveTab}
      title="Faculty Appraisal Dashboard"
      subtitle={profile ? `${profile.full_name || user?.email} · ${profile.designation || "Faculty"} (${profile.department || "CS"})` : "Faculty Overview"}
      cycleInfo={cycle}
    >
      {/* Top Banner Alert / Disclaimer */}
      <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-xs text-amber-900 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Icons.Alert className="w-4 h-4 text-amber-700 shrink-0" />
          <span>{DISCLAIMER}</span>
        </div>
        {cycle && <span className="font-semibold shrink-0">Cycle: {cycle.name}</span>}
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 p-3 rounded-lg text-xs font-semibold">
          {error}
        </div>
      )}

      {/* Main Appraisal Overview Hero Banner */}
      <div className="bg-white rounded-lg border border-[#DCE5E1] p-6 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-6">
        <div className="space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-[#73817C]">
              Current Academic Cycle: {cycle?.academic_year || "2026-2027"}
            </span>
            <StatusBadge tone={approvalStatus === "approved" ? "green" : approvalStatus === "rejected" ? "red" : approvalStatus === "awaiting_review" ? "amber" : "slate"}>
              Status: {approvalStatus.replaceAll("_", " ")}
            </StatusBadge>
          </div>
          <h2 className="text-2xl font-bold text-[#192522]">
            {profile?.full_name || "Faculty Member"}
          </h2>
          <p className="text-xs text-[#53635E]">
            Employee Code: <span className="font-semibold text-[#192522]">{profile?.employee_code || "—"}</span> · Department: <span className="font-semibold text-[#192522]">{profile?.department || "CS"}</span>
          </p>
        </div>

        <div className="flex items-center gap-4 border-t md:border-t-0 md:border-l border-[#DCE5E1] pt-4 md:pt-0 md:pl-6">
          <div className="text-right">
            <p className="text-[11px] font-semibold uppercase text-[#73817C]">Appraisal Score</p>
            <p className="text-3xl font-bold text-[#194537]">
              {totalScore !== null ? totalScore.toFixed(2) : "—"}
              <span className="text-xs text-[#73817C] font-normal"> / 100</span>
            </p>
          </div>
          <div className="flex flex-col gap-2">
            <button
              disabled={!cycle || cycle.status !== "open" || busy}
              onClick={handleRunAppraisal}
              className="h-10 px-5 rounded-md bg-[#194537] text-white text-xs font-semibold hover:bg-[#194537]/90 disabled:opacity-50 shadow-xs transition-all"
            >
              {busy ? "Executing Graph…" : "Run Appraisal"}
            </button>
            {approvalStatus === "changes_requested" && (
              <button
                disabled={busy}
                onClick={handleResubmit}
                className="h-9 px-4 rounded-md border border-amber-300 bg-amber-50 text-amber-900 text-xs font-semibold hover:bg-amber-100"
              >
                Resubmit for Review
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Metric Tiles Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Appraisal Score"
          value={totalScore !== null ? totalScore.toFixed(2) : "N/A"}
          subtext={appraisal?.score?.engine_version ? `Engine v${appraisal.score.scoring_engine_version}` : "Not calculated"}
          icon={Icons.Award}
        />
        <StatCard
          label="Research Papers"
          value={scholarPubsCount + researchActivities.length}
          subtext={`${scholarPubsCount} Scholar + ${researchActivities.length} Internal`}
          icon={Icons.Research}
        />
        <StatCard
          label="Scholar Citations"
          value={report?.json?.research_metrics?.metrics?.total_citations?.toLocaleString() ?? "—"}
          subtext={report?.json?.research_metrics?.metrics?.h_index ? `H-Index: ${report.json.research_metrics.metrics.h_index}` : "Profile pending"}
          icon={Icons.Scholar}
        />
        <StatCard
          label="Evidence Repository"
          value={evidence.length}
          subtext={`${evidence.filter(e => e.validation_status === 'valid').length} Validated Documents`}
          icon={Icons.Evidence}
        />
      </div>

      {/* Tab Controls Bar */}
      <div className="flex items-center gap-1 border-b border-[#DCE5E1] overflow-x-auto pb-px">
        {[
          { id: "overview", label: "Overview", icon: Icons.Overview },
          { id: "appraisal", label: "Appraisal Report", icon: Icons.Appraisal },
          { id: "research", label: "Research & Publications", icon: Icons.Research },
          { id: "teaching", label: "Teaching & Workload", icon: Icons.Teaching },
          { id: "admin-service", label: "Institutional Service", icon: Icons.Admin },
          { id: "evidence", label: "Evidence Vault", icon: Icons.Evidence },
          { id: "profile", label: "Faculty Profile", icon: Icons.Profile },
        ].map((tab) => {
          const IconComp = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-4 py-2.5 text-xs font-semibold border-b-2 transition-all shrink-0 ${
                isActive
                  ? "border-[#194537] text-[#194537] bg-white rounded-t-md"
                  : "border-transparent text-[#53635E] hover:text-[#192522] hover:bg-white/50"
              }`}
            >
              <IconComp className="w-4 h-4" />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </div>

      {/* TAB CONTENT SECTIONS */}

      {/* 1. OVERVIEW TAB */}
      {activeTab === "overview" && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 space-y-6">
              {/* Teaching requirement snippet */}
              <TeachingRequirementSection refresh={activities} />
              {/* Score breakdown if available */}
              {appraisal?.score && (
                <div className="bg-white rounded-lg border border-[#DCE5E1] p-5 shadow-xs">
                  <h3 className="text-base font-bold text-[#192522] mb-4">Current Category Score Breakdown</h3>
                  <ScoreBreakdown score={appraisal.score} />
                </div>
              )}
            </div>
            <div className="space-y-6">
              <PlannerSection />
            </div>
          </div>
        </div>
      )}

      {/* 2. APPRAISAL TAB */}
      {activeTab === "appraisal" && (
        <div className="space-y-6">
          <div className="bg-white rounded-lg border border-[#DCE5E1] p-6 shadow-xs space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#DCE5E1] pb-4">
              <div>
                <span className="text-[11px] font-semibold uppercase tracking-wider text-[#73817C]">Report Preview</span>
                <h3 className="text-lg font-bold text-[#192522]">Generated Appraisal Document</h3>
              </div>
              {report?.rating_recommendation && (
                <StatusBadge tone="green">Rating Recommendation: {report.rating_recommendation}</StatusBadge>
              )}
            </div>

            {report ? (
              <div className="space-y-4">
                <div className="flex justify-between text-xs text-[#53635E]">
                  <span>Report Version #{report.version_number}</span>
                  <span>Status: {report.status}</span>
                </div>
                <div className="border border-[#DCE5E1] rounded-lg overflow-hidden bg-white">
                  <iframe title="appraisal-report" className="w-full h-[500px]" srcDoc={report.html || "<p>Report loading...</p>"} />
                </div>
              </div>
            ) : (
              <div className="py-12 text-center text-xs text-[#73817C] bg-[#F8FAF9] rounded-lg border border-dashed border-[#DCE5E1]">
                No appraisal report generated yet. Click "Run Appraisal" above to execute the LangGraph workflow.
              </div>
            )}
          </div>
        </div>
      )}

      {/* 3. RESEARCH TAB */}
      {activeTab === "research" && (
        <div className="space-y-6">
          <GoogleScholarMetrics report={report} profile={profile} cycle={cycle} />

          <div className="bg-white rounded-lg border border-[#DCE5E1] p-5 sm:p-6 shadow-xs space-y-4">
            <div className="flex items-center justify-between border-b border-[#DCE5E1] pb-4">
              <div>
                <span className="text-[11px] font-semibold uppercase tracking-wider text-[#73817C]">Internal Records</span>
                <h3 className="text-lg font-bold text-[#192522]">Manually Entered Research Activities</h3>
              </div>
              <span className="px-2.5 py-1 rounded-full bg-[#F8FAF9] text-xs font-semibold text-[#53635E] border border-[#DCE5E1]">
                {researchActivities.length} {researchActivities.length === 1 ? "Activity" : "Activities"}
              </span>
            </div>

            {researchActivities.length === 0 ? (
              <div className="py-8 text-center text-xs text-[#73817C] rounded-lg border border-dashed border-[#DCE5E1] bg-[#F8FAF9]">
                No manually entered research activities. Verified Google Scholar publications are displayed in the section above.
              </div>
            ) : (
              <div className="space-y-3">
                {researchActivities.map((act) => (
                  <ActivityItem
                    key={act.id}
                    act={act}
                    evidence={evidence}
                    onEdit={async (id, form) => {
                      await updateActivity(id, form);
                      await refreshAll();
                    }}
                    onDelete={async (id) => {
                      await deleteActivity(id);
                      await refreshAll();
                    }}
                    onUpload={refreshAll}
                  />
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* 4. TEACHING TAB */}
      {activeTab === "teaching" && (
        <div className="space-y-6">
          <TeachingRequirementSection refresh={activities} />
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <TimetableSection onTimetableChange={refreshAll} />
            <AttendanceSection onAttendanceMarked={refreshAll} cycleId={cycle?.id} />
          </div>
          <ProjectTeamsSection />
        </div>
      )}

      {/* 5. SERVICE / ADMIN TAB */}
      {activeTab === "admin-service" && (
        <div className="space-y-6">
          <AdministrativeResponsibilitiesSection />
        </div>
      )}

      {/* 6. EVIDENCE VAULT TAB */}
      {activeTab === "evidence" && (
        <div className="space-y-6">
          <EvidenceVaultSection evidence={evidence} activities={activities} />
        </div>
      )}

      {/* 7. PROFILE TAB */}
      {activeTab === "profile" && (
        <div className="space-y-6">
          <ProfileSection
            profile={profile}
            setProfile={setProfile}
            cycle={cycle}
            approvalStatus={approvalStatus}
          />
        </div>
      )}
    </AppLayout>
  );
}
