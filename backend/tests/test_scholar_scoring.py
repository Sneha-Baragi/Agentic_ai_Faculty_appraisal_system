from app.scoring.engine import ActivityScoreInput, calculate_score, load_demo_rubric
from app.services.scoring_map import (
    appraisal_year_from_cycle,
    to_score_inputs,
    to_scholar_score_inputs,
)


SCHOLAR_ID = "ScholarId123"


def _snapshot(*, metrics=None, publications=None, status="retrieved", scholar_id=SCHOLAR_ID):
    return {
        "status": status,
        "provider": "serpapi_google_scholar_author",
        "scholar_id": scholar_id,
        "scholar_url": f"https://scholar.google.com/citations?user={scholar_id}",
        "retrieved_at": "2026-10-05T12:00:00Z",
        "human_review_required": status != "retrieved",
        "metrics": metrics or {},
        "publications": publications or [],
    }


def _score_scholar(snapshot, *, manual_activities=None, year=2026):
    rubric = load_demo_rubric()
    inputs, publications = to_scholar_score_inputs(
        snapshot,
        appraisal_year=year,
        expected_scholar_id=SCHOLAR_ID,
        cycle_id="cycle-1",
        manual_activities=manual_activities or [],
        rubric=rubric,
    )
    return calculate_score(inputs, rubric), inputs, publications


def test_demo_metric_bands_and_current_faculty_example():
    score, inputs, _ = _score_scholar(
        _snapshot(metrics={"h_index": 17, "i10_index": 21, "total_citations": 958})
    )

    points = {item.rubric_code: item.quantity for item in inputs}
    assert points == {
        "scholar_h_index": 10,
        "scholar_i10_index": 7,
        "scholar_total_citations": 8,
    }
    assert score.category_totals["research"] == 10.0
    assert all(item.source == "google_scholar" for item in score.line_items)
    assert score.line_items[0].provenance["scholar_id"] == SCHOLAR_ID
    assert score.line_items[0].provenance["retrieved_at"] == "2026-10-05T12:00:00Z"


def test_scholar_metric_band_boundaries_are_configured():
    for metric, value, expected in [
        ("h_index", 4, 0),
        ("h_index", 5, 5),
        ("h_index", 10, 8),
        ("h_index", 15, 10),
        ("h_index", 20, 12),
        ("i10_index", 9, 3),
        ("i10_index", 10, 5),
        ("i10_index", 20, 7),
        ("i10_index", 30, 8),
        ("total_citations", 99, 0),
        ("total_citations", 100, 3),
        ("total_citations", 250, 5),
        ("total_citations", 500, 8),
        ("total_citations", 1000, 10),
    ]:
        _score, inputs, _publications = _score_scholar(_snapshot(metrics={metric: value}))
        assert inputs[0].quantity == expected


def test_cycle_year_publication_scoring_and_unclassified_retention():
    snapshot = _snapshot(
        publications=[
            {"title": "Journal paper", "publication": "Journal of Examples", "year": 2026},
            {"title": "Conference paper", "publication": "Proceedings of Example Conference", "year": 2026},
            {"title": "Older paper", "publication": "Journal of Examples", "year": 2025},
            {"title": "Unknown venue", "publication": "Research Archive", "year": 2026},
        ]
    )

    score, inputs, publications = _score_scholar(snapshot)

    publication_inputs = [item for item in inputs if item.activity_id.startswith("scholar-publication:")]
    assert [item.rubric_code for item in publication_inputs] == ["journal_paper", "conference_paper"]
    assert [item.points for item in score.line_items] == [10.0, 5.0]
    assert [item["scoring_status"] for item in publications] == [
        "scored",
        "scored",
        "outside_appraisal_year",
        "unclassified",
    ]
    assert publications[3]["classification"] is None
    assert publication_inputs[0].label == "Google Scholar - Current-year journal paper"
    assert publication_inputs[0].provenance["publication_year"] == 2026
    assert appraisal_year_from_cycle("2027-2028 Academic Year") == 2027


