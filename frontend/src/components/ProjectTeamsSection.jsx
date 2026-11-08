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
    <section className="ui-card h-full space-y-4 p-5 sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="ui-eyebrow">Student supervision</p>
          <h3 className="mt-1 text-lg font-semibold text-ink">Supervised student project teams</h3>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className="ui-status-neutral">
            Total Teams: {teams.length}
          </span>
          <button
            onClick={openAdd}
            className="ui-button-primary"
          >
            + Add Project Team
          </button>
        </div>
      </div>

      {error && <div role="alert" className="rounded-md border border-danger/20 bg-danger/5 p-3 text-sm text-danger">{error}</div>}

      {loading ? (
        <div className="py-4 text-sm text-muted" aria-live="polite">Loading project teams…</div>
      ) : teams.length === 0 ? (
        <div className="rounded-md border border-dashed border-divider p-6 text-center text-sm text-text-secondary">
          No project teams supervised yet. Click "+ Add Project Team" to record student teams under your guidance.
        </div>
      ) : (
        <div className="grid gap-3 md:grid-cols-2">
          {teams.map((team) => (
            <article key={team.id} className="ui-card-subtle space-y-3 p-4">
              <div className="flex items-start justify-between">
                <div>
                  <h4 className="text-sm font-semibold text-ink">{team.title}</h4>
                  <span
                    className={`mt-1 inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${
                      team.status === "active"
                        ? "bg-success/10 text-success"
                        : "bg-neutral/10 text-neutral"
                    }`}
                  >
                    {team.status.toUpperCase()}
                  </span>
                </div>
                <div className="flex gap-1">
                  <button
                    onClick={() => openEdit(team)}
                    className="ui-button-quiet min-h-8 px-2 py-1 text-xs"
                  >
                    Edit
                  </button>
                  <button
                    onClick={() => handleDelete(team.id)}
                    className="ui-button-quiet min-h-8 px-2 py-1 text-xs text-danger hover:bg-danger/5 hover:text-danger"
                  >
                    Delete
                  </button>
                </div>
              </div>

              <div>
                  <span className="ui-eyebrow mb-1 block">
                  Team Members ({team.members ? team.members.length : 0})
                </span>
                {team.members && team.members.length > 0 ? (
                  <ul className="space-y-1 text-sm text-text-secondary">
                    {team.members.map((m, idx) => (
                      <li key={m.id || idx} className="flex items-center justify-between">
                        <span className="font-medium text-ink">{m.name}</span>
                        {m.email && <span className="text-xs text-muted">{m.email}</span>}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <span className="text-sm italic text-muted">No members listed</span>
                )}
              </div>
            </article>
          ))}
        </div>
      )}

      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/35 p-4 backdrop-blur-[2px]">
          <div className="ui-card max-h-[90vh] w-full max-w-lg overflow-y-auto p-6 shadow-xl">
            <h3 className="font-display mb-4 text-xl font-semibold text-ink">
              {editingTeam ? "Edit Project Team" : "Add Project Team"}
            </h3>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                  <label className="block text-sm font-medium text-text-secondary">Project / team title</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. AI-Based Crop Monitoring System"
                  className="ui-input mt-1"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                />
              </div>

              <div>
                  <label className="block text-sm font-medium text-text-secondary">Status</label>
                <select
                  className="ui-input mt-1"
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
                  <label className="text-sm font-medium text-text-secondary">Student members</label>
                  <button
                    type="button"
                    onClick={addMemberRow}
                    className="ui-button-quiet min-h-8 px-2 py-1 text-xs"
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
                        className="ui-input min-w-0 flex-1"
                        value={m.name}
                        onChange={(e) => handleMemberChange(idx, "name", e.target.value)}
                      />
                      <input
                        type="email"
                        placeholder="Student Email (Optional)"
                        className="ui-input min-w-0 flex-1"
                        value={m.email}
                        onChange={(e) => handleMemberChange(idx, "email", e.target.value)}
                      />
                      {members.length > 1 && (
                        <button
                          type="button"
                          onClick={() => removeMemberRow(idx)}
                          aria-label={`Remove student ${idx + 1}`}
                          className="ui-button-quiet min-h-8 px-2 py-1 text-xs text-danger hover:bg-danger/5 hover:text-danger"
                        >
                          ✕
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              </div>

              <div className="flex justify-end gap-2 border-t border-border pt-4">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="ui-button-secondary"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="ui-button-primary"
                >
                  Save Team
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </section>
  );
}
