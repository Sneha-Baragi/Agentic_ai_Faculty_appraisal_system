import React, { useState } from "react";
import { useAuth } from "../../auth/AuthContext.jsx";
import { Icons } from "../ui/Icons.jsx";

export default function AppLayout({
  children,
  activeTab = "overview",
  onTabChange,
  navItems = [],
  title = "Faculty Appraisal Workspace",
  subtitle = null,
  cycleInfo = null,
}) {
  const { user, logout } = useAuth();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const userRoles = user?.roles || [];
  const primaryRole = userRoles.includes("admin")
    ? "Administrator"
    : userRoles.includes("hod")
    ? "HOD / Reviewer"
    : userRoles.includes("dean")
    ? "Dean"
    : userRoles.includes("iqac")
    ? "IQAC Member"
    : userRoles.includes("faculty")
    ? "Faculty Member"
    : "User";

  const defaultNavItems = navItems.length > 0 ? navItems : [
    { id: "overview", label: "Overview", icon: Icons.Overview },
    { id: "appraisal", label: "My Appraisal", icon: Icons.Appraisal },
    { id: "research", label: "Research & Scholar", icon: Icons.Research },
    { id: "teaching", label: "Teaching & Workload", icon: Icons.Teaching },
    { id: "admin-service", label: "Institutional Service", icon: Icons.Admin },
    { id: "evidence", label: "Evidence Vault", icon: Icons.Evidence },
    { id: "profile", label: "Faculty Profile", icon: Icons.Profile },
  ];

  return (
    <div className="min-h-screen bg-[#F4F7F6] text-[#192522] font-sans antialiased flex flex-col lg:flex-row">
      {/* Sidebar - Desktop */}
      <aside className="hidden lg:flex w-64 shrink-0 flex-col border-r border-[#DCE5E1] bg-white sticky top-0 h-screen z-30">
        {/* Brand Header */}
        <div className="p-5 border-b border-[#DCE5E1] flex items-center gap-3">
          <div className="h-10 w-10 rounded-lg bg-[#194537] text-white flex items-center justify-center font-bold tracking-wider text-sm shadow-sm">
            FA
          </div>
          <div>
            <h1 className="font-semibold text-base text-[#192522] leading-tight">Faculty Appraisal</h1>
            <p className="text-xs text-[#53635E]">University Academic Portal</p>
          </div>
        </div>

        {/* Navigation Section */}
        <div className="flex-1 overflow-y-auto px-3 py-4 space-y-1">
          <div className="px-3 pb-2 text-[11px] font-semibold uppercase tracking-wider text-[#73817C]">
            Navigation
          </div>
          {defaultNavItems.map((item) => {
            const IconComp = item.icon || Icons.Overview;
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => {
                  if (onTabChange) onTabChange(item.id);
                }}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-md text-sm font-medium transition-all ${
                  isActive
                    ? "bg-[#194537] text-white shadow-sm font-semibold"
                    : "text-[#53635E] hover:bg-[#F8FAF9] hover:text-[#192522]"
                }`}
              >
                <IconComp className={`w-4 h-4 ${isActive ? "text-white" : "text-[#73817C]"}`} />
                <span className="truncate">{item.label}</span>
                {isActive && (
                  <span className="ml-auto w-1.5 h-1.5 rounded-full bg-emerald-400" />
                )}
              </button>
            );
          })}
        </div>

        {/* Footer Profile */}
        <div className="p-4 border-t border-[#DCE5E1] bg-[#F8FAF9] flex items-center justify-between gap-2">
          <div className="min-w-0 flex-1">
            <p className="text-xs font-semibold text-[#192522] truncate">{user?.email}</p>
            <span className="inline-block mt-0.5 text-[10px] font-medium px-2 py-0.5 rounded bg-[#194537]/10 text-[#194537]">
              {primaryRole}
            </span>
          </div>
          <button
            onClick={logout}
            title="Sign out"
            className="p-2 text-[#73817C] hover:text-[#B43A3A] hover:bg-red-50 rounded-md transition-colors"
          >
            <Icons.LogOut className="w-4 h-4" />
          </button>
        </div>
      </aside>

      {/* Mobile Drawer Backdrop */}
      {mobileMenuOpen && (
        <div
          className="fixed inset-0 bg-black/40 z-40 lg:hidden backdrop-blur-xs"
          onClick={() => setMobileMenuOpen(false)}
        />
      )}

      {/* Mobile Sidebar Drawer */}
      <div
        className={`fixed top-0 left-0 bottom-0 w-72 bg-white z-50 transform transition-transform duration-200 ease-in-out lg:hidden flex flex-col ${
          mobileMenuOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="p-4 border-b border-[#DCE5E1] flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="h-9 w-9 rounded-lg bg-[#194537] text-white flex items-center justify-center font-bold text-sm">
              FA
            </div>
            <div>
              <h2 className="font-semibold text-sm text-[#192522]">Faculty Appraisal</h2>
              <p className="text-[11px] text-[#53635E]">Academic Portal</p>
            </div>
          </div>
          <button
            onClick={() => setMobileMenuOpen(false)}
            className="p-1.5 rounded-md text-[#73817C] hover:bg-[#F8FAF9]"
          >
            <Icons.Close className="w-5 h-5" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-3 space-y-1">
          {defaultNavItems.map((item) => {
            const IconComp = item.icon || Icons.Overview;
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => {
                  if (onTabChange) onTabChange(item.id);
                  setMobileMenuOpen(false);
                }}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-md text-sm font-medium ${
                  isActive
                    ? "bg-[#194537] text-white font-semibold"
                    : "text-[#53635E] hover:bg-[#F8FAF9]"
                }`}
              >
                <IconComp className="w-4 h-4" />
                <span>{item.label}</span>
              </button>
            );
          })}
        </div>

        <div className="p-4 border-t border-[#DCE5E1] bg-[#F8FAF9] flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold text-[#192522] truncate">{user?.email}</p>
            <span className="text-[10px] text-[#53635E]">{primaryRole}</span>
          </div>
          <button
            onClick={logout}
            className="px-3 py-1.5 text-xs font-medium text-[#B43A3A] hover:bg-red-50 rounded"
          >
            Sign out
          </button>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Top Header Bar */}
        <header className="sticky top-0 z-20 bg-white/95 backdrop-blur-md border-b border-[#DCE5E1] px-4 py-3 sm:px-6 lg:px-8 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3 min-w-0">
            <button
              onClick={() => setMobileMenuOpen(true)}
              className="p-2 rounded-md border border-[#DCE5E1] text-[#53635E] hover:bg-[#F8FAF9] lg:hidden"
              aria-label="Open menu"
            >
              <Icons.Menu className="w-5 h-5" />
            </button>
            <div className="min-w-0">
              <h1 className="text-lg sm:text-xl font-bold text-[#192522] tracking-tight truncate">
                {title}
              </h1>
              {subtitle && (
                <p className="text-xs text-[#53635E] truncate mt-0.5">{subtitle}</p>
              )}
            </div>
          </div>

          {/* Right Header info */}
          <div className="flex items-center gap-3 shrink-0">
            {cycleInfo && (
              <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-full bg-[#F8FAF9] border border-[#DCE5E1] text-xs">
                <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                <span className="font-medium text-[#192522]">{cycleInfo.name || "Academic Cycle"}</span>
                {cycleInfo.academic_year && (
                  <span className="text-[#73817C]">({cycleInfo.academic_year})</span>
                )}
              </div>
            )}
            <div className="h-8 w-8 rounded-full bg-[#194537]/10 text-[#194537] border border-[#194537]/20 flex items-center justify-center font-bold text-xs uppercase">
              {user?.email?.charAt(0) || "U"}
            </div>
          </div>
        </header>

        {/* Page Content Body */}
        <main className="flex-1 p-4 sm:p-6 lg:p-8 max-w-[1440px] w-full mx-auto space-y-6">
          {children}
        </main>
      </div>
    </div>
  );
}
