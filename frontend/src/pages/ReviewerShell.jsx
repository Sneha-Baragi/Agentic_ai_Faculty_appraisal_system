import { useAuth } from "../auth/AuthContext.jsx";

export default function ReviewerShell() {
  const { user, logout } = useAuth();
  return (
    <main className="mx-auto max-w-3xl p-8">
      <header className="mb-6 flex items-center justify-between">
        <h1 className="text-xl font-semibold">Reviewer dashboard</h1>
        <button className="text-sm underline" onClick={logout} type="button">
          Sign out
        </button>
      </header>
      <p className="mb-3 text-sm text-slate-500">Roles: {user?.roles?.join(", ")}</p>
      <p className="rounded border bg-white p-6 text-slate-600">
        Placeholder queue for HoD / Dean / IQAC / committee (and admin in Phase 1). Approval actions are not
        implemented yet.
      </p>
    </main>
  );
}
