import React, { useState } from "react";
import { approveSDLCTask, createSDLCTask, executeSDLCTask, regenerateSDLCTask } from "../api/client";

export function SDLCFactorySection() {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [targetFiles, setTargetFiles] = useState("");
  const [taskType, setTaskType] = useState("verification");
  const [currentTask, setCurrentTask] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleCreateTask = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const filesList = targetFiles
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);

      const res = await createSDLCTask({
        title,
        description,
        target_files: filesList,
        task_type: taskType,
      });
      setCurrentTask(res);
      setTitle("");
      setDescription("");
      setTargetFiles("");
    } catch (err) {
      setError(err.message || "Failed to create SDLC task");
    } finally {
      setLoading(false);
    }
  };

  const handleApproval = async (action) => {
    if (!currentTask) return;
    setLoading(true);
    setError(null);
    try {
      const planHash = currentTask.plan?.plan_hash;
      const res = await approveSDLCTask(currentTask.task_id, {
        plan_hash: planHash,
        action,
        rejection_reason: action === "reject" ? "Rejected by reviewer" : undefined,
      });
      setCurrentTask(res);
    } catch (err) {
      setError(err.message || "Failed to process approval");
    } finally {
      setLoading(false);
    }
  };

  const handleRegenerate = async (targetType) => {
    if (!currentTask) return;
    setLoading(true);
    setError(null);
    try {
      const res = await regenerateSDLCTask(currentTask.task_id, {
        task_type: targetType || currentTask.task_type || "verification",
      });
      setCurrentTask(res);
    } catch (err) {
      setError(err.message || "Failed to regenerate plan");
    } finally {
      setLoading(false);
    }
  };

  const handleExecute = async () => {
    if (!currentTask) return;
    setLoading(true);
    setError(null);
    try {
      const res = await executeSDLCTask(currentTask.task_id, {
        verification_command_key: "pytest_quick",
      });
      setCurrentTask(res);
    } catch (err) {
      setError(err.message || "Failed to execute task");
    } finally {
      setLoading(false);
    }
  };

  const getStatusBadge = (status) => {
    switch (status) {
      case "approved":
        return <span className="px-2.5 py-1 text-xs font-semibold rounded-full bg-emerald-100 text-emerald-800 border border-emerald-300">Approved</span>;
      case "completed":
        return <span className="px-2.5 py-1 text-xs font-semibold rounded-full bg-sky-100 text-sky-800 border border-sky-300">Completed</span>;
      case "executing":
        return <span className="px-2.5 py-1 text-xs font-semibold rounded-full bg-indigo-100 text-indigo-800 border border-indigo-300">Executing</span>;
      case "rejected":
        return <span className="px-2.5 py-1 text-xs font-semibold rounded-full bg-rose-100 text-rose-800 border border-rose-300">Rejected</span>;
      case "failed":
        return <span className="px-2.5 py-1 text-xs font-semibold rounded-full bg-rose-100 text-rose-800 border border-rose-300">Failed</span>;
      default:
        return <span className="px-2.5 py-1 text-xs font-semibold rounded-full bg-amber-100 text-amber-800 border border-amber-300">Awaiting Approval</span>;
    }
  };

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 mb-8">
      <div className="flex items-center justify-between pb-4 border-b border-slate-100 mb-6">
        <div>
          <h2 className="text-xl font-bold text-slate-800">Agentic SDLC Factory</h2>
          <p className="text-sm text-slate-500">Submit software development tasks, inspect generated plans, enforce human approval, and execute allowlisted verifications.</p>
        </div>
      </div>

      {error && (
        <div className="mb-4 p-4 rounded-lg bg-rose-50 border border-rose-200 text-rose-700 text-sm">
          <strong>Error:</strong> {error}
        </div>
      )}

      {/* Task Creation Form */}
      <form onSubmit={handleCreateTask} className="space-y-4 mb-8 bg-slate-50 p-4 rounded-lg border border-slate-200 text-xs">
        <h3 className="text-sm font-semibold text-slate-700">Submit New SDLC Task</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div>
            <label className="block text-slate-600 mb-1 font-medium">Task Title</label>
            <input
              type="text"
              required
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Verify Backend and Frontend Build"
              className="w-full px-3 py-2 bg-white border border-slate-300 rounded text-slate-800"
            />
          </div>
          <div>
            <label className="block text-slate-600 mb-1 font-medium">Task Type</label>
            <select
              value={taskType}
              onChange={(e) => setTaskType(e.target.value)}
              className="w-full px-3 py-2 bg-white border border-slate-300 rounded text-slate-800 font-medium"
            >
              <option value="verification">Verification Only (Inspection/Tests only)</option>
              <option value="development">Development (Implementation Planning)</option>
            </select>
          </div>
          <div>
            <label className="block text-slate-600 mb-1 font-medium">Target Files (comma-separated)</label>
            <input
              type="text"
              value={targetFiles}
              onChange={(e) => setTargetFiles(e.target.value)}
              placeholder="e.g. backend/app/main.py, backend/tests/test_api.py"
              className="w-full px-3 py-2 bg-white border border-slate-300 rounded text-slate-800"
            />
          </div>
        </div>
        <div>
          <label className="block text-slate-600 mb-1 font-medium">Description & Requirements</label>
          <textarea
            required
            rows={2}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Detailed description of the task and verification requirements..."
            className="w-full px-3 py-2 bg-white border border-slate-300 rounded text-slate-800"
          />
        </div>
        <button
          type="submit"
          disabled={loading}
          className="px-4 py-2 bg-emerald-700 hover:bg-emerald-800 text-white font-medium rounded transition-colors text-xs"
        >
          {loading ? "Generating Plan..." : "Submit Task & Generate Plan"}
        </button>
      </form>

      {/* Active Task Details & Plan View */}
      {currentTask && (
        <div className="border border-slate-200 rounded-lg p-5 bg-white space-y-4">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-mono text-slate-400">Task ID: {currentTask.task_id}</span>
                <span className="text-[11px] font-semibold px-2 py-0.5 rounded uppercase tracking-wider bg-slate-100 text-slate-700">
                  {currentTask.task_type || "verification"}
                </span>
              </div>
              <h3 className="text-lg font-bold text-slate-800 mt-1">{currentTask.title}</h3>
            </div>
            {getStatusBadge(currentTask.status)}
          </div>

          <p className="text-xs text-slate-600">{currentTask.description}</p>
          {currentTask.rejection_reason && (
            <p className="text-xs font-semibold text-rose-600">Rejection Reason: {currentTask.rejection_reason}</p>
          )}

          {/* Plan Breakdown */}
          {currentTask.plan && (
            <div className="space-y-3">
              <div className="flex items-center justify-between text-xs font-semibold text-slate-700 bg-slate-50 p-2.5 rounded border border-slate-200">
                <span>Plan Hash: <code className="text-slate-900 bg-slate-200 px-1.5 py-0.5 rounded">{currentTask.plan.plan_hash?.slice(0, 16)}...</code></span>
                <span>Risk: <span className="text-amber-600 capitalize">{currentTask.plan.risk_assessment}</span></span>
              </div>

              <h4 className="text-xs font-bold text-slate-700 uppercase tracking-wider">Ordered Execution Steps</h4>
              <div className="space-y-2">
                {currentTask.plan.steps.map((step, idx) => (
                  <div key={step.step_id} className="p-3 rounded border border-slate-200 bg-slate-50 text-xs flex justify-between items-start">
                    <div>
                      <span className="font-semibold text-slate-800">{idx + 1}. {step.title}</span>
                      <p className="text-slate-500 text-[11px] mt-0.5">{step.description}</p>
                    </div>
                    <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-slate-200 text-slate-700">{step.status}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Governance Action Controls */}
          <div className="flex items-center gap-3 pt-3 border-t border-slate-100">
            {currentTask.status === "awaiting_approval" && (
              <>
                <button
                  onClick={() => handleApproval("approve")}
                  disabled={loading}
                  className="px-4 py-2 bg-emerald-700 hover:bg-emerald-800 text-white font-medium rounded transition-colors text-xs"
                >
                  Approve Plan (Bind Hash)
                </button>
                <button
                  onClick={() => handleApproval("reject")}
                  disabled={loading}
                  className="px-4 py-2 bg-rose-700 hover:bg-rose-800 text-white font-medium rounded transition-colors text-xs"
                >
                  Reject Plan
                </button>
                <button
                  onClick={() => handleRegenerate("verification")}
                  disabled={loading}
                  className="px-4 py-2 bg-slate-200 hover:bg-slate-300 text-slate-700 font-medium rounded transition-colors text-xs"
                >
                  Regenerate as Verification-Only
                </button>
              </>
            )}

            {currentTask.status === "rejected" && (
              <button
                onClick={() => handleRegenerate()}
                disabled={loading}
                className="px-4 py-2 bg-amber-600 hover:bg-amber-700 text-white font-medium rounded transition-colors text-xs"
              >
                Regenerate Plan (Reset to Awaiting Approval)
              </button>
            )}

            {currentTask.status === "approved" && (
              <button
                onClick={handleExecute}
                disabled={loading}
                className="px-4 py-2 bg-sky-700 hover:bg-sky-800 text-white font-medium rounded transition-colors text-xs"
              >
                Execute Approved Steps & Run Verification
              </button>
            )}
          </div>

          {/* Execution & Verification Results */}
          {currentTask.execution_results && currentTask.execution_results.length > 0 && (
            <div className="mt-4 pt-4 border-t border-slate-100">
              <h4 className="text-xs font-bold text-slate-700 mb-2">Verification Output Stream</h4>
              {currentTask.execution_results.map((res, idx) => (
                <div key={idx} className="p-3 rounded bg-slate-900 text-slate-100 font-mono text-xs overflow-x-auto">
                  <div className="text-sky-400 mb-1">Exit Code: {res.exit_code} | Duration: {res.duration_ms}ms</div>
                  {res.stdout && <pre className="text-slate-300 text-[11px] whitespace-pre-wrap">{res.stdout}</pre>}
                  {res.stderr && <pre className="text-rose-400 text-[11px] whitespace-pre-wrap">{res.stderr}</pre>}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
