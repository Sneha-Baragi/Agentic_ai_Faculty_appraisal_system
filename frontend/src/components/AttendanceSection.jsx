import { useEffect, useState } from "react";
import { fetchAttendance, fetchTimetable, markAttendance, syncAttendance } from "../api/client.js";

export function AttendanceSection({ onAttendanceMarked, cycleId }) {
  const [timetable, setTimetable] = useState([]);
  const [attendance, setAttendance] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [syncing, setSyncing] = useState(false);
  const [syncMsg, setSyncMsg] = useState("");
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

  const handleSync = async () => {
    try {
      setSyncing(true);
      setError("");
      setSyncMsg("");
      const res = await syncAttendance(cycleId);
      setSyncMsg(res.message || `Synchronized ${res.synchronized_hours} hours to course delivery.`);
      await loadData();
      if (onAttendanceMarked) onAttendanceMarked();
    } catch (err) {
      setError(err.message || "Failed to synchronize attendance");
    } finally {
      setSyncing(false);
    }
  };

  const presentCount = attendance.filter((a) => a.status === "present").length;
  const absentCount = attendance.filter((a) => a.status === "absent").length;

  return (
    <section className="ui-card space-y-5 p-5 sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="ui-eyebrow">Attendance tracking</p>
          <h3 className="mt-1 text-lg font-semibold text-ink">Class attendance</h3>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span className="ui-status-success">
            Attended: {presentCount}
          </span>
          <span className="ui-status-danger">
            Absent: {absentCount}
          </span>
          <button
            type="button"
            onClick={handleSync}
            disabled={syncing || presentCount === 0}
            className="inline-flex items-center gap-1.5 px-3 py-1 rounded-md bg-[#194537] text-white font-semibold hover:bg-[#194537]/90 disabled:opacity-50 transition-colors cursor-pointer"
          >
            {syncing ? "Syncing…" : "Sync to Course Delivery"}
          </button>
        </div>
      </div>

      {error && <div role="alert" className="rounded-md border border-danger/20 bg-danger/5 p-3 text-sm text-danger">{error}</div>}
      {success && <div role="status" className="rounded-md border border-success/20 bg-success/5 p-3 text-sm text-success">{success}</div>}
      {syncMsg && (
        <div role="status" className="rounded-md border border-emerald-200 bg-emerald-50 p-3 text-xs text-emerald-800">
          <span className="font-semibold">Course Delivery Sync:</span> {syncMsg}
        </div>
      )}

      {/* Attendance & Scoring Integration Policy Notice */}
      <div className="rounded-md border border-[#DCE5E1] bg-[#F8FAF9] p-3 text-xs text-[#53635E] space-y-1">
        <span className="font-semibold text-[#192522]">Course Delivery & Attendance Integration Rules:</span>
        <ul className="list-disc list-inside space-y-0.5 text-[11px] text-[#53635E]">
          <li>Only validated completed sessions marked <strong>Present</strong> within the current appraisal cycle are eligible (0.50 pts/hr up to rubric cap).</li>
          <li>Timetable schedule slots alone do not confer points without validated attendance. Absent or cancelled sessions earn 0 points.</li>
          <li><strong>Double-counting prevention:</strong> Courses already submitted as manual course delivery activities (e.g. CSAI101) are automatically skipped.</li>
          <li><strong>Idempotent:</strong> Subsequent synchronizations update verified hours in-place without duplicating activity records.</li>
        </ul>
      </div>

      {/* Attendance Form */}
      <form onSubmit={handleMark} className="ui-card-subtle flex flex-wrap items-end gap-3 p-4">
        <div className="flex-1 min-w-[200px]">
          <label className="mb-1 block text-xs font-medium text-text-secondary">Select scheduled class</label>
          <select
            value={selectedEntry}
            onChange={(e) => setSelectedEntry(e.target.value)}
            className="ui-input min-h-10"
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
          <label className="mb-1 block text-xs font-medium text-text-secondary">Date</label>
          <input
            type="date"
            value={attendanceDate}
            onChange={(e) => setAttendanceDate(e.target.value)}
            className="ui-input min-h-10"
          />
        </div>

        <div className="w-32">
          <label className="mb-1 block text-xs font-medium text-text-secondary">Status</label>
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className="ui-input min-h-10"
          >
            <option value="present">Present</option>
            <option value="absent">Absent</option>
          </select>
        </div>

        <button
          type="submit"
          disabled={timetable.length === 0}
          className="ui-button-primary"
        >
          Mark Attendance
        </button>
      </form>

      {/* Attendance History */}
      <div>
        <h4 className="mb-2 text-sm font-semibold text-ink">Recent attendance history</h4>
        {loading ? (
          <div className="py-2 text-sm text-muted" aria-live="polite">Loading attendance history…</div>
        ) : attendance.length === 0 ? (
          <div className="py-2 text-sm text-muted">No attendance records found yet.</div>
        ) : (
          <div className="overflow-x-auto max-h-48">
            <table className="w-full min-w-[620px] text-left text-sm text-text-secondary">
              <thead className="sticky top-0 bg-subtle text-xs font-semibold text-muted">
                <tr>
                  <th className="py-2 px-3">Date</th>
                  <th className="py-2 px-3">Course</th>
                  <th className="py-2 px-3">Section</th>
                  <th className="py-2 px-3">Schedule Time</th>
                  <th className="py-2 px-3">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {attendance.map((rec) => (
                  <tr key={rec.id} className="hover:bg-subtle">
                    <td className="px-3 py-2.5 font-medium text-ink">
                      {new Date(rec.attended_at).toLocaleDateString()}
                    </td>
                    <td className="px-3 py-2.5 font-semibold text-ink">{rec.course_code || "Class"}</td>
                    <td className="px-3 py-2.5">{rec.section || "—"}</td>
                    <td className="px-3 py-2.5 text-text-secondary">
                      {rec.start_time?.substring(0, 5)} - {rec.end_time?.substring(0, 5)}
                    </td>
                    <td className="px-3 py-2.5">
                      <span
                        className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${
                          rec.status === "present"
                            ? "bg-success/10 text-success"
                            : "bg-danger/10 text-danger"
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
    </section>
  );
}
