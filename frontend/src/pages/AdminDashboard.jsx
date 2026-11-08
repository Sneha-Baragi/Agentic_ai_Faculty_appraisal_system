import { useEffect, useState } from "react";
import { useAuth } from "../auth/AuthContext.jsx";
import AppLayout from "../components/layout/AppLayout.jsx";
import { Icons } from "../components/ui/Icons.jsx";
import {
  closeAdminCycle,
  createAdminCycle,
  fetchAdminStatus,
  listAdminCycles,
  listAdminUsers,
  openAdminCycle,
} from "../api/client.js";
import { CloudOpsSection } from "../components/CloudOpsSection.jsx";
import { SDLCFactorySection } from "../components/SDLCFactorySection.jsx";

function StatTile({ label, value, subtext, icon: IconComp }) {
  return (
    <div className="bg-white rounded-lg border border-[#DCE5E1] p-4 shadow-xs flex items-center justify-between">
      <div>
        <p className="text-[11px] font-semibold uppercase text-[#73817C]">{label}</p>
        <p className="text-2xl font-bold text-[#192522] mt-1">{value}</p>
        {subtext && <p className="text-xs text-[#53635E] mt-0.5">{subtext}</p>}
      </div>
      {IconComp && (
        <div className="h-10 w-10 rounded-lg bg-[#F8FAF9] border border-[#DCE5E1] text-[#194537] flex items-center justify-center shrink-0">
          <IconComp className="w-5 h-5" />
        </div>
      )}
    </div>
  );
}

function CycleForm({ onSubmit, onCancel }) {
  const today = new Date();
  const yyyy = today.getFullYear();
  const [form, setForm] = useState({
    name: `Academic Appraisal ${yyyy}-${yyyy + 1}`,
    academic_year: `${yyyy}-${yyyy + 1}`,
    start_date: `${yyyy}-08-01`,
    end_date: `${yyyy + 1}-07-31`,
    status: "draft",
  });
  const [error, setError] = useState("");

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    try {
      await onSubmit(form);
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="p-4 rounded-lg bg-[#F8FAF9] border border-[#DCE5E1] space-y-4 text-xs">
      <h4 className="font-bold text-sm text-[#192522]">Create New Appraisal Cycle</h4>
      <div className="grid gap-3 md:grid-cols-2">
        <label className="block md:col-span-2">
          <span className="text-[#53635E]">Cycle Name</span>
          <input
            className="w-full mt-1 h-9 px-3 rounded border border-[#DCE5E1] bg-white text-xs text-[#192522]"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            required
          />
        </label>
        <label className="block">
          <span className="text-[#53635E]">Academic Year</span>
          <input
            className="w-full mt-1 h-9 px-3 rounded border border-[#DCE5E1] bg-white text-xs text-[#192522]"
            placeholder="e.g. 2026-2027"
            value={form.academic_year}
            onChange={(e) => setForm({ ...form, academic_year: e.target.value })}
            required
          />
        </label>
        <label className="block">
          <span className="text-[#53635E]">Initial Status</span>
          <select
            className="w-full mt-1 h-9 px-2 rounded border border-[#DCE5E1] bg-white text-xs text-[#192522]"
            value={form.status}
            onChange={(e) => setForm({ ...form, status: e.target.value })}
          >
            <option value="draft">Draft</option>
            <option value="open">Open Immediately</option>
          </select>
        </label>
        <label className="block">
          <span className="text-[#53635E]">Start Date</span>
          <input
            className="w-full mt-1 h-9 px-2 rounded border border-[#DCE5E1] bg-white text-xs text-[#192522]"
            type="date"
            value={form.start_date}
            onChange={(e) => setForm({ ...form, start_date: e.target.value })}
            required
          />
        </label>
        <label className="block">
          <span className="text-[#53635E]">End Date</span>
          <input
            className="w-full mt-1 h-9 px-2 rounded border border-[#DCE5E1] bg-white text-xs text-[#192522]"
            type="date"
            value={form.end_date}
            onChange={(e) => setForm({ ...form, end_date: e.target.value })}
            required
          />
        </label>
      </div>
      {error && <p className="text-xs text-red-600">{error}</p>}
      <div className="flex justify-end gap-2 pt-2 border-t border-[#DCE5E1]">
        <button type="button" onClick={onCancel} className="px-3 py-1.5 rounded border border-[#DCE5E1] text-xs font-semibold text-[#53635E]">
          Cancel
        </button>
        <button type="submit" className="px-4 py-1.5 rounded bg-[#194537] text-white text-xs font-semibold">
          Save Cycle
        </button>
      </div>
    </form>
  );
}

