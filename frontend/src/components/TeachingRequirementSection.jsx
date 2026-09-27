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

  if (loading) return <div className="p-4 text-sm text-slate-500">Loading teaching requirements...</div>;
  if (error) return <div className="p-4 text-sm text-red-600">Error: {error}</div>;
  if (!data) return null;

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-center justify-between">
        <div>
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Teaching Requirements</span>
          <h3 className="text-lg font-bold text-slate-900 mt-1">Role: {data.role}</h3>
        </div>
        <span
          className={`px-3 py-1 text-xs font-medium rounded-full ${
            data.completed
              ? "bg-emerald-100 text-emerald-800 border border-emerald-300"
              : "bg-amber-100 text-amber-800 border border-amber-300"
          }`}
        >
          {data.completed ? "Requirement Met ✓" : "In Progress"}
        </span>
      </div>

      <div className="mt-4 grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="rounded-md bg-slate-50 p-3 border border-slate-100">
          <span className="block text-xs text-slate-500">Required Hours</span>
          <span className="block text-xl font-bold text-slate-800 mt-0.5">{data.required_hours} hrs</span>
        </div>
        <div className="rounded-md bg-slate-50 p-3 border border-slate-100">
          <span className="block text-xs text-slate-500">Actual Attended Hours</span>
          <span className="block text-xl font-bold text-emerald-700 mt-0.5">{data.actual_hours} hrs</span>
        </div>
        <div className="rounded-md bg-slate-50 p-3 border border-slate-100">
          <span className="block text-xs text-slate-500">Remaining Hours</span>
          <span className="block text-xl font-bold text-amber-700 mt-0.5">{data.remaining_hours} hrs</span>
        </div>
      </div>
    </div>
  );
}
