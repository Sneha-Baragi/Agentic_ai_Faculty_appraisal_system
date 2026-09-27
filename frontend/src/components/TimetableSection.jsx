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
    <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-center justify-between mb-4">
        <div>
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Faculty Schedule</span>
          <h3 className="text-xl font-bold text-slate-900">My Timetable</h3>
        </div>
        <button
          onClick={openAdd}
          className="rounded-md bg-slate-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-slate-800 transition"
        >
          + Add Entry
        </button>
      </div>

      {error && <div className="mb-4 rounded bg-red-50 p-3 text-xs text-red-700">{error}</div>}

      {loading ? (
        <div className="text-sm text-slate-500 py-4">Loading schedule...</div>
      ) : entries.length === 0 ? (
        <div className="rounded border border-dashed border-slate-200 p-6 text-center text-sm text-slate-500">
          No timetable entries added yet. Click "+ Add Entry" to create your schedule.
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm text-slate-600">
            <thead className="bg-slate-50 text-xs font-semibold uppercase text-slate-500 border-b border-slate-200">
              <tr>
                <th className="py-2.5 px-3">Day</th>
                <th className="py-2.5 px-3">Course</th>
                <th className="py-2.5 px-3">Section</th>
                <th className="py-2.5 px-3">Time</th>
                <th className="py-2.5 px-3">Room</th>
                <th className="py-2.5 px-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {entries.map((item) => (
                <tr key={item.id} className="hover:bg-slate-50/50">
                  <td className="py-2.5 px-3 font-medium text-slate-800">{item.day_of_week}</td>
                  <td className="py-2.5 px-3 font-semibold text-slate-900">{item.course_code}</td>
                  <td className="py-2.5 px-3">{item.section}</td>
                  <td className="py-2.5 px-3 text-xs font-mono text-slate-700">
                    {item.start_time?.substring(0, 5)} - {item.end_time?.substring(0, 5)}
                  </td>
                  <td className="py-2.5 px-3">{item.room || "—"}</td>
                  <td className="py-2.5 px-3 text-right space-x-2">
                    <button
                      onClick={() => openEdit(item)}
                      className="text-xs font-medium text-sky-600 hover:text-sky-800"
                    >
                      Edit
                    </button>
                    <button
                      onClick={() => handleDelete(item.id)}
                      className="text-xs font-medium text-rose-600 hover:text-rose-800"
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
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4">
          <div className="w-full max-w-md rounded-lg bg-white p-6 shadow-xl border border-slate-200">
            <h3 className="text-lg font-bold text-slate-900 mb-4">
              {editingEntry ? "Edit Timetable Entry" : "Add Timetable Entry"}
            </h3>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-700">Course Code</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. CS101"
                  className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-slate-800"
                  value={form.course_code}
                  onChange={(e) => setForm({ ...form, course_code: e.target.value })}
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-slate-700">Section</label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Sec-A"
                    className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-slate-800"
                    value={form.section}
                    onChange={(e) => setForm({ ...form, section: e.target.value })}
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-700">Day</label>
                  <select
                    className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-slate-800"
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
                  <label className="block text-xs font-medium text-slate-700">Start Time</label>
                  <input
                    type="time"
                    required
                    className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-slate-800"
                    value={form.start_time}
                    onChange={(e) => setForm({ ...form, start_time: e.target.value })}
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-700">End Time</label>
                  <input
                    type="time"
                    required
                    className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-slate-800"
                    value={form.end_time}
                    onChange={(e) => setForm({ ...form, end_time: e.target.value })}
                  />
                </div>
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-700">Room / Hall (Optional)</label>
                <input
                  type="text"
                  placeholder="e.g. Lab 3 / Room 402"
                  className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-slate-800"
                  value={form.room}
                  onChange={(e) => setForm({ ...form, room: e.target.value })}
                />
              </div>

              <div className="flex justify-end space-x-2 pt-2">
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
                  Save Entry
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
