import { useAuth } from "../auth/AuthContext.jsx";

export default function FacultyShell() {
  const { user, logout } = useAuth();
  return (
    <main className="mx-auto max-w-3xl p-8">
      <header className="mb-6 flex items-center justify-between">
        <h1 className="text-xl font-semibold">Faculty dashboard</h1>
        <button className="text-sm underline" onClick={logout} type="button">
          Sign out
        </button>
      </header>
      <p className="rounded border bg-white p-6 text-slate-600">
        Placeholder shell for {user?.email}. Activity capture, evidence, and scores land in later phases.
      </p>
    </main>
  );
}
