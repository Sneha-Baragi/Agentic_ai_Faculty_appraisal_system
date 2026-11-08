import json
from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy import func, select

from app.agents.tools import FacultyInput, ToolError, read_google_scholar_profile_tool
from app.models import AppraisalReport, AuditLog, FacultyActivity
from app.services.google_scholar import GoogleScholarError, GoogleScholarService
from app.services.activities import create_activity
from .conftest import auth_headers, login, make_cycle, make_faculty_profile, make_user
from .test_phase2 import _attach_valid_evidence


API_KEY = "test-only-serpapi-key"
SCHOLAR_ID = "ScholarId123"


def _serpapi_payload(*, author_id: str = SCHOLAR_ID) -> dict:
    return {
        "search_parameters": {"author_id": author_id},
        "search_metadata": {
            "google_scholar_author_url": (
                f"https://scholar.google.com/citations?user={author_id}"
            )
        },
        "author": {"name": "Faculty Example"},
        "cited_by": {
            "table": [
                {"citations": {"all": "1,234", "since_2016": "900"}},
                {"h_index": {"all": "24", "since_2016": "19"}},
                {"i10_index": {"all": "57", "since_2016": "42"}},
            ]
        },
        "articles": [
            {
                "title": "A Research Paper",
                "authors": "Faculty Example, Coauthor",
                "publication": "Journal of Examples",
                "year": "2024",
                "cited_by": {"value": "12"},
                "link": "https://example.test/paper",
                "citation_id": "citation-1",
            },
            {"title": "Older Paper", "year": "2010"},
        ],
    }


