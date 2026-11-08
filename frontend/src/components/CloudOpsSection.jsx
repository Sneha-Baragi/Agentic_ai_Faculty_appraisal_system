import React, { useEffect, useState } from "react";
import { fetchCloudOpsDiagnostics } from "../api/client";

export function CloudOpsSection() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const loadDiagnostics = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchCloudOpsDiagnostics();
      setData(res);
    } catch (err) {
      setError(err.message || "Failed to load cloud operations diagnostics");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDiagnostics();
  }, []);

  const getStatusBadge = (status) => {
    switch (status) {
      case "healthy":
        return <span className="px-2.5 py-1 text-xs font-semibold rounded-full bg-emerald-100 text-emerald-800 border border-emerald-300">Healthy</span>;
      case "degraded":
        return <span className="px-2.5 py-1 text-xs font-semibold rounded-full bg-amber-100 text-amber-800 border border-amber-300">Degraded</span>;
      case "unhealthy":
        return <span className="px-2.5 py-1 text-xs font-semibold rounded-full bg-rose-100 text-rose-800 border border-rose-300">Unhealthy</span>;
      default:
        return <span className="px-2.5 py-1 text-xs font-semibold rounded-full bg-slate-100 text-slate-700 border border-slate-300">Unknown</span>;
    }
  };

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 mb-8">
      <div className="flex items-center justify-between pb-4 border-b border-slate-100">
        <div>
          <h2 className="text-xl font-bold text-slate-800">Cloud Operations & System Diagnostics</h2>
          <p className="text-sm text-slate-500">Read-only diagnostic monitoring for backend services, database, object storage, and containers</p>
        </div>
        <button
          onClick={loadDiagnostics}
          disabled={loading}
          className="px-3.5 py-2 text-sm font-medium text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-lg transition-colors flex items-center gap-2"
        >
          {loading ? "Refreshing..." : "Refresh Diagnostics"}
        </button>
      </div>

      {loading && !data && (
        <div className="py-8 text-center text-slate-500">
          Running diagnostic health checks across services...
        </div>
      )}

      {error && (
        <div className="my-4 p-4 rounded-lg bg-rose-50 border border-rose-200 text-rose-700 text-sm">
          <strong>Diagnostic Error:</strong> {error}
        </div>
      )}

      {data && (
        <div className="mt-6 space-y-6">
          {/* Overall Health Summary */}
          <div className="flex items-center justify-between p-4 rounded-lg bg-slate-50 border border-slate-200">
            <div className="flex items-center gap-3">
              <span className="text-sm font-medium text-slate-600">Overall System Health:</span>
              {getStatusBadge(data.overall_status)}
            </div>
            <div className="text-xs text-slate-400">
              Last checked: {data.timestamp ? new Date(data.timestamp).toLocaleString() : "N/A"}
            </div>
          </div>

          {/* Service Cards Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {data.services && data.services.map((svc, idx) => (
              <div key={idx} className="p-4 rounded-lg border border-slate-200 bg-white hover:border-slate-300 transition-all">
                <div className="flex items-center justify-between mb-2">
                  <span className="font-semibold text-slate-800 capitalize">{svc.service.replace("_", " ")}</span>
                  {getStatusBadge(svc.status)}
                </div>
                {svc.observed_issue && (
                  <p className="text-xs text-rose-600 font-medium mb-2">{svc.observed_issue}</p>
                )}
                <div className="text-xs text-slate-500 space-y-1 bg-slate-50 p-2.5 rounded border border-slate-100">
                  {svc.diagnostic_evidence && Object.entries(svc.diagnostic_evidence).map(([k, v]) => (
                    <div key={k} className="flex justify-between">
                      <span className="font-medium text-slate-600">{k}:</span>
                      <span className="text-slate-800 font-mono">{typeof v === "object" ? JSON.stringify(v) : String(v)}</span>
                    </div>
                  ))}
                </div>
                <div className="mt-2 text-xs text-slate-400 italic">
                  Action: {svc.recommended_action || "None"}
                </div>
              </div>
            ))}
          </div>

          {/* Operational Errors Stream */}
          {data.operational_errors && data.operational_errors.length > 0 && (
            <div className="mt-6">
              <h3 className="text-md font-semibold text-slate-700 mb-3">Recent Operational Events & Errors</h3>
              <div className="max-h-48 overflow-y-auto space-y-2 border border-slate-200 rounded-lg p-3 bg-slate-900 text-slate-100 font-mono text-xs">
                {data.operational_errors.map((err) => (
                  <div key={err.id} className="border-b border-slate-800 pb-2">
                    <span className="text-amber-400">[{err.timestamp ? new Date(err.timestamp).toLocaleTimeString() : "N/A"}]</span>{" "}
                    <span className="text-sky-400">{err.action}</span> - {err.entity_type} ({err.entity_id})
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