export default function AdminDashboard() {
  const { user } = useAuth();
  const [status, setStatus] = useState(null);
  const [users, setUsers] = useState([]);
  const [cycles, setCycles] = useState([]);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(null);

  const adminNavItems = [
    { id: "overview", label: "Admin Overview", icon: Icons.Overview },
    { id: "cycles", label: "Cycle Management", icon: Icons.Schedule },
    { id: "users", label: "User Accounts", icon: Icons.Users },
  ];

  async function refresh() {
    try {
      const [s, u, c] = await Promise.all([
        fetchAdminStatus(),
        listAdminUsers(),
        listAdminCycles(),
      ]);
      setStatus(s);
      setUsers(u);
      setCycles(c);
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function handleCreate(payload) {
    setCreating(false);
    await createAdminCycle(payload);
    await refresh();
  }

  async function handleOpenCycle(id) {
    setBusy(id);
    try {
      await openAdminCycle(id);
      await refresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(null);
    }
  }

  async function handleCloseCycle(id) {
    setBusy(id);
    try {
      await closeAdminCycle(id);
      await refresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(null);
    }
  }

  return (
    <AppLayout
      title="System Administration Console"
      subtitle={`Signed in as Admin (${user?.email})`}
      navItems={adminNavItems}
    >
      {error && <div className="p-3 rounded bg-red-50 border border-red-200 text-xs text-red-700 font-semibold">{error}</div>}

      {/* Admin Stats Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <StatTile
          label="Registered Users"
          value={users.length}
          subtext="Faculty, Reviewers, Administrators"
          icon={Icons.Users}
        />
        <StatTile
          label="Appraisal Cycles"
          value={cycles.length}
          subtext={`${cycles.filter(c => c.status === 'open').length} Active Open Cycle`}
          icon={Icons.Schedule}
        />
        <StatTile
          label="Active Cycle Status"
          value={status?.open_cycle ? "OPEN" : "CLOSED"}
          subtext={status?.open_cycle?.name || "No open cycle"}
          icon={Icons.Appraisal}
        />
      </div>

      {/* Cycle Management Section */}
      <div className="bg-white rounded-lg border border-[#DCE5E1] p-5 sm:p-6 shadow-xs space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#DCE5E1] pb-4">
          <div>
            <span className="text-[11px] font-semibold uppercase tracking-wider text-[#73817C]">Appraisal Cycle Administration</span>
            <h3 className="text-lg font-bold text-[#192522]">Cycle Control</h3>
          </div>
          {!creating ? (
            <button
              onClick={() => setCreating(true)}
              className="h-9 px-4 rounded bg-[#194537] text-white text-xs font-semibold hover:bg-[#194537]/90"
            >
              + Create New Cycle
            </button>
          ) : (
            <button
              onClick={() => setCreating(false)}
              className="h-9 px-3 rounded border border-[#DCE5E1] text-xs font-semibold text-[#53635E]"
            >
              Cancel Create
            </button>
          )}
        </div>

        {creating && <CycleForm onSubmit={handleCreate} onCancel={() => setCreating(false)} />}

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-[#53635E]">
            <thead className="bg-[#F8FAF9] font-semibold text-[#73817C] border-b border-[#DCE5E1]">
              <tr>
                <th className="py-3 px-4">Cycle Name</th>
                <th className="py-3 px-4">Academic Year</th>
                <th className="py-3 px-4">Start Date</th>
                <th className="py-3 px-4">End Date</th>
                <th className="py-3 px-4 text-center">Status</th>
                <th className="py-3 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#DCE5E1]">
              {cycles.map((c) => (
                <tr key={c.id} className="hover:bg-[#F8FAF9]">
                  <td className="py-3 px-4 font-bold text-[#192522]">{c.name}</td>
                  <td className="py-3 px-4">{c.academic_year}</td>
                  <td className="py-3 px-4">{c.start_date || c.starts_on || "—"}</td>
                  <td className="py-3 px-4">{c.end_date || c.ends_on || "—"}</td>
                  <td className="py-3 px-4 text-center">
                    <span
                      className={`inline-block px-2.5 py-0.5 rounded-full font-semibold ${
                        c.status === "open"
                          ? "bg-emerald-100 text-emerald-800"
                          : c.status === "closed"
                          ? "bg-slate-100 text-slate-700"
                          : "bg-amber-100 text-amber-800"
                      }`}
                    >
                      {c.status.toUpperCase()}
                    </span>
                  </td>
                  <td className="py-3 px-4 text-right">
                    {c.status !== "open" ? (
                      <button
                        disabled={busy === c.id}
                        onClick={() => handleOpenCycle(c.id)}
                        className="px-3 py-1 rounded bg-[#194537] text-white font-semibold hover:bg-[#194537]/90 disabled:opacity-50"
                      >
                        Open Cycle
                      </button>
                    ) : (
                      <button
                        disabled={busy === c.id}
                        onClick={() => handleCloseCycle(c.id)}
                        className="px-3 py-1 rounded border border-red-300 bg-red-50 text-red-700 font-semibold hover:bg-red-100 disabled:opacity-50"
                      >
                        Close Cycle
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* User Accounts Section */}
      <div className="bg-white rounded-lg border border-[#DCE5E1] p-5 sm:p-6 shadow-xs space-y-4">
        <div className="border-b border-[#DCE5E1] pb-3">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-[#73817C]">User Management</span>
          <h3 className="text-lg font-bold text-[#192522]">Registered User Accounts ({users.length})</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-[#53635E]">
            <thead className="bg-[#F8FAF9] font-semibold text-[#73817C] border-b border-[#DCE5E1]">
              <tr>
                <th className="py-3 px-4">User Email</th>
                <th className="py-3 px-4">Assigned Roles</th>
                <th className="py-3 px-4 text-center">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#DCE5E1]">
              {users.map((u) => (
                <tr key={u.id} className="hover:bg-[#F8FAF9]">
                  <td className="py-3 px-4 font-semibold text-[#192522]">{u.email}</td>
                  <td className="py-3 px-4">
                    <div className="flex flex-wrap gap-1">
                      {u.roles?.map((r) => (
                        <span key={r} className="px-2 py-0.5 rounded bg-slate-100 text-slate-700 font-medium capitalize">
                          {r}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td className="py-3 px-4 text-center">
                    <span className={`inline-block px-2.5 py-0.5 rounded-full font-semibold ${u.is_active ? "bg-emerald-100 text-emerald-800" : "bg-red-100 text-red-800"}`}>
                      {u.is_active ? "Active" : "Inactive"}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Agentic SDLC Factory Panel */}
      <SDLCFactorySection />

      {/* Cloud Operations Diagnostic Panel */}
      <CloudOpsSection />
    </AppLayout>
  );
}
