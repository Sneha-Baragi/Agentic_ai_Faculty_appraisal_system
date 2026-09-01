ALLOWED_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".png", ".jpg", ".jpeg"}
ALLOWED_MIME_PREFIXES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "image/png",
    "image/jpeg",
}

ACTIVITY_TYPES = {
    "research": ["publications", "patents", "research_projects", "conferences", "grants"],
    "teaching": ["courses_taught", "lectures", "laboratory_sessions", "student_projects", "mentoring"],
    "administrative": ["committee_work", "institutional_responsibilities", "events", "administrative_contributions"],
}

TYPE_TO_RUBRIC = {
    "publications": ("research", "journal_paper", 1.0),
    "patents": ("research", "patent", 1.0),
    "research_projects": ("research", "funded_project", 1.0),
    "conferences": ("research", "conference_paper", 1.0),
    "grants": ("research", "funded_project", 1.0),
    "courses_taught": ("teaching", "course_delivery", None),
    "lectures": ("teaching", "course_delivery", None),
    "laboratory_sessions": ("teaching", "course_delivery", None),
    "student_projects": ("teaching", "pedagogy_innovation", 1.0),
    "mentoring": ("teaching", "pedagogy_innovation", 1.0),
    "committee_work": ("administrative", "committee_role", 1.0),
    "institutional_responsibilities": ("administrative", "coordinator", 1.0),
    "events": ("administrative", "outreach", 1.0),
    "administrative_contributions": ("administrative", "outreach", 1.0),
}

CYCLE_STATUSES = ("draft", "open", "under_review", "approved", "closed")
