import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth/AuthContext.jsx";
import { RoleGate } from "./components/RoleGate.jsx";
import AdminDashboard from "./pages/AdminDashboard.jsx";
import FacultyDashboard from "./pages/FacultyDashboard.jsx";
import Login from "./pages/Login.jsx";
import ReviewerDashboard from "./pages/ReviewerDashboard.jsx";

const REVIEWER_ROLES = ["hod", "dean", "iqac", "committee", "admin"];

function HomeRedirect() {
  const { user, loading } = useAuth();
  if (loading) return <p className="p-8 text-sm">Loading…</p>;
  if (!user) return <Navigate to="/login" replace />;
  if (user.roles.includes("faculty")) return <Navigate to="/faculty" replace />;
  if (user.roles.includes("admin")) return <Navigate to="/admin" replace />;
  if (user.roles.some((role) => REVIEWER_ROLES.includes(role))) return <Navigate to="/review" replace />;
  return (
    <main className="mx-auto max-w-xl px-6 py-16">
      <h1 className="font-display text-3xl">Signed in as {user.email}</h1>
      <p className="mt-3 text-sm text-slate-600">No applicable dashboard for roles: {user.roles.join(", ")}</p>
    </main>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="/faculty"
        element={
          <RoleGate allow={["faculty"]}>
            <FacultyDashboard />
          </RoleGate>
        }
      />
      <Route
        path="/review"
        element={
          <RoleGate allow={REVIEWER_ROLES}>
            <ReviewerDashboard />
          </RoleGate>
        }
      />
      <Route
        path="/admin"
        element={
          <RoleGate allow={["admin"]}>
            <AdminDashboard />
          </RoleGate>
        }
      />
      <Route path="/" element={<HomeRedirect />} />
    </Routes>
  );
}
