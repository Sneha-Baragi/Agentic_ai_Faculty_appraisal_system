import { useEffect, useMemo, useState } from "react";
import { useAuth } from "../auth/AuthContext.jsx";
import {
  approveReviewerAppraisal,
  editReviewerReport,
  fetchReviewerFacultyPacket,
  listReviewerFaculty,
  overrideReviewerReport,
  publishReviewerReport,
  rejectReviewerAppraisal,
  requestReviewerChanges,
  rollbackReviewerReport,
} from "../api/client.js";

const DISCLAIMER = "DEMO/TEST WEIGHTAGES — NOT OFFICIAL UGC";

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

function FacultyList({ faculty, selectedId, onSelect }) {
  return (
    <aside className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm lg:sticky lg:top-4">
      <p className="text-xs uppercase tracking-[0.2em] text-accent">Review queue</p>
      <h2 className="font-display mt-1 text-xl">Faculty</h2>
      <p className="mt-1 text-xs text-slate-500">Select a faculty member to open their appraisal packet.</p>
      <ul className="mt-4 space-y-2">
        {faculty.map((f) => {
          const active = selectedId === f.id;
          return (
            <li key={f.id}>
              <button
                onClick={() => onSelect(f.id)}
                className={`w-full rounded border px-3 py-2 text-left text-sm ${
                  active ? "border-accent bg-accent/5 font-semibold" : "border-slate-200 bg-white hover:bg-slate-50"
                }`}
              >
                <p className="truncate">{f.full_name ?? f.email ?? f.id}</p>
                <p className="truncate text-xs text-slate-500">
                  {f.department ?? "—"} · {f.designation ?? "—"}
                </p>
              </button>
            </li>
          );
        })}
        {faculty.length === 0 ? (
          <li className="rounded border border-dashed border-slate-300 p-3 text-center text-sm text-slate-400">
            No faculty yet.
          </li>
        ) : null}
      </ul>
    </aside>
  );
}

function Section({ title, eyebrow, children }) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      {eyebrow ? <p className="text-xs uppercase tracking-[0.2em] text-accent">{eyebrow}</p> : null}
      <h2 className="font-display mt-1 text-xl">{title}</h2>
      <div className="mt-4 text-sm">{children}</div>
    </section>
  );
}

function Row({ label, value }) {
  return (
    <div className="flex flex-wrap justify-between gap-2 py-1">
      <span className="text-slate-500">{label}</span>
      <span className="font-medium text-ink">{value ?? "—"}</span>
    </div>
  );
}

