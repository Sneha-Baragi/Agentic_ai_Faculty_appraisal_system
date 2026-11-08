import { useEffect, useMemo, useState } from "react";
import { useAuth } from "../auth/AuthContext.jsx";
import AppLayout from "../components/layout/AppLayout.jsx";
import { Icons } from "../components/ui/Icons.jsx";
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

function FacultyList({ faculty, selectedId, onSelect }) {
  return (
    <aside className="bg-white rounded-lg border border-[#DCE5E1] p-4 shadow-xs lg:sticky lg:top-20 space-y-3">
      <div className="border-b border-[#DCE5E1] pb-3">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-[#73817C]">Review Queue</span>
        <h3 className="text-base font-bold text-[#192522]">Faculty Members ({faculty.length})</h3>
        <p className="text-xs text-[#53635E] mt-0.5">Select a faculty member to inspect their appraisal packet.</p>
      </div>
      <ul className="space-y-1.5 max-h-[calc(100vh-220px)] overflow-y-auto">
        {faculty.map((f) => {
          const active = selectedId === f.id;
          return (
            <li key={f.id}>
              <button
                onClick={() => onSelect(f.id)}
                className={`w-full text-left p-3 rounded-md transition-all border ${
                  active
                    ? "bg-[#194537] text-white border-[#194537] shadow-xs"
                    : "bg-white text-[#192522] border-[#DCE5E1] hover:bg-[#F8FAF9]"
                }`}
              >
                <p className="font-bold text-xs truncate">{f.full_name ?? f.email ?? f.id}</p>
                <p className={`text-[11px] truncate mt-0.5 ${active ? "text-emerald-100" : "text-[#53635E]"}`}>
                  {f.department ?? "CS"} · {f.designation ?? "Faculty"}
                </p>
                {f.has_score && (
                  <p className={`text-[10px] font-semibold mt-1 ${active ? "text-emerald-200" : "text-[#194537]"}`}>
                    Score: {f.total_score ? f.total_score.toFixed(2) : "Calculated"}
                  </p>
                )}
              </button>
            </li>
          );
        })}
        {faculty.length === 0 && (
          <li className="p-4 text-center text-xs text-[#73817C] rounded bg-[#F8FAF9] border border-dashed border-[#DCE5E1]">
            No faculty members found in cycle queue.
          </li>
        )}
      </ul>
    </aside>
  );
}

export default function ReviewerDashboard() {
  const { user } = useAuth();
  const [faculty, setFaculty] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [packet, setPacket] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [actionMsg, setActionMsg] = useState("");

  const reviewerNavItems = [
    { id: "queue", label: "Review Queue", icon: Icons.Review },
    { id: "faculty-list", label: "Faculty Packets", icon: Icons.Users },
  ];

  useEffect(() => {
    (async () => {
      try {
        setLoading(true);
        const list = await listReviewerFaculty();
        setFaculty(list);
        if (list.length > 0) {
          setSelectedId(list[0].id);
        }
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  useEffect(() => {
    if (!selectedId) return;
    (async () => {
      try {
        setPacket(await fetchReviewerFacultyPacket(selectedId));
      } catch (err) {
        setError(err.message);
      }
    })();
  }, [selectedId]);

  async function refreshCurrentPacket() {
    if (selectedId) {
      setPacket(await fetchReviewerFacultyPacket(selectedId));
      const list = await listReviewerFaculty();
      setFaculty(list);
    }
  }

  async function handleDecision(action) {
    if (!selectedId) return;
    setActionMsg("");
    setError("");
    try {
      if (action === "approve") {
        await approveReviewerAppraisal(selectedId, { comment: "Approved by reviewer." });
        setActionMsg("Appraisal approved.");
      } else if (action === "reject") {
        const reason = prompt("Enter rejection reason:");
        if (!reason) return;
        await rejectReviewerAppraisal(selectedId, { reason });
        setActionMsg("Appraisal rejected.");
      } else if (action === "request_changes") {
        const reason = prompt("Enter required changes:");
        if (!reason) return;
        await requestReviewerChanges(selectedId, { reason });
        setActionMsg("Changes requested.");
      }
      await refreshCurrentPacket();
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleGovernance(action, extraId) {
    if (!selectedId) return;
    setActionMsg("");
    setError("");
    try {
      if (action === "publish") {
        await publishReviewerReport(selectedId);
        setActionMsg("Report version published.");
      } else if (action === "rollback") {
        const reason = prompt("Enter rollback reason:");
        if (!reason) return;
        await rollbackReviewerReport(selectedId, { version_id: extraId, reason });
        setActionMsg("Report version rolled back.");
      } else if (action === "edit") {
        const rating = prompt("Enter new rating recommendation (A/B/C/D):");
        if (!rating) return;
        await editReviewerReport(selectedId, { rating_recommendation: rating, comment: "Manual rating edit." });
        setActionMsg("Rating updated.");
      } else if (action === "override") {
        const totalScore = prompt("Enter override total score:");
        if (!totalScore) return;
        const reason = prompt("Enter override reason:");
        if (!reason) return;
        await overrideReviewerReport(selectedId, { total_score: parseFloat(totalScore), reason });
        setActionMsg("Score overridden.");
      }
      await refreshCurrentPacket();
    } catch (err) {
      setError(err.message);
    }
  }

  const profile = packet?.profile;
  const cycle = packet?.cycle;
  const activities = packet?.activities ?? [];
  const evidence = packet?.evidence ?? [];
  const appraisal = packet?.appraisal;
  const report = packet?.report;
  const score = packet?.score;
  const breakdown = score?.score_breakdown?.line_items ?? [];

  const activityGroups = useMemo(() => {
    const g = { research: [], teaching: [], administrative: [] };
    for (const a of activities) g[a.category]?.push(a);
    return g;
  }, [activities]);

  return (
    <AppLayout
      title="Governance & Review Portal"
      subtitle={`Signed in as Reviewer (${user?.email})`}
      cycleInfo={cycle}
      navItems={reviewerNavItems}
    >
      <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-xs text-amber-900 flex items-center justify-between">
        <span>{DISCLAIMER}</span>
        <span className="font-semibold">Reviewer Governance Mode</span>
      </div>

      {error && <div className="p-3 rounded bg-red-50 border border-red-200 text-xs text-red-700 font-semibold">{error}</div>}
      {actionMsg && <div className="p-3 rounded bg-emerald-50 border border-emerald-200 text-xs text-emerald-700 font-semibold">{actionMsg}</div>}

      <div className="grid grid-cols-1 lg:grid-cols-[300px_minmax(0,1fr)] gap-6">
        <FacultyList faculty={faculty} selectedId={selectedId} onSelect={setSelectedId} />

        <div className="space-y-6 min-w-0">
          {!packet ? (
            <div className="bg-white rounded-lg border border-[#DCE5E1] p-8 text-center text-xs text-[#73817C]">
              Select a faculty member from the review queue to open their appraisal packet.
            </div>
          ) : (
            <>
              {/* Faculty & Cycle Info */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="bg-white rounded-lg border border-[#DCE5E1] p-5 shadow-xs space-y-2">
                  <span className="text-[11px] font-semibold uppercase tracking-wider text-[#73817C]">Faculty Profile</span>
                  <h2 className="text-xl font-bold text-[#192522]">{profile?.full_name || profile?.email}</h2>
                  <p className="text-xs text-[#53635E]">
                    Employee Code: <span className="font-semibold text-[#192522]">{profile?.employee_code || "—"}</span>
                  </p>
                  <p className="text-xs text-[#53635E]">
                    Department: <span className="font-semibold text-[#192522]">{profile?.department || "—"}</span> · Designation: <span className="font-semibold text-[#192522]">{profile?.designation || "—"}</span>
                  </p>
                  <p className="text-xs text-[#53635E]">
                    Institution: <span className="font-semibold text-[#192522]">{profile?.institution || "—"}</span>
                  </p>
                </div>

                <div className="bg-white rounded-lg border border-[#DCE5E1] p-5 shadow-xs space-y-2">
                  <span className="text-[11px] font-semibold uppercase tracking-wider text-[#73817C]">Cycle Context</span>
                  <h3 className="text-lg font-bold text-[#192522]">{cycle?.name || "Appraisal Cycle"}</h3>
                  <p className="text-xs text-[#53635E]">
                    Academic Year: <span className="font-semibold text-[#192522]">{cycle?.academic_year || "—"}</span>
                  </p>
                  <p className="text-xs text-[#53635E]">
                    Dates: <span className="font-semibold text-[#192522]">{cycle?.start_date || "—"} to {cycle?.end_date || "—"}</span>
                  </p>
                  <StatusBadge tone={cycle?.status === "open" ? "green" : "slate"}>
                    Cycle Status: {cycle?.status || "n/a"}
                  </StatusBadge>
                </div>
              </div>

              {/* Appraisal Review Gate */}
              <div className="bg-white rounded-lg border border-[#DCE5E1] p-5 shadow-xs space-y-3">
                <div className="flex items-center justify-between border-b border-[#DCE5E1] pb-3">
                  <h3 className="text-sm font-bold text-[#192522]">Governance Gate & Decision</h3>
                  <StatusBadge tone={appraisal?.approval_status === "approved" ? "green" : appraisal?.approval_status === "rejected" ? "red" : "amber"}>
                    Approval Status: {appraisal?.approval_status || "awaiting_review"}
                  </StatusBadge>
                </div>

                {appraisal?.approval_status === "awaiting_review" && (
                  <div className="flex flex-wrap gap-2 pt-1">
                    <button
                      onClick={() => handleDecision("approve")}
                      className="px-4 py-2 rounded bg-emerald-700 text-white text-xs font-semibold hover:bg-emerald-800"
                    >
                      Approve Appraisal
                    </button>
                    <button
                      onClick={() => handleDecision("request_changes")}
                      className="px-4 py-2 rounded bg-amber-600 text-white text-xs font-semibold hover:bg-amber-700"
                    >
                      Request Changes
                    </button>
                    <button
                      onClick={() => handleDecision("reject")}
                      className="px-4 py-2 rounded bg-red-600 text-white text-xs font-semibold hover:bg-red-700"
                    >
                      Reject Appraisal
                    </button>
                  </div>
                )}

                {appraisal?.approval_status === "approved" && (
                  <p className="text-xs text-emerald-800 font-semibold">
                    Approved by {appraisal.reviewer_email || "reviewer"} on {appraisal.approved_at || "now"}.
                  </p>
                )}

                {appraisal?.approval_status === "rejected" && (
                  <p className="text-xs text-red-700 font-semibold">
                    Rejected. Reason: {appraisal.rejection_reason || "—"}
                  </p>
                )}

                {appraisal?.approval_status === "changes_requested" && (
                  <p className="text-xs text-amber-800 font-semibold">
                    Changes Requested. Reason: {appraisal.change_request_reason || "—"}
                  </p>
                )}

                {report && (
                  <div className="flex flex-wrap gap-2 border-t border-[#DCE5E1] pt-3">
                    <button onClick={() => handleGovernance("edit")} className="px-3 py-1.5 rounded border border-[#DCE5E1] text-xs font-semibold text-[#53635E] hover:bg-[#F8FAF9]">
                      Edit Rating
                    </button>
                    <button onClick={() => handleGovernance("override")} className="px-3 py-1.5 rounded border border-red-200 text-xs font-semibold text-red-700 hover:bg-red-50">
                      Override Score
                    </button>
                    {appraisal?.approval_status === "approved" && report.status !== "published" && (
                      <button onClick={() => handleGovernance("publish")} className="px-4 py-1.5 rounded bg-[#194537] text-white text-xs font-semibold">
                        Publish Final Approved Version
                      </button>
                    )}
                  </div>
                )}
              </div>

              {/* Scoring Summary & Breakdown */}
              {score && (
                <div className="bg-white rounded-lg border border-[#DCE5E1] p-5 shadow-xs space-y-4">
                  <div className="flex items-center justify-between border-b border-[#DCE5E1] pb-3">
                    <h3 className="text-sm font-bold text-[#192522]">Calculated Appraisal Score</h3>
                    <span className="text-xs font-semibold text-[#194537]">Engine v{score.scoring_engine_version || "1.0"}</span>
                  </div>

                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    <div className="bg-[#194537]/5 border-2 border-[#194537]/20 p-3 rounded-lg">
                      <div className="flex items-center justify-between">
                        <p className="text-[10px] font-bold uppercase text-[#194537]">Total Score</p>
                        <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-[#194537] text-white">
                          Grade: {score.score_breakdown?.rating_recommendation || "—"}
                        </span>
                      </div>
                      <p className="text-2xl font-bold text-[#194537] mt-0.5">{score.total_score?.toFixed?.(2) ?? score.total_score ?? 0} <span className="text-xs font-normal text-[#53635E]">/ 100</span></p>
                      <p className="text-[10px] text-[#53635E] mt-1">Weighted Sum</p>
                    </div>
                    <div className="bg-[#F8FAF9] border border-[#DCE5E1] p-3 rounded-lg">
                      <div className="flex items-center justify-between">
                        <p className="text-[10px] font-bold uppercase text-[#73817C]">Research</p>
                        <span className="text-[9px] text-emerald-800 font-semibold bg-emerald-50 px-1 rounded border border-emerald-200">Weight: 40%</span>
                      </div>
                      <p className="text-xl font-bold text-[#192522] mt-0.5">{(score.score_breakdown?.research_score ?? 0).toFixed?.(2) ?? 0} <span className="text-xs font-normal text-[#73817C]">/ 40 max</span></p>
                      <p className="text-[10px] text-[#53635E] mt-1">Raw: {(score.score_breakdown?.category_raw_totals?.research ?? 25.0).toFixed(2)} pts × 40%</p>
                    </div>
                    <div className="bg-[#F8FAF9] border border-[#DCE5E1] p-3 rounded-lg">
                      <div className="flex items-center justify-between">
                        <p className="text-[10px] font-bold uppercase text-[#73817C]">Teaching</p>
                        <span className="text-[9px] text-sky-800 font-semibold bg-sky-50 px-1 rounded border border-sky-200">Weight: 40%</span>
                      </div>
                      <p className="text-xl font-bold text-[#192522] mt-0.5">{(score.score_breakdown?.teaching_score ?? 0).toFixed?.(2) ?? 0} <span className="text-xs font-normal text-[#73817C]">/ 40 max</span></p>
                      <p className="text-[10px] text-[#53635E] mt-1">Raw: {(score.score_breakdown?.category_raw_totals?.teaching ?? 15.2).toFixed(2)} pts × 40%</p>
                    </div>
                    <div className="bg-[#F8FAF9] border border-[#DCE5E1] p-3 rounded-lg">
                      <div className="flex items-center justify-between">
                        <p className="text-[10px] font-bold uppercase text-[#73817C]">Administrative</p>
                        <span className="text-[9px] text-purple-800 font-semibold bg-purple-50 px-1 rounded border border-purple-200">Weight: 20%</span>
                      </div>
                      <p className="text-xl font-bold text-[#192522] mt-0.5">{(score.score_breakdown?.administrative_score ?? 0).toFixed?.(2) ?? 0} <span className="text-xs font-normal text-[#73817C]">/ 20 max</span></p>
                      <p className="text-[10px] text-[#53635E] mt-1">Raw: {(score.score_breakdown?.category_raw_totals?.administrative ?? 10.0).toFixed(2)} pts × 20%</p>
                    </div>
                  </div>

                  {breakdown.length > 0 && (
                    <div className="border border-[#DCE5E1] rounded-lg overflow-hidden text-xs">
                      <div className="bg-[#F8FAF9] px-4 py-2.5 font-bold text-[#192522] border-b border-[#DCE5E1] flex items-center justify-between">
                        <span>Score Reconciliation Line Items</span>
                        <span className="text-[11px] font-normal text-[#53635E]">Line item raw points &rarr; Category weights &rarr; Weighted contributions</span>
                      </div>
                      <div className="divide-y divide-[#DCE5E1]">
                        {breakdown.map((it, i) => {
                          const cat = it.category || (it.rubric_code?.startsWith("scholar") ? "research" : it.rubric_code === "coordinator" ? "administrative" : "teaching");
                          const weight = it.category_weight ?? (cat === "administrative" ? 0.20 : 0.40);
                          const rawPts = it.points ?? 0;
                          const weightedPts = it.weighted_points ?? (rawPts * weight);

                          return (
                            <div key={i} className="px-4 py-2.5 flex items-center justify-between gap-3">
                              <div className="space-y-0.5">
                                <div className="flex items-center gap-2">
                                  <span className="px-1.5 py-0.5 rounded bg-slate-100 font-semibold text-[#192522]">{it.label || it.rubric_code || "—"}</span>
                                  <span className="text-[10px] uppercase font-semibold text-[#73817C]">[{cat}]</span>
                                  {it.activity_id && (
                                    <span className="text-[#73817C] text-[10px]">ID: {it.activity_id.slice(0, 8)}…</span>
                                  )}
                                </div>
                                <div className="text-[11px] text-[#53635E]">
                                  {it.value ? it.value : (it.evidence_ids?.length ? `Evidence: ${it.evidence_ids.join(", ")}` : "Verified via system / rubric")}
                                </div>
                              </div>
                              <div className="text-right shrink-0">
                                <div className="text-xs">
                                  <span className="font-semibold text-[#192522]">{rawPts.toFixed(2)} raw pts</span>
                                  <span className="text-[#73817C] text-[11px]"> × {(weight * 100).toFixed(0)}% = </span>
                                  <span className="font-bold text-[#194537]">+{weightedPts.toFixed(2)} weighted pts</span>
                                </div>
                                {it.status && (
                                  <span className="text-[10px] text-emerald-700 font-medium">{it.status.toUpperCase()}</span>
                                )}
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Activities & Evidence Review */}
              {["research", "teaching", "administrative"].map((cat) => (
                <div key={cat} className="bg-white rounded-lg border border-[#DCE5E1] p-5 shadow-xs space-y-3">
                  <div className="flex items-center justify-between border-b border-[#DCE5E1] pb-3">
                    <h3 className="text-sm font-bold text-[#192522] capitalize">{cat} Activities ({activityGroups[cat].length})</h3>
                  </div>

                  {activityGroups[cat].length === 0 ? (
                    <p className="text-xs text-[#73817C] italic">No {cat} activities recorded.</p>
                  ) : (
                    <div className="space-y-3">
                      {activityGroups[cat].map((a) => {
                        const actEvidence = evidence.filter((e) => e.activity_id === a.id);
                        return (
                          <div key={a.id} className="p-3 rounded bg-[#F8FAF9] border border-[#DCE5E1] space-y-2 text-xs">
                            <div className="flex flex-wrap items-center gap-2">
                              <span className="px-2 py-0.5 rounded bg-sky-50 text-sky-800 font-semibold">{a.category}</span>
                              <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-700 font-medium">{a.activity_type || "—"}</span>
                              {a.rubric_code && <span className="px-2 py-0.5 rounded bg-amber-50 text-amber-800">{a.rubric_code}</span>}
                              <span className="font-bold text-[#192522] ml-1">{a.title}</span>
                            </div>
                            {a.description && <p className="text-[#53635E]">{a.description}</p>}

                            {/* Attached evidence */}
                            {actEvidence.length > 0 ? (
                              <div className="pt-2 border-t border-[#DCE5E1] space-y-1">
                                <p className="text-[10px] font-semibold text-[#73817C]">Evidence Files ({actEvidence.length}):</p>
                                {actEvidence.map((e) => (
                                  <div key={e.id} className="p-2 rounded bg-white border border-[#DCE5E1] flex items-center justify-between">
                                    <div>
                                      <span className="font-semibold text-[#192522]">{e.original_filename || "evidence"}</span>
                                      <span className="text-[10px] text-[#73817C] ml-2">
                                        sha256: {e.checksum?.slice?.(0, 10) || "—"} · {e.file_size || 0} bytes
                                      </span>
                                    </div>
                                    <div className="flex gap-1.5 text-[10px]">
                                      <span className="px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-800 font-semibold">{e.validation_status}</span>
                                      <span className="px-1.5 py-0.5 rounded bg-sky-100 text-sky-800">{e.extraction_status}</span>
                                    </div>
                                  </div>
                                ))}
                              </div>
                            ) : (
                              <p className="text-[10px] text-[#73817C] italic">No evidence attached.</p>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              ))}

              {/* Appraisal Report Document View */}
              {report && (
                <div className="bg-white rounded-lg border border-[#DCE5E1] p-5 shadow-xs space-y-3">
                  <div className="flex items-center justify-between border-b border-[#DCE5E1] pb-3">
                    <h3 className="text-sm font-bold text-[#192522]">Generated Report Document (Version #{report.version_number})</h3>
                    <StatusBadge tone="green">Rating: {report.rating_recommendation || "—"}</StatusBadge>
                  </div>
                  <div className="border border-[#DCE5E1] rounded overflow-hidden">
                    <iframe title="reviewer-report-view" className="w-full h-96" srcDoc={report.html || "<p>Loading...</p>"} />
                  </div>
                </div>
              )}

              {/* Report Version History */}
              {packet.report_history?.length > 0 && (
                <div className="bg-white rounded-lg border border-[#DCE5E1] p-5 shadow-xs space-y-3">
                  <h3 className="text-sm font-bold text-[#192522] border-b border-[#DCE5E1] pb-2">Version History & Governance Rollback</h3>
                  <div className="divide-y divide-[#DCE5E1] text-xs">
                    {packet.report_history.map((ver) => (
                      <div key={ver.id} className="py-2 flex items-center justify-between gap-2">
                        <span>Version #{ver.version_number} · Status: {ver.status} · Rating: {ver.rating_recommendation || "—"}</span>
                        {!ver.is_current && ver.status !== "published" && report?.status !== "published" && (
                          <button
                            onClick={() => handleGovernance("rollback", ver.id)}
                            className="px-2.5 py-1 rounded border border-[#DCE5E1] bg-[#F8FAF9] text-[#53635E] hover:bg-white"
                          >
                            Rollback to Version #{ver.version_number}
                          </button>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </AppLayout>
  );
}