def _service_for_response(payload: dict, seen: list[httpx.Request] | None = None):
    def handler(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        return httpx.Response(200, json=payload)

    return GoogleScholarService(API_KEY), httpx.MockTransport(handler)


def test_fetch_profile_sends_stored_id_and_normalizes_response():
    requests: list[httpx.Request] = []
    service, transport = _service_for_response(_serpapi_payload(), requests)

    result = service.fetch_profile(
        SCHOLAR_ID,
        scholar_url=f"https://scholar.google.com/citations?user={SCHOLAR_ID}",
        transport=transport,
    )

    assert requests[0].url.params["engine"] == "google_scholar_author"
    assert requests[0].url.params["author_id"] == SCHOLAR_ID
    assert requests[0].url.params["api_key"] == API_KEY
    assert requests[0].url.params["hl"] == "en"
    assert result["scholar_id"] == SCHOLAR_ID
    assert result["scholar_name"] == "Faculty Example"
    assert result["total_citations"] == 1234
    assert result["citations_since_2016"] == 900
    assert result["h_index"] == 24
    assert result["h_index_since_2016"] == 19
    assert result["i10_index"] == 57
    assert result["i10_index_since_2016"] == 42
    assert result["publications"] == [
        {
            "title": "A Research Paper",
            "authors": ["Faculty Example, Coauthor"],
            "publication": "Journal of Examples",
            "year": 2024,
            "citation_count": 12,
            "link": "https://example.test/paper",
            "citation_id": "citation-1",
        },
        {
            "title": "Older Paper",
            "authors": [],
            "publication": None,
            "year": 2010,
            "citation_count": None,
            "link": None,
            "citation_id": None,
        },
    ]
    assert result["source"] == "serpapi_google_scholar_author"
    assert result["retrieved_at"].endswith("Z")


def test_fetch_profile_validates_primary_search_parameter_author_id():
    service, transport = _service_for_response(_serpapi_payload())

    result = service.fetch_profile(SCHOLAR_ID, transport=transport)

    assert result["scholar_id"] == SCHOLAR_ID


def test_fetch_profile_validates_documented_author_url_without_search_parameter_id():
    payload = _serpapi_payload()
    payload.pop("search_parameters")
    service, transport = _service_for_response(payload)

    result = service.fetch_profile(SCHOLAR_ID, transport=transport)

    assert result["scholar_id"] == SCHOLAR_ID
    assert result["scholar_url"] == payload["search_metadata"]["google_scholar_author_url"]


def test_fetch_profile_supports_legacy_nested_author_id_fallback():
    payload = _serpapi_payload()
    payload.pop("search_parameters")
    payload.pop("search_metadata")
    payload["author"]["author_id"] = SCHOLAR_ID
    service, transport = _service_for_response(payload)

    result = service.fetch_profile(SCHOLAR_ID, transport=transport)

    assert result["scholar_id"] == SCHOLAR_ID


def test_fetch_profile_passes_configured_timeout_to_httpx(monkeypatch):
    real_client = httpx.Client
    captured = {}

    def client_factory(*, timeout, transport):
        captured["timeout"] = timeout
        return real_client(timeout=timeout, transport=transport)

    monkeypatch.setattr("app.services.google_scholar.httpx.Client", client_factory)
    service, transport = _service_for_response(_serpapi_payload())

    service.fetch_profile(SCHOLAR_ID, transport=transport)

    assert captured["timeout"] == 30.0


@pytest.mark.parametrize(
    ("api_key", "scholar_id", "category"),
    [("", SCHOLAR_ID, "missing_api_key"), (API_KEY, None, "missing_scholar_id")],
)
def test_fetch_profile_rejects_missing_configuration(api_key, scholar_id, category):
    with pytest.raises(GoogleScholarError) as raised:
        GoogleScholarService(api_key).fetch_profile(scholar_id)
    assert raised.value.category == category


def test_fetch_profile_sanitizes_timeout_and_http_errors():
    def timeout_handler(request):
        raise httpx.ReadTimeout(f"failed for key={API_KEY}", request=request)

    with pytest.raises(GoogleScholarError) as timeout:
        GoogleScholarService(API_KEY).fetch_profile(
            SCHOLAR_ID, transport=httpx.MockTransport(timeout_handler)
        )
    assert timeout.value.category == "provider_timeout"
    assert API_KEY not in str(timeout.value)

    error_transport = httpx.MockTransport(lambda request: httpx.Response(503))
    with pytest.raises(GoogleScholarError) as http_error:
        GoogleScholarService(API_KEY).fetch_profile(SCHOLAR_ID, transport=error_transport)
    assert http_error.value.category == "provider_http_error"
    assert API_KEY not in str(http_error.value)


@pytest.mark.parametrize(
    ("response", "category"),
    [
        (httpx.Response(200, content=b"not-json"), "invalid_provider_response"),
        (httpx.Response(200, json={"error": "credential rejected"}), "provider_error"),
        (httpx.Response(200, json={"articles": []}), "missing_author"),
    ],
)
def test_fetch_profile_rejects_invalid_provider_responses(response, category):
    transport = httpx.MockTransport(lambda request: response)
    with pytest.raises(GoogleScholarError) as raised:
        GoogleScholarService(API_KEY).fetch_profile(SCHOLAR_ID, transport=transport)
    assert raised.value.category == category
    assert API_KEY not in str(raised.value)


@pytest.mark.parametrize(
    ("payload", "category"),
    [
        ({"author": {"name": "No ID"}}, "identity_unverified"),
        (_serpapi_payload(author_id="DifferentScholarId"), "identity_unverified"),
        (
            {
                **_serpapi_payload(),
                "search_metadata": {
                    "google_scholar_author_url": (
                        "https://scholar.google.com/citations?user=DifferentScholarId"
                    )
                },
            },
            "identity_unverified",
        ),
        (
            {
                **_serpapi_payload(),
                "cited_by": {"table": [{"h_index": {"all": "not-a-number"}}]},
            },
            "malformed_citation_metrics",
        ),
    ],
)
def test_fetch_profile_rejects_unverified_identity_and_malformed_metrics(payload, category):
    service, transport = _service_for_response(payload)
    with pytest.raises(GoogleScholarError) as raised:
        service.fetch_profile(SCHOLAR_ID, transport=transport)
    assert raised.value.category == category


def test_fetch_profile_rejects_stored_scholar_id_mismatch():
    service, transport = _service_for_response(_serpapi_payload())

    with pytest.raises(GoogleScholarError) as raised:
        service.fetch_profile("DifferentStoredScholarId", transport=transport)

    assert raised.value.category == "identity_unverified"


def test_fetch_profile_rejects_stored_scholar_url_mismatch():
    service, transport = _service_for_response(_serpapi_payload())

    with pytest.raises(GoogleScholarError) as raised:
        service.fetch_profile(
            SCHOLAR_ID,
            scholar_url="https://scholar.google.com/citations?user=DifferentStoredScholarId",
            transport=transport,
        )

    assert raised.value.category == "identity_unverified"


def test_scholar_tool_authorizes_and_audits_without_exposing_api_key(db_session, monkeypatch):
    user = make_user(db_session, "scholar-tool@demo.local", ["faculty"])
    profile = make_faculty_profile(db_session, user, "SCHOLAR-TOOL")
    profile.google_scholar_id = SCHOLAR_ID
    db_session.commit()
    monkeypatch.setattr(
        "app.agents.tools.get_settings",
        lambda: SimpleNamespace(serpapi_api_key=API_KEY),
    )

    class FakeService:
        def __init__(self, api_key):
            assert api_key == API_KEY

        def fetch_profile(self, scholar_id, *, scholar_url=None):
            assert scholar_id == SCHOLAR_ID
            return {"scholar_id": scholar_id, "source": "serpapi_google_scholar_author"}

    monkeypatch.setattr("app.agents.tools.GoogleScholarService", FakeService)
    result = read_google_scholar_profile_tool(
        db_session, user, FacultyInput(faculty_id=profile.id)
    )
    assert result.data["scholar_id"] == SCHOLAR_ID
    assert API_KEY not in result.model_dump_json()
    success_audit = db_session.scalar(
        select(AuditLog).where(AuditLog.action == "tool_read_google_scholar_profile_success")
    )
    assert success_audit is not None
    assert API_KEY not in json.dumps(success_audit.after)

    class FailingService:
        def __init__(self, api_key):
            pass

        def fetch_profile(self, scholar_id, *, scholar_url=None):
            raise GoogleScholarError("provider_error")

    monkeypatch.setattr("app.agents.tools.GoogleScholarService", FailingService)
    with pytest.raises(ToolError) as raised:
        read_google_scholar_profile_tool(
            db_session, user, FacultyInput(faculty_id=profile.id)
        )
    assert API_KEY not in str(raised.value)
    failure_audit = db_session.scalar(
        select(AuditLog).where(AuditLog.action == "tool_read_google_scholar_profile_failure")
    )
    assert failure_audit is not None
    assert failure_audit.after["detail"] == "provider_error"
    assert API_KEY not in json.dumps(failure_audit.after)


def test_appraisal_automatically_retrieves_and_persists_scholar_snapshot(
    client, db_session, monkeypatch
):
    user = make_user(db_session, "automatic-scholar@demo.local", ["faculty"])
    profile = make_faculty_profile(db_session, user, "AUTO-SCHOLAR")
    profile.google_scholar_id = SCHOLAR_ID
    profile.google_scholar_url = f"https://scholar.google.com/citations?user={SCHOLAR_ID}"
    cycle = make_cycle(db_session)
    activity = create_activity(
        db_session,
        faculty=profile,
        category="research",
        activity_type="publications",
        title="Current appraisal research activity",
        description="",
        activity_date=None,
        extras={},
    )
    db_session.flush()
    _attach_valid_evidence(db_session, activity.id, profile.id, cycle.id, "AUTO-SCHOLAR")
    db_session.commit()

    class FakeService:
        def __init__(self, api_key):
            pass

        def fetch_profile(self, scholar_id, *, scholar_url=None):
            assert scholar_id == SCHOLAR_ID
            assert scholar_url == profile.google_scholar_url
            normalized = _serpapi_payload()
            service, transport = _service_for_response(normalized)
            return service.fetch_profile(scholar_id, scholar_url=scholar_url, transport=transport)

    monkeypatch.setattr("app.services.appraisals.GoogleScholarService", FakeService)
    monkeypatch.setattr(
        "app.services.appraisals.get_settings",
        lambda: SimpleNamespace(serpapi_api_key=API_KEY),
    )
    token = login(client, user.email)

    response = client.post("/api/v1/appraisals/run", headers=auth_headers(token))

    assert response.status_code == 200, response.text
    report = db_session.scalar(select(AppraisalReport))
    assert report is not None
    snapshot = report.report_json["research_metrics"]
    assert snapshot["status"] == "retrieved"
    assert snapshot["provider"] == "serpapi_google_scholar_author"
    assert snapshot["scholar_id"] == SCHOLAR_ID
    assert snapshot["scholar_url"] == profile.google_scholar_url
    assert snapshot["metrics"]["total_citations"] == 1234
    assert snapshot["metrics"]["h_index"] == 24
    assert snapshot["metrics"]["i10_index"] == 57
    assert snapshot["publications"][0]["year"] == 2024
    assert snapshot["publications"][0]["scoring_status"] == "outside_appraisal_year"
    assert snapshot["retrieved_at"].endswith("Z")
    assert snapshot["human_review_required"] is False
    assert response.json()["score"]["research_score"] == 16.0
    assert db_session.scalar(select(func.count(FacultyActivity.id))) == 1
    score_lines = report.report_json["score"]["line_items"]
    scholar_lines = [item for item in score_lines if item["source"] == "google_scholar"]
    assert scholar_lines
    assert scholar_lines[0]["provenance"]["scholar_id"] == SCHOLAR_ID
    assert "Google Scholar - H Index" in report.summary_md
    assert "Google Scholar - I10 Index" in report.summary_md
    assert API_KEY not in json.dumps(report.report_json)
    audit = db_session.scalar(
        select(AuditLog).where(AuditLog.action == "appraisal_research_metrics_success")
    )
    assert audit is not None
    assert audit.after["scholar_id"] == SCHOLAR_ID
    assert audit.after["success"] is True
    assert API_KEY not in json.dumps(audit.after)


def test_appraisal_provider_failure_is_visible_for_human_review(client, db_session, monkeypatch):
    user = make_user(db_session, "failed-scholar@demo.local", ["faculty"])
    profile = make_faculty_profile(db_session, user, "FAILED-SCHOLAR")
    profile.google_scholar_id = SCHOLAR_ID
    cycle = make_cycle(db_session)
    db_session.commit()

    class FailingService:
        def __init__(self, api_key):
            pass

        def fetch_profile(self, scholar_id, *, scholar_url=None):
            raise GoogleScholarError("identity_mismatch")

    monkeypatch.setattr("app.services.appraisals.GoogleScholarService", FailingService)
    monkeypatch.setattr(
        "app.services.appraisals.get_settings",
        lambda: SimpleNamespace(serpapi_api_key=API_KEY),
    )
    token = login(client, user.email)

    response = client.post("/api/v1/appraisals/run", headers=auth_headers(token))

    assert response.status_code == 200, response.text
    report = db_session.scalar(select(AppraisalReport))
    assert report is not None
    snapshot = report.report_json["research_metrics"]
    assert snapshot["status"] == "unavailable"
    assert snapshot["metrics"] is None
    assert snapshot["publications"] == []
    assert snapshot["error_category"] == "identity_mismatch"
    assert snapshot["human_review_required"] is True
    assert "require human review" in report.summary_md
    assert "identity_mismatch" in report.summary_md
    audit = db_session.scalar(
        select(AuditLog).where(AuditLog.action == "appraisal_research_metrics_failure")
    )
    assert audit is not None
    assert audit.after["error_category"] == "identity_mismatch"
    assert API_KEY not in json.dumps(audit.after)