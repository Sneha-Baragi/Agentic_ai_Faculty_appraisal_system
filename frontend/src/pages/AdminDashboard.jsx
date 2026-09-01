import { useEffect, useState } from "react";
import { useAuth } from "../auth/AuthContext.jsx";
import {
  closeAdminCycle,
  createAdminCycle,
  fetchAdminStatus,
  listAdminCycles,
  listAdminUsers,
  openAdminCycle,
} from "../api/client.js";

function StatCard({ label, value, tone = "default" }) {
  const toneClass =
    tone === "accent"
      ? "border-accent/30 bg-accent/5"
      : "border-slate-200 bg-white";
  return (
    <article className={`rounded-lg border p-4 shadow-sm ${toneClass}`}>
      <p className="text-xs uppercase tracking-widest text-slate-500">{label}</p>
      <p className="mt-2 font-display text-3xl text-ink">{value}</p>
    </article>
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
    <form
      onSubmit={handleSubmit}
      className="mt-4 rounded-lg border border-dashed border-slate-300 bg-slate-50 p-4 text-sm"
    >
      <div className="grid gap-3 md:grid-cols-2">
        <label className="block md:col-span-2">
          <span className="text-slate-500">Cycle name</span>
          <input
            className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            required
          />
        </label>
        <label className="block">
          <span className="text-slate-500">Academic year</span>
          <input
            className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
            placeholder="e.g. 2026-2027"
            value={form.academic_year}
            onChange={(e) => setForm({ ...form, academic_year: e.target.value })}
            required
          />
        </label>
        <label className="block">
          <span className="text-slate-500">Initial status</span>
          <select
            className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
            value={form.status}
            onChange={(e) => setForm({ ...form, status: e.target.value })}
          >
            <option value="draft">Draft</option>
            <option value="open">Open immediately</option>
          </select>
        </label>
        <label className="block">
          <span className="text-slate-500">Start date</span>
          <input
            className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
            type="date"
            value={form.start_date}
            onChange={(e) => setForm({ ...form, start_date: e.target.value })}
            required
          />
        </label>
        <label className="block">
          <span className="text-slate-500">End date</span>
          <input
            className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
            type="date"
            value={form.end_date}
            onChange={(e) => setForm({ ...form, end_date: e.target.value })}
            required
          />
        </label>
      </div>
      {error ? <p className="mt-3 text-sm text-red-700">{error}</p> : null}
      <div className="mt-4 flex justify-end gap-2">
        <button
          type="button"
          onClick={onCancel}
          className="rounded border border-slate-300 px-3 py-1.5"
        >
          Cancel
        </button>
        <button
          type="submit"
          className="rounded bg-accent px-3 py-1.5 font-semibold text-white"
        >
          Create cycle
        </button>
      </div>
    </form>
  );
}

function statusTone(status) {
  if (status === "open") return "green";
  if (status === "closed") return "slate";
  if (status === "draft") return "amber";
  return "slate";
}

function StatusPill({ status }) {
  const tone = statusTone(status);
  const map = {
    slate: "bg-slate-100 text-slate-700",
    green: "bg-emerald-100 text-emerald-800",
    amber: "bg-amber-100 text-amber-800",
    red: "bg-red-100 text-red-800",
  };
  return (
    <span
      className={`rounded px-2 py-0.5 text-xs font-medium ${
        map[tone] ?? map.slate
      }`}
    >
      {status}
    </span>
  );
}

