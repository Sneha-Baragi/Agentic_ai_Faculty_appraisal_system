import { useEffect, useState } from "react";
import { fetchAttendance, fetchTimetable, markAttendance } from "../api/client.js";

export function AttendanceSection({ onAttendanceMarked }) {
  const [timetable, setTimetable] = useState([]);
  const [attendance, setAttendance] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [selectedEntry, setSelectedEntry] = useState("");
  const [attendanceDate, setAttendanceDate] = useState(new Date().toISOString().substring(0, 10));
  const [status, setStatus] = useState("present");

  const loadData = async () => {
    try {
      setLoading(true);
      setError("");
      const [tList, aList] = await Promise.all([fetchTimetable(), fetchAttendance()]);
      setTimetable(tList);
      setAttendance(aList);
      if (tList.length > 0 && !selectedEntry) {
        setSelectedEntry(tList[0].id);
      }
    } catch (err) {
      setError(err.message || "Failed to load attendance data");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleMark = async (e) => {
    e.preventDefault();
    if (!selectedEntry) return;
    try {
      setError("");
      setSuccess("");
      await markAttendance({
        timetable_entry_id: selectedEntry,
        attended_at: new Date(attendanceDate).toISOString(),
        status: status,
      });
      setSuccess("Attendance marked successfully!");
      await loadData();
      if (onAttendanceMarked) onAttendanceMarked();
    } catch (err) {
      setError(err.message || "Failed to mark attendance");
    }
  };

  const presentCount = attendance.filter((a) => a.status === "present").length;
  const absentCount = attendance.filter((a) => a.status === "absent").length;

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Attendance Tracking</span>
          <h3 className="text-xl font-bold text-slate-900">Class Attendance</h3>
        </div>
        <div className="flex space-x-3 text-xs">
          <span className="rounded-md bg-emerald-50 px-2.5 py-1 text-emerald-700 font-semibold border border-emerald-200">
            Attended: {presentCount}
          </span>
          <span className="rounded-md bg-rose-50 px-2.5 py-1 text-rose-700 font-semibold border border-rose-200">
            Absent: {absentCount}
          </span>
        </div>
      </div>

      {error && <div className="rounded bg-red-50 p-3 text-xs text-red-700">{error}</div>}
      {success && <div className="rounded bg-emerald-50 p-3 text-xs text-emerald-700">{success}</div>}

      {/* Attendance Form */}
      <form onSubmit={handleMark} className="rounded-lg bg-slate-50 p-4 border border-slate-200 flex flex-wrap items-end gap-3">
        <div className="flex-1 min-w-[200px]">
          <label className="block text-xs font-medium text-slate-700 mb-1">Select Scheduled Class</label>
          <select
            value={selectedEntry}
            onChange={(e) => setSelectedEntry(e.target.value)}
            className="w-full rounded border border-slate-300 px-3 py-1.5 text-xs bg-white focus:outline-none focus:ring-1 focus:ring-slate-800"
          >
            {timetable.length === 0 ? (
              <option value="">No timetable entries found</option>
            ) : (
              timetable.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.day_of_week}: {t.course_code} ({t.section}) [{t.start_time?.substring(0, 5)} - {t.end_time?.substring(0, 5)}]
                </option>
              ))
            )}
          </select>
        </div>

        <div className="w-36">
          <label className="block text-xs font-medium text-slate-700 mb-1">Date</label>
          <input
            type="date"
            value={attendanceDate}
            onChange={(e) => setAttendanceDate(e.target.value)}
            className="w-full rounded border border-slate-300 px-3 py-1.5 text-xs bg-white focus:outline-none focus:ring-1 focus:ring-slate-800"
          />
        </div>

        <div className="w-32">
          <label className="block text-xs font-medium text-slate-700 mb-1">Status</label>
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className="w-full rounded border border-slate-300 px-3 py-1.5 text-xs bg-white focus:outline-none focus:ring-1 focus:ring-slate-800"
          >
            <option value="present">Present</option>
            <option value="absent">Absent</option>
          </select>
        </div>

        <button
          type="submit"
          disabled={timetable.length === 0}
          className="rounded bg-emerald-600 px-4 py-1.5 text-xs font-medium text-white hover:bg-emerald-700 disabled:opacity-50 transition"
        >
          Mark Attendance
        </button>
      </form>

      {/* Attendance History */}
      <div>
        <h4 className="text-sm font-bold text-slate-800 mb-2">Recent Attendance History</h4>
        {loading ? (
          <div className="text-xs text-slate-500 py-2">Loading attendance history...</div>
        ) : attendance.length === 0 ? (
          <div className="text-xs text-slate-500 py-2">No attendance records found yet.</div>
        ) : (
          <div className="overflow-x-auto max-h-48">
            <table className="w-full text-left text-xs text-slate-600">
              <thead className="bg-slate-100 font-semibold uppercase text-slate-500 sticky top-0">
                <tr>
                  <th className="py-2 px-3">Date</th>
                  <th className="py-2 px-3">Course</th>
                  <th className="py-2 px-3">Section</th>
                  <th className="py-2 px-3">Schedule Time</th>
                  <th className="py-2 px-3">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {attendance.map((rec) => (
                  <tr key={rec.id} className="hover:bg-slate-50">
                    <td className="py-2 px-3 font-medium text-slate-800">
                      {new Date(rec.attended_at).toLocaleDateString()}
                    </td>
                    <td className="py-2 px-3 font-semibold text-slate-900">{rec.course_code || "Class"}</td>
                    <td className="py-2 px-3">{rec.section || "—"}</td>
                    <td className="py-2 px-3 text-slate-700">
                      {rec.start_time?.substring(0, 5)} - {rec.end_time?.substring(0, 5)}
                    </td>
                    <td className="py-2 px-3">
                      <span
                        className={`inline-block px-2 py-0.5 rounded text-[10px] font-semibold ${
                          rec.status === "present"
                            ? "bg-emerald-100 text-emerald-800"
                            : "bg-rose-100 text-rose-800"
                        }`}
                      >
                        {rec.status.toUpperCase()}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
