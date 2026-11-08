import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext.jsx";
import { Icons } from "../components/ui/Icons.jsx";

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

  function setDemo(demoEmail, demoPass) {
    setEmail(demoEmail);
    setPassword(demoPass);
  }

  return (
    <main className="min-h-screen bg-[#F4F7F6] text-[#192522] font-sans antialiased flex flex-col justify-center items-center p-4 sm:p-6">
      <div className="w-full max-w-md space-y-6">
        {/* Brand Header */}
        <div className="text-center space-y-2">
          <div className="inline-flex h-12 w-12 rounded-xl bg-[#194537] text-white font-bold text-lg items-center justify-center shadow-md">
            FA
          </div>
          <h1 className="text-2xl font-bold text-[#192522] tracking-tight">
            Faculty Appraisal Portal
          </h1>
          <p className="text-xs text-[#53635E]">
            Agentic Academic Performance System
          </p>
        </div>

        {/* Login Card */}
        <div className="bg-white rounded-xl border border-[#DCE5E1] p-6 shadow-sm space-y-5">
          <div className="border-b border-[#DCE5E1] pb-3">
            <h2 className="text-base font-bold text-[#192522]">Sign In to Your Account</h2>
            <p className="text-xs text-[#53635E]">Enter your credentials or click a demo profile below.</p>
          </div>

          <form onSubmit={onSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-[#53635E] mb-1">Email Address</label>
              <input
                type="email"
                required
                className="w-full h-10 px-3 rounded-md border border-[#DCE5E1] bg-white text-sm text-[#192522] outline-none focus:border-[#194537] focus:ring-2 focus:ring-[#194537]/20"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-[#53635E] mb-1">Password</label>
              <input
                type="password"
                required
                className="w-full h-10 px-3 rounded-md border border-[#DCE5E1] bg-white text-sm text-[#192522] outline-none focus:border-[#194537] focus:ring-2 focus:ring-[#194537]/20"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>

            {error && (
              <p className="p-2.5 rounded bg-red-50 border border-red-200 text-xs text-red-700 font-medium">
                {error}
              </p>
            )}

            <button
              type="submit"
              className="w-full h-10 rounded-md bg-[#194537] text-white text-xs font-bold uppercase tracking-wider hover:bg-[#194537]/90 shadow-xs transition-colors"
            >
              Sign In
            </button>
          </form>

          {/* Quick Demo Accounts Selection */}
          <div className="border-t border-[#DCE5E1] pt-4 space-y-2">
            <p className="text-[11px] font-semibold uppercase text-[#73817C] text-center">Quick Demo Accounts</p>
            <div className="grid grid-cols-2 gap-2 text-xs">
              <button
                type="button"
                onClick={() => setDemo("faculty@demo.local", "faculty-demo")}
                className="p-2 rounded border border-[#DCE5E1] bg-[#F8FAF9] hover:bg-[#194537]/10 text-left font-medium text-[#192522]"
              >
                Faculty Member
              </button>
              <button
                type="button"
                onClick={() => setDemo("hod@demo.local", "hod-demo")}
                className="p-2 rounded border border-[#DCE5E1] bg-[#F8FAF9] hover:bg-[#194537]/10 text-left font-medium text-[#192522]"
              >
                HOD Reviewer
              </button>
              <button
                type="button"
                onClick={() => setDemo("dean@demo.local", "dean-demo")}
                className="p-2 rounded border border-[#DCE5E1] bg-[#F8FAF9] hover:bg-[#194537]/10 text-left font-medium text-[#192522]"
              >
                Dean Reviewer
              </button>
              <button
                type="button"
                onClick={() => setDemo("admin@demo.local", "admin-demo")}
                className="p-2 rounded border border-[#DCE5E1] bg-[#F8FAF9] hover:bg-[#194537]/10 text-left font-medium text-[#192522]"
              >
                System Admin
              </button>
            </div>
          </div>
        </div>

        <p className="text-center text-[11px] text-[#73817C]">
          Faculty Appraisal System · DEMO/TEST Weightages
        </p>
      </div>
    </main>
  );
}
