import { useEffect, useState } from "react";
import {
  createProjectTeam,
  deleteProjectTeam,
  fetchProjectTeams,
  updateProjectTeam,
} from "../api/client.js";

export function ProjectTeamsSection() {
  const [teams, setTeams] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showModal, setShowModal] = useState(false);
  const [editingTeam, setEditingTeam] = useState(null);

  const [title, setTitle] = useState("");
  const [status, setStatus] = useState("active");
  const [members, setMembers] = useState([{ name: "", email: "" }]);

  const load = async () => {
    try {
      setLoading(true);
      setError("");
      const res = await fetchProjectTeams();
      setTeams(res);
    } catch (err) {
      setError(err.message || "Failed to load project teams");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const openAdd = () => {
    setEditingTeam(null);
    setTitle("");
    setStatus("active");
    setMembers([{ name: "", email: "" }]);
    setShowModal(true);
  };

  const openEdit = (team) => {
    setEditingTeam(team);
    setTitle(team.title || "");
    setStatus(team.status || "active");
    setMembers(
      team.members && team.members.length > 0
        ? team.members.map((m) => ({ name: m.name, email: m.email || "" }))
        : [{ name: "", email: "" }]
    );
    setShowModal(true);
  };

  const handleMemberChange = (index, field, value) => {
    const updated = [...members];
    updated[index][field] = value;
    setMembers(updated);
  };

  const addMemberRow = () => {
    setMembers([...members, { name: "", email: "" }]);
  };

  const removeMemberRow = (index) => {
    if (members.length === 1) return;
    setMembers(members.filter((_, i) => i !== index));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!title.trim()) return;
    const validMembers = members.filter((m) => m.name.trim() !== "");
    const payload = {
      title: title.trim(),
      status,
      members: validMembers,
    };
    try {
      setError("");
      if (editingTeam) {
        await updateProjectTeam(editingTeam.id, payload);
      } else {
        await createProjectTeam(payload);
      }
      setShowModal(false);
      await load();
    } catch (err) {
      setError(err.message || "Failed to save project team");
    }
  };

  const handleDelete = async (teamId) => {
    if (!window.confirm("Are you sure you want to delete this project team?")) return;
    try {
      setError("");
      await deleteProjectTeam(teamId);
      await load();
    } catch (err) {
      setError(err.message || "Failed to delete project team");
    }
  };

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Student Supervision</span>
          <h3 className="text-xl font-bold text-slate-900">Supervised Student Project Teams</h3>
        </div>
        <div className="flex items-center space-x-3">
          <span className="rounded-md bg-sky-50 px-3 py-1 text-sky-800 font-bold text-xs border border-sky-200">
            Total Teams: {teams.length}
          </span>
          <button
            onClick={openAdd}
            className="rounded-md bg-slate-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-slate-800 transition"
          >
            + Add Project Team
          </button>
        </div>
      </div>

      {error && <div className="rounded bg-red-50 p-3 text-xs text-red-700">{error}</div>}

      {loading ? (
        <div className="text-xs text-slate-500 py-4">Loading project teams...</div>
      ) : teams.length === 0 ? (
        <div className="rounded border border-dashed border-slate-200 p-6 text-center text-sm text-slate-500">
          No project teams supervised yet. Click "+ Add Project Team" to record student teams under your guidance.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {teams.map((team) => (
            <div key={team.id} className="rounded-lg border border-slate-200 bg-slate-50/50 p-4 space-y-3">
              <div className="flex items-start justify-between">
                <div>
                  <h4 className="font-bold text-slate-900 text-sm">{team.title}</h4>
                  <span
                    className={`inline-block mt-1 px-2 py-0.5 rounded text-[10px] font-semibold ${
                      team.status === "active"
                        ? "bg-emerald-100 text-emerald-800"
                        : "bg-slate-200 text-slate-700"
                    }`}
                  >
                    {team.status.toUpperCase()}
                  </span>
                </div>
                <div className="flex space-x-2">
                  <button
                    onClick={() => openEdit(team)}
                    className="text-xs font-medium text-sky-600 hover:text-sky-800"
                  >
                    Edit
                  </button>
                  <button
                    onClick={() => handleDelete(team.id)}
                    className="text-xs font-medium text-rose-600 hover:text-rose-800"
                  >
                    Delete
                  </button>
                </div>
              </div>

              <div>
                <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider block mb-1">
                  Team Members ({team.members ? team.members.length : 0})
                </span>
                {team.members && team.members.length > 0 ? (
                  <ul className="space-y-1 text-xs text-slate-700">
                    {team.members.map((m, idx) => (
                      <li key={m.id || idx} className="flex items-center justify-between">
                        <span className="font-medium">{m.name}</span>
                        {m.email && <span className="text-slate-500 text-[11px]">{m.email}</span>}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <span className="text-xs text-slate-400 italic">No members listed</span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4">
          <div className="w-full max-w-lg rounded-lg bg-white p-6 shadow-xl border border-slate-200 max-h-[90vh] overflow-y-auto">
            <h3 className="text-lg font-bold text-slate-900 mb-4">
              {editingTeam ? "Edit Project Team" : "Add Project Team"}
            </h3>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-700">Project / Team Title</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. AI-Based Crop Monitoring System"
                  className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-slate-800"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-700">Status</label>
                <select
                  className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-slate-800"
                  value={status}
                  onChange={(e) => setStatus(e.target.value)}
                >
                  <option value="active">Active</option>
                  <option value="completed">Completed</option>
                  <option value="paused">Paused</option>
                </select>
              </div>

              <div>
                <div className="flex items-center justify-between mb-2">
                  <label className="text-xs font-medium text-slate-700">Student Members</label>
                  <button
                    type="button"
                    onClick={addMemberRow}
                    className="text-xs font-semibold text-sky-600 hover:text-sky-800"
                  >
                    + Add Student
                  </button>
                </div>

                <div className="space-y-2">
                  {members.map((m, idx) => (
                    <div key={idx} className="flex gap-2 items-center">
                      <input
                        type="text"
                        placeholder="Student Name"
                        required
                        className="flex-1 rounded border border-slate-300 px-3 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-slate-800"
                        value={m.name}
                        onChange={(e) => handleMemberChange(idx, "name", e.target.value)}
                      />
                      <input
                        type="email"
                        placeholder="Student Email (Optional)"
                        className="flex-1 rounded border border-slate-300 px-3 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-slate-800"
                        value={m.email}
                        onChange={(e) => handleMemberChange(idx, "email", e.target.value)}
                      />
                      {members.length > 1 && (
                        <button
                          type="button"
                          onClick={() => removeMemberRow(idx)}
                          className="text-rose-600 text-xs font-bold px-1"
                        >
                          ✕
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              </div>

              <div className="flex justify-end space-x-2 pt-4 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="rounded px-4 py-2 text-xs font-medium text-slate-600 hover:bg-slate-100"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="rounded bg-slate-900 px-4 py-2 text-xs font-medium text-white hover:bg-slate-800"
                >
                  Save Team
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
