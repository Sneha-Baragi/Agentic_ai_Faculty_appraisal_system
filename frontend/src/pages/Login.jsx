import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext.jsx";

const REVIEWER_ROLES = ["hod", "dean", "iqac", "committee"];

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("faculty@demo.local");
  const [password, setPassword] = useState("faculty-demo");
  const [error, setError] = useState("");

  async function onSubmit(event) {
    event.preventDefault();
    setError("");
    try {
      const me = await login(email, password);
      if (me.roles.includes("faculty")) navigate("/faculty");
      else if (me.roles.includes("admin")) navigate("/admin");
      else if (me.roles.some((role) => REVIEWER_ROLES.includes(role))) navigate("/review");
      else navigate("/");
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-lg flex-col justify-center px-6">
      <p className="text-xs uppercase tracking-[0.2em] text-accent">Phase 2 DEMO</p>
      <h1 className="font-display mt-2 text-4xl font-semibold">Faculty Appraisal</h1>
      <p className="mt-3 text-sm text-slate-600">
        Agentic AI worklet skeleton. Scoring uses DEMO/TEST weightages, not official UGC values.
      </p>
      <form onSubmit={onSubmit} className="mt-8 space-y-4 rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
        <label className="block text-sm font-semibold">
          Email
          <input
            className="mt-1 w-full rounded border border-slate-300 px-3 py-2 font-normal"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </label>
        <label className="block text-sm font-semibold">
          Password
          <input
            type="password"
            className="mt-1 w-full rounded border border-slate-300 px-3 py-2 font-normal"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </label>
        {error ? <p className="text-sm text-red-700">{error}</p> : null}
        <button type="submit" className="w-full rounded bg-accent py-2 text-sm font-semibold text-white">
          Sign in
        </button>
      </form>
      <p className="mt-4 text-xs text-slate-500">
        Demo accounts: faculty@demo.local / faculty-demo · hod@demo.local / hod-demo · dean@demo.local / dean-demo ·
        iqac@demo.local / iqac-demo · committee@demo.local / committee-demo · admin@demo.local / admin-demo
      </p>
    </main>
  );
}
