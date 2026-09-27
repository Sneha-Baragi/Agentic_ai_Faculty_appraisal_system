const TOKEN_KEY = "faa_token";

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

async function request(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  const isFormData = typeof options.body !== "undefined" && options.body instanceof FormData;
  if (options.body && !isFormData && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }
  const response = await fetch(path, { ...options, headers });
  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    throw new Error(detail.detail || `Request failed (${response.status})`);
  }
  if (response.status === 204) {
    return null;
  }

  const text = await response.text();
  if (!text) {
    return null;
  }

  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

export function login(email, password) {
  return request("/api/v1/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export function fetchMe() {
  return request("/api/v1/auth/me");
}

export function fetchProfile() {
  return request("/api/v1/profile/me");
}

export function updateProfile(patch) {
  return request("/api/v1/profile/me", {
    method: "PATCH",
    body: JSON.stringify(patch),
  });
}

export function listCycles() {
  return request("/api/v1/cycles");
}

export function fetchCurrentCycle() {
  return request("/api/v1/cycles/current");
}

export function listActivities(category) {
  const qs = category ? `?category=${encodeURIComponent(category)}` : "";
  return request(`/api/v1/activities${qs}`);
}

export function createActivity(payload) {
  return request("/api/v1/activities", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateActivity(activityId, payload) {
  return request(`/api/v1/activities/${activityId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function deleteActivity(activityId) {
  return request(`/api/v1/activities/${activityId}`, {
    method: "DELETE",
  });
}

export function listActivityTypes() {
  return request("/api/v1/activities/types");
}

export function listEvidence(activityId) {
  const qs = activityId ? `?activity_id=${encodeURIComponent(activityId)}` : "";
  return request(`/api/v1/evidence${qs}`);
}

export function getEvidence(evidenceId) {
  return request(`/api/v1/evidence/${evidenceId}`);
}

export function uploadEvidence(activityId, file) {
  const form = new FormData();
  form.append("activity_id", activityId);
  form.append("file", file);
  return request(`/api/v1/evidence?activity_id=${encodeURIComponent(activityId)}`, {
    method: "POST",
    body: form,
  });
}

export function downloadEvidenceUrl(evidenceId) {
  const token = getToken();
  if (!token) return `/api/v1/evidence/${evidenceId}/file`;
  return `/api/v1/evidence/${evidenceId}/file`;
}

export function runAppraisal() {
  return request("/api/v1/appraisals/run", { method: "POST" });
}

export function fetchCurrentAppraisal() {
  return request("/api/v1/appraisals/current");
}

export function fetchCurrentReport() {
  return request("/api/v1/reports/current");
}

export function createAgentPlan(payload) {
  return request("/api/v1/agent/plans", { method: "POST", body: JSON.stringify(payload) });
}

export function answerAgentPlan(planId, answers) {
  return request(`/api/v1/agent/plans/${planId}/clarify`, { method: "POST", body: JSON.stringify({ answers }) });
}

export function reviseAgentPlan(planId, payload) {
  return request(`/api/v1/agent/plans/${planId}`, { method: "PATCH", body: JSON.stringify(payload) });
}

export function lockAgentPlan(planId) {
  return request(`/api/v1/agent/plans/${planId}/lock`, { method: "POST" });
}

export function listReviewerFaculty() {
  return request("/api/v1/review/faculty");
}

export function fetchReviewerFacultyPacket(facultyId) {
  return request(`/api/v1/review/faculty/${facultyId}`);
}

export function approveReviewerAppraisal(facultyId, payload = {}) {
  return request(`/api/v1/review/faculty/${facultyId}/approve`, { method: "POST", body: JSON.stringify(payload) });
}

export function rejectReviewerAppraisal(facultyId, payload) {
  return request(`/api/v1/review/faculty/${facultyId}/reject`, { method: "POST", body: JSON.stringify(payload) });
}

export function requestReviewerChanges(facultyId, payload) {
  return request(`/api/v1/review/faculty/${facultyId}/request-changes`, { method: "POST", body: JSON.stringify(payload) });
}

export function editReviewerReport(facultyId, payload) {
  return request(`/api/v1/review/faculty/${facultyId}/report/edit`, { method: "PATCH", body: JSON.stringify(payload) });
}

export function overrideReviewerReport(facultyId, payload) {
  return request(`/api/v1/review/faculty/${facultyId}/report/override`, { method: "POST", body: JSON.stringify(payload) });
}

export function rollbackReviewerReport(facultyId, payload) {
  return request(`/api/v1/review/faculty/${facultyId}/report/rollback`, { method: "POST", body: JSON.stringify(payload) });
}

export function publishReviewerReport(facultyId) {
  return request(`/api/v1/review/faculty/${facultyId}/report/publish`, { method: "POST" });
}

export function resubmitAppraisal() {
  return request("/api/v1/appraisals/resubmit", { method: "POST" });
}

export function listAdminUsers() {
  return request("/api/v1/admin/users");
}

export function listAdminCycles() {
  return request("/api/v1/admin/cycles");
}

export function createAdminCycle(payload) {
  return request("/api/v1/admin/cycles", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function openAdminCycle(cycleId) {
  return request(`/api/v1/admin/cycles/${cycleId}/open`, {
    method: "PATCH",
  });
}

export function closeAdminCycle(cycleId) {
  return request(`/api/v1/admin/cycles/${cycleId}/close`, {
    method: "PATCH",
  });
}

export function fetchAdminStatus() {
  return request("/api/v1/admin/status");
}

export function fetchTeachingRequirement() {
  return request("/api/v1/teaching-requirements/me");
}

export function fetchTimetable() {
  return request("/api/v1/timetable/me");
}

export function createTimetableEntry(payload) {
  return request("/api/v1/timetable", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateTimetableEntry(entryId, payload) {
  return request(`/api/v1/timetable/${entryId}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export function deleteTimetableEntry(entryId) {
  return request(`/api/v1/timetable/${entryId}`, {
    method: "DELETE",
  });
}

export function fetchAttendance() {
  return request("/api/v1/attendance/me");
}

export function markAttendance(payload) {
  return request("/api/v1/attendance/mark", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function fetchResearchPaperStatus() {
  return request("/api/v1/research-papers/me");
}

export function fetchProjectTeams() {
  return request("/api/v1/project-teams/me");
}

export function createProjectTeam(payload) {
  return request("/api/v1/project-teams", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateProjectTeam(teamId, payload) {
  return request(`/api/v1/project-teams/${teamId}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export function deleteProjectTeam(teamId) {
  return request(`/api/v1/project-teams/${teamId}`, {
    method: "DELETE",
  });
}