function Packet({ packet, onDecision, onGovernance }) {
  const profile = packet?.profile ?? null;
  const cycle = packet?.cycle ?? null;
  const activities = packet?.activities ?? [];
  const evidence = packet?.evidence ?? [];
  const appraisal = packet?.appraisal ?? null;
  const report = packet?.report ?? null;
  const score = packet?.score ?? null;
  const breakdown = score?.score_breakdown?.line_items ?? [];
  const groups = useMemo(() => {
    const g = { research: [], teaching: [], administrative: [] };
    for (const a of activities) g[a.category]?.push(a);
    return g;
  }, [activities]);

  return (
    <div className="space-y-4">
      <div className="grid gap-4 md:grid-cols-2">
        <Section eyebrow="Faculty" title={profile?.full_name ?? profile?.email ?? "Faculty"}>
          <Row label="Employee code" value={profile?.employee_code} />
          <Row label="Department" value={profile?.department} />
          <Row label="Designation" value={profile?.designation} />
          <Row label="Institution" value={profile?.institution} />
          <Row label="Joining date" value={profile?.joining_date} />
        </Section>
        <Section eyebrow="Cycle" title={cycle?.name ?? "n/a"}>
          <Row label="Academic year" value={cycle?.academic_year} />
          <Row label="Start" value={cycle?.start_date} />
          <Row label="End" value={cycle?.end_date} />
          <Row label="Status" value={<Pill tone={cycle?.status === "open" ? "green" : "slate"}>{cycle?.status ?? "n/a"}</Pill>} />
        </Section>
      </div>

      <Section eyebrow="Appraisal status" title="Current run">
        <Row label="Run status" value={appraisal?.status ?? "n/a"} />
        <Row
          label="Approval"
          value={
            <Pill tone={appraisal?.approval_status === "awaiting_review" ? "green" : "slate"}>
              {appraisal?.approval_status ?? "n/a"}
            </Pill>
          }
        />
        <Row label="Scoring engine" value={score?.scoring_engine_version ? `v${score.scoring_engine_version}` : "n/a"} />
        <Row label="Disclaimer" value={DISCLAIMER} />
        {appraisal?.approval_status === "awaiting_review" ? (
          <div className="mt-4 flex flex-wrap gap-2">
            <button onClick={() => onDecision("approve")} className="rounded bg-emerald-600 px-3 py-2 text-sm font-semibold text-white">Approve</button>
            <button onClick={() => onDecision("reject")} className="rounded bg-red-600 px-3 py-2 text-sm font-semibold text-white">Reject</button>
            <button onClick={() => onDecision("request_changes")} className="rounded border border-amber-500 px-3 py-2 text-sm font-semibold text-amber-800">Request Changes</button>
          </div>
        ) : null}
        {appraisal?.approval_status === "approved" ? <p className="mt-3 text-sm text-emerald-700">Approved by {appraisal.reviewer_email ?? "reviewer"} on {appraisal.approved_at ?? "—"}.</p> : null}
        {appraisal?.approval_status === "rejected" ? <p className="mt-3 text-sm text-red-700">Rejected. Reason: {appraisal.rejection_reason ?? "—"}</p> : null}
        {appraisal?.approval_status === "changes_requested" ? <p className="mt-3 text-sm text-amber-800">Changes requested. Reason: {appraisal.change_request_reason ?? "—"}</p> : null}
        {report?.status !== "published" && report ? (
          <div className="mt-4 flex flex-wrap gap-2 border-t border-slate-200 pt-4">
            <button onClick={() => onGovernance("edit")} className="rounded border border-slate-300 px-3 py-2 text-sm">Edit rating</button>
            <button onClick={() => onGovernance("override")} className="rounded border border-red-300 px-3 py-2 text-sm text-red-700">Override score</button>
            {appraisal?.approval_status === "approved" ? <button onClick={() => onGovernance("publish")} className="rounded bg-accent px-3 py-2 text-sm font-semibold text-white">Publish approved version</button> : null}
          </div>
        ) : null}
      </Section>

      {score ? (
        <Section eyebrow="Score" title={`${score.total_score?.toFixed?.(2) ?? score.total_score ?? 0} / 100`}>
          <div className="grid gap-3 md:grid-cols-4">
            <div className="rounded border border-accent/30 bg-accent/5 p-3">
              <p className="text-xs uppercase tracking-widest text-slate-500">Total</p>
              <p className="font-display mt-1 text-2xl text-accent">{score.total_score?.toFixed?.(2) ?? score.total_score ?? 0}</p>
            </div>
            {[
              { k: "research_score", label: "Research" },
              { k: "teaching_score", label: "Teaching" },
              { k: "administrative_score", label: "Administrative" },
            ].map((c) => (
              <div key={c.k} className="rounded border border-slate-200 bg-white p-3">
                <p className="text-xs uppercase tracking-widest text-slate-500">{c.label}</p>
                <p className="font-display mt-1 text-2xl">
                  {(score.score_breakdown?.[c.k] ?? 0)?.toFixed?.(2) ?? score.score_breakdown?.[c.k] ?? 0}
                </p>
              </div>
            ))}
          </div>
          {breakdown.length > 0 ? (
            <div className="mt-5">
              <h3 className="text-sm font-semibold text-ink">Score breakdown</h3>
              <div className="mt-2 overflow-hidden rounded border border-slate-200">
                <ul className="divide-y divide-slate-100 text-sm">
                  {breakdown.map((it, i) => (
                    <li key={`${it.activity_id}-${i}`} className="flex flex-wrap items-center justify-between gap-2 px-4 py-2">
                      <div>
                        <Pill>{it.rubric_code ?? "—"}</Pill>
                        <span className="ml-2 text-slate-700">
                          Activity {it.activity_id?.slice?.(0, 8) ?? it.activity_id}
                        </span>
                      </div>
                      <div className="text-right">
                        <p className="font-semibold text-accent">{it.points?.toFixed?.(2) ?? it.points ?? 0}</p>
                        <p className="text-xs text-slate-500">
                          evidence: {(it.evidence_ids ?? []).map((e) => e?.slice?.(0, 6) ?? e).join(", ") || "none"}
                        </p>
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          ) : null}
        </Section>
      ) : null}

      {["research", "teaching", "administrative"].map((cat) => (
        <Section key={cat} eyebrow="Activities" title={`${cat} (${groups[cat].length})`}>
          {groups[cat].length === 0 ? (
            <p className="text-slate-400">No {cat} activities.</p>
          ) : (
            <ul className="space-y-3">
              {groups[cat].map((a) => {
                const actEvidence = evidence.filter((e) => e.activity_id === a.id);
                return (
                  <li key={a.id} className="rounded border border-slate-200 bg-slate-50 p-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <Pill tone="blue">{a.category}</Pill>
                      <Pill>{a.activity_type ?? "—"}</Pill>
                      {a.rubric_code ? <Pill tone="amber">{a.rubric_code}</Pill> : null}
                      <span className="font-semibold text-ink">{a.title}</span>
                    </div>
                    {a.description ? (
                      <p className="mt-2 whitespace-pre-wrap text-slate-600">{a.description}</p>
                    ) : null}
                    {actEvidence.length > 0 ? (
                      <ul className="mt-3 space-y-2">
                        {actEvidence.map((e) => (
                          <li key={e.id} className="rounded border border-white bg-white p-2 text-xs">
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              <span className="font-medium text-ink">{e.original_filename ?? "evidence"}</span>
                              <div className="flex flex-wrap gap-1">
                                <Pill
                                  tone={
                                    e.validation_status === "valid"
                                      ? "green"
                                      : e.validation_status === "invalid"
                                      ? "red"
                                      : "amber"
                                  }
                                >
                                  validation: {e.validation_status}
                                </Pill>
                                <Pill
                                  tone={
                                    e.extraction_status === "extracted"
                                      ? "green"
                                      : e.extraction_status === "failed"
                                      ? "red"
                                      : "amber"
                                  }
                                >
                                  extraction: {e.extraction_status}
                                </Pill>
                              </div>
                            </div>
                            <div className="mt-1 text-slate-500">
                              sha256: {e.checksum?.slice?.(0, 12) ?? "—"} · {e.file_size ?? 0} bytes
                            </div>
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="mt-2 text-xs text-slate-500">No evidence.</p>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </Section>
      ))}

      {report ? (
        <Section eyebrow="Report" title={`Version ${report.version_number ?? 1}`}>
          <Row
            label={appraisal?.approval_status === "approved" || report.status === "published" ? "Final Rating" : "Recommended Rating"}
            value={
              <Pill tone={report.rating_recommendation === "A" || report.rating_recommendation === "B" ? "green" : "amber"}>
                {report.rating_recommendation ?? "—"}
              </Pill>
            }
          />
          <Row label="Status" value={report.status ?? "—"} />
          <div className="mt-3 overflow-hidden rounded border border-slate-200 bg-white">
            <iframe title="report" className="h-96 w-full bg-white" srcDoc={report.html ?? ""} />
          </div>
        </Section>
      ) : null}
      {packet.report_history?.length ? (
        <Section eyebrow="Governance" title="Version history">
          <ul className="divide-y divide-slate-100">
            {packet.report_history.map((version) => (
              <li key={version.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
                <span>Version {version.version_number} · {version.status} · {version.rating_recommendation ?? "—"}</span>
                {!version.is_current && version.status !== "published" && report?.status !== "published" ? (
                  <button onClick={() => onGovernance("rollback", version.id)} className="rounded border border-slate-300 px-2 py-1 text-xs">Rollback</button>
                ) : null}
              </li>
            ))}
          </ul>
        </Section>
      ) : null}
    </div>
  );
}

export default function ReviewerDashboard() {
  const { user, logout } = useAuth();
  const [faculty, setFaculty] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [packet, setPacket] = useState(null);
  const [error, setError] = useState("");

  async function handleDecision(action) {
    const reason = action === "approve" ? null : window.prompt(action === "reject" ? "Reason for rejection" : "Requested changes")?.trim();
    if (action !== "approve" && !reason) return;
    if (action === "approve" && !window.confirm("Are you sure you want to approve this appraisal?")) return;
    try {
      const payload = reason ? { reason } : {};
      if (action === "approve") await approveReviewerAppraisal(selectedId, payload);
      if (action === "reject") await rejectReviewerAppraisal(selectedId, payload);
      if (action === "request_changes") await requestReviewerChanges(selectedId, payload);
      setPacket(await fetchReviewerFacultyPacket(selectedId));
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleGovernance(action, versionId) {
    try {
      if (action === "publish") {
        if (!window.confirm("Publish this approved report version? Published versions cannot be changed.")) return;
        await publishReviewerReport(selectedId);
      } else if (action === "edit") {
        const rating = window.prompt("Final recommended rating", packet?.report?.rating_recommendation ?? "");
        if (!rating?.trim()) return;
        await editReviewerReport(selectedId, { rating_recommendation: rating.trim(), comment: "HOD report edit" });
      } else if (action === "override") {
        const reason = window.prompt("Mandatory reason for score override")?.trim();
        const total = window.prompt("Override total score")?.trim();
        if (!reason || !total || Number.isNaN(Number(total))) return;
        await overrideReviewerReport(selectedId, { reason, total_score: Number(total) });
      } else if (action === "rollback") {
        const reason = window.prompt("Mandatory reason for rollback")?.trim();
        if (!reason) return;
        await rollbackReviewerReport(selectedId, { version_id: versionId, reason });
      }
      setPacket(await fetchReviewerFacultyPacket(selectedId));
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const list = await listReviewerFaculty();
        if (!mounted) return;
        setFaculty(list);
        if (list.length > 0) setSelectedId(list[0].id);
      } catch (err) {
        if (mounted) setError(err.message);
      }
    })();
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    if (!selectedId) return;
    let mounted = true;
    (async () => {
      try {
        setPacket(null);
        const p = await fetchReviewerFacultyPacket(selectedId);
        if (mounted) setPacket(p);
      } catch (err) {
        if (mounted) setError(err.message);
      }
    })();
    return () => {
      mounted = false;
    };
  }, [selectedId]);

  return (
    <main className="mx-auto max-w-7xl px-6 py-10">
      <header className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.2em] text-accent">Reviewer workspace</p>
          <h1 className="font-display mt-1 text-3xl">Appraisal review queue</h1>
          <p className="mt-2 text-sm text-slate-600">{user?.email} · roles: {(user?.roles ?? []).join(", ")}</p>
        </div>
        <button onClick={logout} className="text-sm underline">
          Sign out
        </button>
      </header>
      <div className="mt-4 rounded border border-amber-200 bg-amber-50 px-3 py-2 text-sm">{DISCLAIMER}</div>
      {error ? <p className="mt-3 text-sm text-red-700">{error}</p> : null}

      <div className="mt-8 grid gap-4 lg:grid-cols-[300px_1fr]">
        <FacultyList faculty={faculty} selectedId={selectedId} onSelect={setSelectedId} />
        <div>
          {!selectedId ? (
            <p className="text-sm text-slate-500">Select a faculty member on the left.</p>
          ) : packet ? (
            <Packet packet={packet} onDecision={handleDecision} onGovernance={handleGovernance} />
          ) : (
            <p className="text-sm text-slate-500">Loading packet…</p>
          )}
        </div>
      </div>
    </main>
  );
}
