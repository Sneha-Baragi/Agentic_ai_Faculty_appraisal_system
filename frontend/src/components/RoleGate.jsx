import { Navigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext.jsx";

export function RoleGate({ allow, children }) {
  const { user, loading } = useAuth();
  if (loading) return <p className="p-8 text-sm">Loading…</p>;
  if (!user) return <Navigate to="/login" replace />;
  const ok = user.roles.some((role) => allow.includes(role));
  if (!ok) return <Navigate to="/" replace />;
  return children;
}