def test_duplicate_scholar_publication_is_not_scored_twice():
    snapshot = _snapshot(
        publications=[
            {
                "title": "  A JOURNAL   PAPER! ",
                "publication": "Journal of Examples",
                "year": 2026,
                "citation_id": "citation-1",
            }
        ]
    )
    manual = [
        {
            "id": "manual-activity-1",
            "category": "research",
            "activity_type": "publications",
            "title": "A journal paper",
            "details": {"year": 2026},
        }
    ]

    _score, inputs, publications = _score_scholar(snapshot, manual_activities=manual)

    assert inputs == []
    assert publications[0]["scoring_status"] == "duplicate_of_manual_activity"


def test_duplicate_publications_inside_scholar_snapshot_score_once():
    snapshot = _snapshot(
        publications=[
            {"title": "Same paper", "publication": "Journal of Examples", "year": 2026, "citation_id": "id-1"},
            {"title": "Same paper", "publication": "Journal of Examples", "year": 2026, "citation_id": "id-2"},
        ]
    )

    _score, inputs, publications = _score_scholar(snapshot)

    assert len(inputs) == 1
    assert publications[0]["scoring_status"] == "scored"
    assert publications[1]["scoring_status"] == "duplicate_scholar_publication"


def test_scholar_metrics_are_not_scored_on_failure_or_identity_mismatch():
    failure_score, failure_inputs, _ = _score_scholar(
        _snapshot(metrics={"h_index": 17}, status="unavailable")
    )
    mismatch_score, mismatch_inputs, _ = _score_scholar(
        _snapshot(metrics={"h_index": 17}, scholar_id="DifferentScholarId")
    )

    assert failure_inputs == []
    assert mismatch_inputs == []
    assert failure_score.category_totals["research"] == 0
    assert mismatch_score.category_totals["research"] == 0


def test_manual_research_activity_codes_and_existing_weights_remain():
    activities = [
        {"id": "journal", "activity_type": "publications", "evidence_ids": ["e1"]},
        {"id": "conference", "activity_type": "conferences", "evidence_ids": ["e2"]},
        {"id": "project", "activity_type": "research_projects", "evidence_ids": ["e3"]},
        {"id": "patent", "activity_type": "patents", "evidence_ids": ["e4"]},
    ]

    result = calculate_score(to_score_inputs(activities))

    assert [item.rubric_code for item in result.line_items] == [
        "journal_paper",
        "conference_paper",
        "funded_project",
        "patent",
    ]
    assert result.category_totals["research"] == 20.0


def test_research_raw_score_cap_applies_before_existing_weight():
    activities = [
        ActivityScoreInput("journal", "research", "journal_paper", ("e1",), 4),
        ActivityScoreInput("conference", "research", "conference_paper", ("e2",), 4),
        ActivityScoreInput("project", "research", "funded_project", ("e3",), 2),
        ActivityScoreInput("patent", "research", "patent", ("e4",), 1),
    ]

    result = calculate_score(activities)

    assert result.category_raw_totals["research"] == 100
    assert result.category_totals["research"] == 40


def test_missing_scholar_metrics_and_other_category_scores_remain_safe():
    rubric = load_demo_rubric()
    result = calculate_score(
        [
            ActivityScoreInput("teaching", "teaching", "course_delivery", ("e1",), 12),
            ActivityScoreInput("admin", "administrative", "coordinator", ("e2",), 1),
        ],
        rubric,
    )
    _inputs, publications = to_scholar_score_inputs(
        _snapshot(metrics=None),
        appraisal_year=2026,
        expected_scholar_id=SCHOLAR_ID,
        cycle_id="cycle-1",
        manual_activities=[],
        rubric=rubric,
    )

    assert result.category_totals["teaching"] == 2.4
    assert result.category_totals["administrative"] == 2.0
    assert result.category_totals["research"] == 0
    assert publications == []