export default function AdminDashboard() {
  const { user, logout } = useAuth();
  const [status, setStatus] = useState(null);
  const [users, setUsers] = useState([]);
  const [cycles, setCycles] = useState([]);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(null);

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
    let mounted = true;
    (async () => {
      try {
        const [s, u, c] = await Promise.all([
          fetchAdminStatus(),
          listAdminUsers(),
          listAdminCycles(),
        ]);
        if (!mounted) return;
        setStatus(s);
        setUsers(u);
        setCycles(c);
      } catch (err) {
        if (mounted) setError(err.message);
      }
    })();
    return () => {
      mounted = false;
    };
  }, []);

  async function handleCreate(payload) {
    setCreating(false);
    await createAdminCycle(payload);
    await refresh();
  }

  async function handleOpen(cycleId) {
    setBusy(cycleId);
    setError("");
    try {
      await openAdminCycle(cycleId);
      await refresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(null);
    }
  }

  async function handleClose(cycleId) {
    setBusy(cycleId);
    setError("");
    try {
      await closeAdminCycle(cycleId);
      await refresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(null);
    }
  }

  return (
    <main className="mx-auto max-w-6xl px-6 py-10">
      <header className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.2em] text-accent">
            Admin dashboard
          </p>
          <h1 className="font-display mt-1 text-3xl">
            System status &amp; overview
          </h1>
          <p className="mt-2 text-sm text-slate-600">
            Signed in as {user?.email}
          </p>
        </div>
        <button onClick={logout} className="text-sm underline">
          Sign out
        </button>
      </header>

      <div className="mt-4 rounded border border-amber-200 bg-amber-50 px-3 py-2 text-sm">
        DEMO/TEST WEIGHTAGES — NOT OFFICIAL UGC. Approval workflow comes in
        Phase 3.
      </div>

      {error ? <p className="mt-4 text-sm text-red-700">{error}</p> : null}

      <section className="mt-8 grid gap-4 md:grid-cols-4">
        <StatCard label="Total users" value={status?.users ?? "—"} />
        <StatCard
          label="Faculty profiles"
          value={status?.faculty_profiles ?? "—"}
        />
        <StatCard label="Cycles" value={status?.cycles ?? "—"} tone="accent" />
        <StatCard label="Phase" value={status?.phase ?? "—"} tone="accent" />
      </section>

      <section className="mt-8 grid gap-4 md:grid-cols-2">
        <article className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="font-semibold text-ink">Storage &amp; compute</h2>
          <dl className="mt-3 space-y-2 text-sm">
            <div className="flex justify-between">
              <dt className="text-slate-500">Storage backend</dt>
              <dd className="font-medium">{status?.storage_backend ?? "—"}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-500">MinIO endpoint</dt>
              <dd className="font-medium">{status?.minio_endpoint ?? "—"}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-500">LLM provider</dt>
              <dd className="font-medium">{status?.llm_provider ?? "none"}</dd>
            </div>
          </dl>
        </article>
        <article className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="font-semibold text-ink">Secrets</h2>
          <p className="mt-3 text-sm text-slate-500">
            No secrets are exposed by this endpoint. Configure via{" "}
            <code>.env</code>.
          </p>
        </article>
      </section>

      <section className="mt-8">
        <h2 className="font-semibold text-ink">Users</h2>
        <div className="mt-3 overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 text-slate-500">
              <tr>
                <th className="px-4 py-2">Email</th>
                <th className="px-4 py-2">Roles</th>
                <th className="px-4 py-2">Active</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {users.map((u) => (
                <tr key={u.id}>
                  <td className="px-4 py-2">{u.email}</td>
                  <td className="px-4 py-2">
                    {u.roles.map((r) => (
                      <span
                        key={r}
                        className="mr-1 inline-block rounded bg-slate-100 px-2 py-0.5 text-xs"
                      >
                        {r}
                      </span>
                    ))}
                  </td>
                  <td className="px-4 py-2">{u.is_active ? "yes" : "no"}</td>
                </tr>
              ))}
              {users.length === 0 ? (
                <tr>
                  <td colSpan="3" className="px-4 py-4 text-slate-400">
                    No users.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>

      <section className="mt-8 pb-10">
        <div className="flex items-start justify-between gap-4">
          <h2 className="font-semibold text-ink">Appraisal cycles</h2>
          {!creating ? (
            <button
              onClick={() => {
                setCreating(true);
                setError("");
              }}
              className="rounded bg-accent px-3 py-1.5 text-sm font-semibold text-white"
            >
              Create cycle
            </button>
          ) : (
            <button
              onClick={() => {
                setCreating(false);
                setError("");
              }}
              className="text-sm underline"
            >
              Cancel
            </button>
          )}
        </div>
        {creating ? (
          <CycleForm onSubmit={handleCreate} onCancel={() => setCreating(false)} />
        ) : null}
        <div className="mt-3 overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 text-slate-500">
              <tr>
                <th className="px-4 py-2">Name</th>
                <th className="px-4 py-2">Academic year</th>
                <th className="px-4 py-2">Start</th>
                <th className="px-4 py-2">End</th>
                <th className="px-4 py-2">Status</th>
                <th className="px-4 py-2 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {cycles.map((c) => (
                <tr key={c.id}>
                  <td className="px-4 py-2">{c.name}</td>
                  <td className="px-4 py-2">{c.academic_year}</td>
                  <td className="px-4 py-2">{c.start_date ?? "—"}</td>
                  <td className="px-4 py-2">{c.end_date ?? "—"}</td>
                  <td className="px-4 py-2">
                    <StatusPill status={c.status} />
                  </td>
                  <td className="px-4 py-2 text-right">
                    {c.status !== "open" ? (
                      <button
                        onClick={() => handleOpen(c.id)}
                        disabled={busy === c.id}
                        className="rounded border border-emerald-300 bg-emerald-50 px-2 py-1 text-xs font-medium text-emerald-800 disabled:opacity-50"
                      >
                        {busy === c.id ? "Opening…" : "Open"}
                      </button>
                    ) : (
                      <button
                        onClick={() => handleClose(c.id)}
                        disabled={busy === c.id}
                        className="rounded border border-slate-300 bg-slate-50 px-2 py-1 text-xs font-medium text-slate-700 disabled:opacity-50"
                      >
                        {busy === c.id ? "Closing…" : "Close"}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
              {cycles.length === 0 ? (
                <tr>
                  <td
                    colSpan="6"
                    className="px-4 py-8 text-center text-slate-400"
                  >
                    No cycles yet. Click <strong>Create cycle</strong> above to
                    get started.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  );
}
