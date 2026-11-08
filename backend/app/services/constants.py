ALLOWED_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".png", ".jpg", ".jpeg"}
ALLOWED_MIME_PREFIXES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "image/png",
    "image/jpeg",
}

# Supported MIME aliases mapped by declared file extension
ALLOWED_MIME_BY_EXT: dict[str, set[str]] = {
    ".pdf": {"application/pdf", "application/x-pdf", "application/octet-stream"},
    ".docx": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword",
        "application/zip",
        "application/x-zip-compressed",
        "application/octet-stream",
    },
    ".xlsx": {
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel",
        "application/zip",
        "application/x-zip-compressed",
        "application/octet-stream",
    },
    ".png": {"image/png", "image/x-png", "application/octet-stream"},
    ".jpg": {"image/jpeg", "image/jpg", "image/pjpeg", "application/octet-stream"},
    ".jpeg": {"image/jpeg", "image/jpg", "image/pjpeg", "application/octet-stream"},
}

DISALLOWED_MIME_TYPES = {
    "text/html",
    "text/javascript",
    "application/javascript",
    "application/x-javascript",
    "application/x-executable",
    "application/x-msdownload",
    "application/x-dosexec",
    "application/exe",
    "application/x-sh",
    "application/x-bat",
}

# Parser and Decompression Security Limits (SEC-05)
MAX_PDF_PAGES: int = 50
MAX_EXTRACTED_CHARS: int = 50_000
MAX_ZIP_UNCOMPRESSED_BYTES: int = 30 * 1024 * 1024  # 30 MiB
MAX_ZIP_RATIO: float = 100.0
MAX_ZIP_MEMBERS: int = 150
MAX_XLSX_SHEETS: int = 5
MAX_XLSX_ROWS_PER_SHEET: int = 2_000

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
