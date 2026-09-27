import { useEffect, useState } from "react";
import { fetchResearchPaperStatus } from "../api/client.js";

export function ResearchPaperRequirementSection({ refresh }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = async () => {
    try {
      setLoading(true);
      setError("");
      const res = await fetchResearchPaperStatus();
      setData(res);
    } catch (err) {
      setError(err.message || "Failed to load research paper status");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [refresh]);

  if (loading) return <div className="p-4 text-xs text-slate-500">Loading research paper status...</div>;
  if (error) return <div className="p-4 text-xs text-red-600">Error: {error}</div>;
  if (!data) return null;

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-center justify-between">
        <div>
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Research Validation</span>
          <h3 className="text-lg font-bold text-slate-900 mt-0.5">Research Papers Requirement</h3>
        </div>
        <span
          className={`px-3 py-1 text-xs font-bold rounded-full ${
            data.is_satisfied
              ? "bg-emerald-100 text-emerald-800 border border-emerald-300"
              : "bg-rose-100 text-rose-800 border border-rose-300"
          }`}
        >
          {data.is_satisfied ? "Requirement Satisfied ✓" : "Minimum Requirement Pending ✗"}
        </span>
      </div>

      <div className="mt-4 flex items-center justify-between rounded-md bg-slate-50 p-4 border border-slate-100">
        <div>
          <span className="text-xs text-slate-500 font-medium">Submitted Research Papers</span>
          <div className="text-2xl font-extrabold text-slate-900 mt-0.5">
            {data.submitted_count} / {data.required_count} Required
          </div>
        </div>
        <div className="text-right">
          <span className="text-xs text-slate-500">Status</span>
          <div className="text-sm font-semibold text-slate-800 mt-1">
            {data.is_satisfied ? "Minimum 2 Papers Uploaded ✓" : `Needs ${data.required_count - data.submitted_count} more paper(s)`}
          </div>
        </div>
      </div>
    </div>
  );
}
