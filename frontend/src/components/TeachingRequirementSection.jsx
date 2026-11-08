import { useEffect, useState } from "react";
import { fetchTeachingRequirement } from "../api/client.js";

export function TeachingRequirementSection({ req, refresh }) {
  const [data, setData] = useState(req || null);
  const [loading, setLoading] = useState(!req);
  const [error, setError] = useState("");

  const load = async () => {
    try {
      setLoading(true);
      setError("");
      const res = await fetchTeachingRequirement();
      setData(res);
    } catch (err) {
      setError(err.message || "Failed to load teaching requirements");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (req) {
      setData(req);
    } else {
      load();
    }
  }, [req, refresh]);

  if (loading) return <section className="ui-card animate-pulse p-5" aria-busy="true"><div className="h-4 w-36 rounded bg-subtle" /><div className="mt-5 grid grid-cols-3 gap-3"><div className="h-20 rounded-md bg-subtle" /><div className="h-20 rounded-md bg-subtle" /><div className="h-20 rounded-md bg-subtle" /></div></section>;
  if (error) return <section role="alert" className="ui-card border-danger/30 p-5 text-sm text-danger">{error}</section>;
  if (!data) return null;

  return (
    <section className="ui-card h-full p-5 sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="ui-eyebrow">Teaching requirement</p>
          <h3 className="mt-1 text-lg font-semibold text-ink">{data.role}</h3>
        </div>
        <span
          className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold ${
            data.completed
              ? "bg-success/10 text-success"
              : "bg-pending/10 text-pending"
          }`}
        >
          {data.completed ? "Requirement met" : "In progress"}
        </span>
      </div>

      <div className="mt-5 grid grid-cols-1 gap-3 sm:grid-cols-3">
        <div className="ui-card-subtle p-3">
          <span className="block text-xs text-text-secondary">Required hours</span>
          <span className="font-display mt-1 block text-2xl font-semibold text-ink">{data.required_hours} hrs</span>
        </div>
        <div className="ui-card-subtle p-3">
          <span className="block text-xs text-text-secondary">Actual attended hours</span>
          <span className="font-display mt-1 block text-2xl font-semibold text-success">{data.actual_hours} hrs</span>
        </div>
        <div className="ui-card-subtle p-3">
          <span className="block text-xs text-text-secondary">Remaining hours</span>
          <span className="font-display mt-1 block text-2xl font-semibold text-pending">{data.remaining_hours} hrs</span>
        </div>
      </div>

      <div className="mt-3 rounded-md border border-[#DCE5E1] bg-[#F8FAF9] p-3 text-xs text-[#53635E]">
        <span className="font-semibold text-[#192522]">Workload Compliance vs. Appraisal Scoring:</span>
        <p className="mt-0.5">
          This tracker monitors departmental workload compliance ({data.actual_hours} attended, {data.remaining_hours} remaining out of {data.required_hours} hrs required).
          Under official appraisal policy, remaining required hours are <strong>not deducted</strong> from your appraisal score. Appraisal scoring credits points for validated completed teaching activities (0.50 pts/hr up to rubric cap).
        </p>
      </div>
    </section>
  );
}
