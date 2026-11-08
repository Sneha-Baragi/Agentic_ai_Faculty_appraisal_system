import { useEffect, useState } from "react";
import {
  createTimetableEntry,
  deleteTimetableEntry,
  fetchTimetable,
  updateTimetableEntry,
} from "../api/client.js";

export function TimetableSection({ onTimetableChange }) {
  const [entries, setEntries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showModal, setShowModal] = useState(false);
  const [editingEntry, setEditingEntry] = useState(null);

  const [form, setForm] = useState({
    course_code: "",
    section: "",
    day_of_week: "Monday",
    start_time: "09:00",
    end_time: "10:00",
    room: "",
  });

  const load = async () => {
    try {
      setLoading(true);
      setError("");
      const list = await fetchTimetable();
      setEntries(list);
    } catch (err) {
      setError(err.message || "Failed to load timetable");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const openAdd = () => {
    setEditingEntry(null);
    setForm({
      course_code: "",
      section: "",
      day_of_week: "Monday",
      start_time: "09:00",
      end_time: "10:00",
      room: "",
    });
    setShowModal(true);
  };

  const openEdit = (entry) => {
    setEditingEntry(entry);
    setForm({
      course_code: entry.course_code || "",
      section: entry.section || "",
      day_of_week: entry.day_of_week || "Monday",
      start_time: entry.start_time ? entry.start_time.substring(0, 5) : "09:00",
      end_time: entry.end_time ? entry.end_time.substring(0, 5) : "10:00",
      room: entry.room || "",
    });
    setShowModal(true);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      setError("");
      if (editingEntry) {
        await updateTimetableEntry(editingEntry.id, form);
      } else {
        await createTimetableEntry(form);
      }
      setShowModal(false);
      await load();
      if (onTimetableChange) onTimetableChange();
    } catch (err) {
      setError(err.message || "Failed to save timetable entry");
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm("Are you sure you want to delete this timetable entry?")) return;
    try {
      setError("");
      await deleteTimetableEntry(id);
      await load();
      if (onTimetableChange) onTimetableChange();
    } catch (err) {
      setError(err.message || "Failed to delete timetable entry");
    }
  };

  const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

  return (
    <section className="ui-card h-full p-5 sm:p-6">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="ui-eyebrow">Faculty schedule</p>
          <h3 className="mt-1 text-lg font-semibold text-ink">My timetable</h3>
        </div>
        <button
          onClick={openAdd}
          className="ui-button-primary"
        >
          + Add Entry
        </button>
      </div>

      {error && <div role="alert" className="mb-4 rounded-md border border-danger/20 bg-danger/5 p-3 text-sm text-danger">{error}</div>}

      {loading ? (
        <div className="py-4 text-sm text-muted" aria-live="polite">Loading schedule…</div>
      ) : entries.length === 0 ? (
        <div className="rounded-md border border-dashed border-divider p-6 text-center text-sm text-text-secondary">
          No timetable entries added yet. Click "+ Add Entry" to create your schedule.
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-left text-sm text-text-secondary">
            <thead className="border-b border-divider bg-subtle text-xs font-semibold text-muted">
              <tr>
                <th className="py-2.5 px-3">Day</th>
                <th className="py-2.5 px-3">Course</th>
                <th className="py-2.5 px-3">Section</th>
                <th className="py-2.5 px-3">Time</th>
                <th className="py-2.5 px-3">Room</th>
                <th className="py-2.5 px-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {entries.map((item) => (
                <tr key={item.id} className="hover:bg-subtle">
                  <td className="px-3 py-2.5 font-medium text-ink">{item.day_of_week}</td>
                  <td className="px-3 py-2.5 font-semibold text-ink">{item.course_code}</td>
                  <td className="px-3 py-2.5">{item.section}</td>
                  <td className="px-3 py-2.5 text-sm tabular-nums text-text-secondary">
                    {item.start_time?.substring(0, 5)} - {item.end_time?.substring(0, 5)}
                  </td>
                  <td className="px-3 py-2.5">{item.room || "—"}</td>
                  <td className="space-x-1 px-3 py-2.5 text-right">
                    <button
                      onClick={() => openEdit(item)}
                      className="ui-button-quiet min-h-8 px-2 py-1 text-xs"
                    >
                      Edit
                    </button>
                    <button
                      onClick={() => handleDelete(item.id)}
                      className="ui-button-quiet min-h-8 px-2 py-1 text-xs text-danger hover:bg-danger/5 hover:text-danger"
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/35 p-4 backdrop-blur-[2px]">
          <div className="ui-card max-h-[90vh] w-full max-w-lg overflow-y-auto p-6 shadow-xl">
            <h3 className="font-display mb-4 text-xl font-semibold text-ink">
              {editingEntry ? "Edit Timetable Entry" : "Add Timetable Entry"}
            </h3>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-text-secondary">Course code</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. CS101"
                  className="ui-input mt-1"
                  value={form.course_code}
                  onChange={(e) => setForm({ ...form, course_code: e.target.value })}
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium text-text-secondary">Section</label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Sec-A"
                    className="ui-input mt-1"
                    value={form.section}
                    onChange={(e) => setForm({ ...form, section: e.target.value })}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-text-secondary">Day</label>
                  <select
                    className="ui-input mt-1"
                    value={form.day_of_week}
                    onChange={(e) => setForm({ ...form, day_of_week: e.target.value })}
                  >
                    {DAYS.map((d) => (
                      <option key={d} value={d}>
                        {d}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium text-text-secondary">Start time</label>
                  <input
                    type="time"
                    required
                    className="ui-input mt-1"
                    value={form.start_time}
                    onChange={(e) => setForm({ ...form, start_time: e.target.value })}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-text-secondary">End time</label>
                  <input
                    type="time"
                    required
                    className="ui-input mt-1"
                    value={form.end_time}
                    onChange={(e) => setForm({ ...form, end_time: e.target.value })}
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-text-secondary">Room / hall (optional)</label>
                <input
                  type="text"
                  placeholder="e.g. Lab 3 / Room 402"
                  className="ui-input mt-1"
                  value={form.room}
                  onChange={(e) => setForm({ ...form, room: e.target.value })}
                />
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
                  Save Entry
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </section>
  );
}
