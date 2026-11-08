from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.graph import build_graph, checkpointed_graph
from app.models import (
    AppraisalReport,
    AppraisalScore,
    AuditLog,
    FacultyAppraisalRun,
)
from app.scoring.engine import (
    ActivityScoreInput,
    ScoringError,
    calculate_score,
    load_demo_rubric,
)
from app.services.scoring_map import to_student_feedback_score_input
from app.services.student_feedback import (
    DEFAULT_FEEDBACK_CSV_PATH,
    StudentFeedbackDataError,
    StudentFeedbackFileNotFoundError,
    calculate_student_feedback_points,
    get_student_feedback_record,
    load_student_feedback_csv,
    normalize_faculty_name,
)
from .conftest import auth_headers, login, make_cycle, make_faculty_profile, make_user


# =============================================================================
# 1. Real CSV Verification
# =============================================================================


def test_default_csv_exists_and_loads() -> None:
    assert DEFAULT_FEEDBACK_CSV_PATH.is_file(), f"CSV file not found at {DEFAULT_FEEDBACK_CSV_PATH}"
    records = load_student_feedback_csv()
    assert len(records) == 15

    # Check known sample records
    assert "dr. uday kulkarni" in records
    assert records["dr. uday kulkarni"].percentage == 92.0
    assert records["dr. uday kulkarni"].faculty_name == "Dr. Uday Kulkarni"

    assert "dr. ananya rao" in records
    assert records["dr. ananya rao"].percentage == 88.0

    assert "prof. rohan deshmukh" in records
    assert records["prof. rohan deshmukh"].percentage == 95.0


# =============================================================================
# 2. CSV Validation and Error Handling
# =============================================================================


def test_missing_csv_file_raises_error(tmp_path: Path) -> None:
    non_existent = tmp_path / "does_not_exist.csv"
    with pytest.raises(StudentFeedbackFileNotFoundError, match="not found"):
        load_student_feedback_csv(non_existent)


def test_empty_csv_raises_error(tmp_path: Path) -> None:
    empty_csv = tmp_path / "empty.csv"
    empty_csv.write_text("", encoding="utf-8")
    with pytest.raises(StudentFeedbackDataError, match="is empty"):
        load_student_feedback_csv(empty_csv)


def test_missing_headers_raises_error(tmp_path: Path) -> None:
    bad_csv = tmp_path / "bad_headers.csv"
    bad_csv.write_text("Name,Score\nDr. Someone,90\n", encoding="utf-8")
    with pytest.raises(StudentFeedbackDataError, match="missing required headers"):
        load_student_feedback_csv(bad_csv)


def test_malformed_row_raises_error(tmp_path: Path) -> None:
    bad_csv = tmp_path / "malformed.csv"
    bad_csv.write_text("Faculty Name,Feedback Percentage\nDr. Someone\n", encoding="utf-8")
    with pytest.raises(StudentFeedbackDataError, match="malformed row 2"):
        load_student_feedback_csv(bad_csv)


def test_empty_faculty_name_raises_error(tmp_path: Path) -> None:
    bad_csv = tmp_path / "empty_name.csv"
    bad_csv.write_text("Faculty Name,Feedback Percentage\n ,90\n", encoding="utf-8")
    with pytest.raises(StudentFeedbackDataError, match="empty Faculty Name at row 2"):
        load_student_feedback_csv(bad_csv)


def test_duplicate_faculty_name_raises_error(tmp_path: Path) -> None:
    bad_csv = tmp_path / "duplicate.csv"
    bad_csv.write_text(
        "Faculty Name,Feedback Percentage\n"
        "Dr. Uday Kulkarni,92\n"
        "  dr. uday kulkarni  ,88\n",
        encoding="utf-8",
    )
    with pytest.raises(StudentFeedbackDataError, match="Duplicate faculty name"):
        load_student_feedback_csv(bad_csv)


def test_non_numeric_percentage_raises_error(tmp_path: Path) -> None:
    bad_csv = tmp_path / "non_numeric.csv"
    bad_csv.write_text(
        "Faculty Name,Feedback Percentage\nDr. Someone,Excellent\n",
        encoding="utf-8",
    )
    with pytest.raises(StudentFeedbackDataError, match="Invalid numeric percentage"):
        load_student_feedback_csv(bad_csv)


@pytest.mark.parametrize("invalid_perc", [-1.0, -0.01, 100.1, 150.0])
def test_out_of_range_percentage_raises_error(tmp_path: Path, invalid_perc: float) -> None:
    bad_csv = tmp_path / "out_of_range.csv"
    bad_csv.write_text(
        f"Faculty Name,Feedback Percentage\nDr. Someone,{invalid_perc}\n",
        encoding="utf-8",
    )
    with pytest.raises(StudentFeedbackDataError, match="out of valid range"):
        load_student_feedback_csv(bad_csv)


# =============================================================================
# 3. Faculty Name Normalization and Two-Tier Matching
# =============================================================================


def test_name_normalization_variants() -> None:
    assert normalize_faculty_name("Dr. Uday Kulkarni") == "dr. uday kulkarni"
    assert normalize_faculty_name("  dr.   uday   kulkarni  ") == "dr. uday kulkarni"
    assert normalize_faculty_name("DR. UDAY KULKARNI") == "dr. uday kulkarni"
    assert normalize_faculty_name("Dr.Uday Kulkarni") == "dr. uday kulkarni"
    assert normalize_faculty_name("Prof.Rohan Deshmukh") == "prof. rohan deshmukh"
    assert normalize_faculty_name("Mr.Rajesh Sharma") == "mr. rajesh sharma"
    assert normalize_faculty_name("Mrs.Anita Desai") == "mrs. anita desai"
    assert normalize_faculty_name("Ms.Pooja Desai") == "ms. pooja desai"
    assert normalize_faculty_name("A.P.J. Abdul Kalam") == "a.p.j. abdul kalam"
    assert normalize_faculty_name("Uday K. Kulkarni") == "uday k. kulkarni"
    assert normalize_faculty_name("") == ""
    assert normalize_faculty_name(None) == ""


def test_tier1_exact_record_retrieval() -> None:
    rec = get_student_feedback_record("  Dr.   Uday   Kulkarni ")
    assert rec is not None
    assert rec["status"] == "matched"
    assert rec["faculty_name"] == "Dr. Uday Kulkarni"
    assert rec["feedback_percentage"] == 92.0
    assert rec["source_file"] == "synthetic_student_feedback.csv"


def test_tier2_matching_missing_honorific_in_profile() -> None:
    # When profile has no honorific, matches unambiguous CSV record
    rec_uday = get_student_feedback_record("Uday Kulkarni")
    assert rec_uday is not None
    assert rec_uday["status"] == "matched"
    assert rec_uday["faculty_name"] == "Dr. Uday Kulkarni"
    assert rec_uday["feedback_percentage"] == 92.0

    rec_rohan = get_student_feedback_record("Rohan Deshmukh")
    assert rec_rohan is not None
    assert rec_rohan["status"] == "matched"
    assert rec_rohan["faculty_name"] == "Prof. Rohan Deshmukh"
    assert rec_rohan["feedback_percentage"] == 95.0

    rec_ananya = get_student_feedback_record("Ananya Rao")
    assert rec_ananya is not None
    assert rec_ananya["status"] == "matched"
    assert rec_ananya["faculty_name"] == "Dr. Ananya Rao"
    assert rec_ananya["feedback_percentage"] == 88.0


def test_tier2_matching_with_punctuation_differences() -> None:
    # Punctuation difference within same honorific family (e.g. Dr vs Dr.) matches
    rec = get_student_feedback_record("Dr Uday Kulkarni")
    assert rec is not None
    assert rec["status"] == "matched"
    assert rec["faculty_name"] == "Dr. Uday Kulkarni"
    assert rec["feedback_percentage"] == 92.0

    rec_prof = get_student_feedback_record("Prof Rohan Deshmukh")
    assert rec_prof is not None
    assert rec_prof["status"] == "matched"
    assert rec_prof["faculty_name"] == "Prof. Rohan Deshmukh"
    assert rec_prof["feedback_percentage"] == 95.0


def test_tier2_different_explicit_honorific_rejected() -> None:
    # Prof. Uday Kulkarni must NOT match Dr. Uday Kulkarni
    rec_prof = get_student_feedback_record("Prof. Uday Kulkarni")
    assert rec_prof is not None
    assert rec_prof["status"] == "unmatched"
    assert rec_prof["feedback_percentage"] is None

    # Dr. Rohan Deshmukh must NOT match Prof. Rohan Deshmukh
    rec_dr = get_student_feedback_record("Dr. Rohan Deshmukh")
    assert rec_dr is not None
    assert rec_dr["status"] == "unmatched"
    assert rec_dr["feedback_percentage"] is None


def test_tier2_ambiguous_base_name_collision_fails_closed(tmp_path: Path) -> None:
    # If multiple CSV records share the same base name, base-name match is ambiguous
    collision_csv = tmp_path / "collision.csv"
    collision_csv.write_text(
        "Faculty Name,Feedback Percentage\n"
        "Dr. Rajesh Sharma,85\n"
        "Prof. Rajesh Sharma,90\n",
        encoding="utf-8",
    )

    # Missing honorific -> ambiguous collision -> reject match, award zero points
    rec_ambig = get_student_feedback_record("Rajesh Sharma", csv_path=collision_csv)
    assert rec_ambig is not None
    assert rec_ambig["status"] == "ambiguous_match"
    assert rec_ambig["feedback_percentage"] is None

    # Exact honorific match still resolves unambiguously via Tier 1
    rec_dr = get_student_feedback_record("Dr. Rajesh Sharma", csv_path=collision_csv)
    assert rec_dr is not None
    assert rec_dr["status"] == "matched"
    assert rec_dr["faculty_name"] == "Dr. Rajesh Sharma"
    assert rec_dr["feedback_percentage"] == 85.0

    rec_prof = get_student_feedback_record("Prof. Rajesh Sharma", csv_path=collision_csv)
    assert rec_prof is not None
    assert rec_prof["status"] == "matched"
    assert rec_prof["faculty_name"] == "Prof. Rajesh Sharma"
    assert rec_prof["feedback_percentage"] == 90.0

    # Incompatible explicit honorific
    rec_mr = get_student_feedback_record("Mr. Rajesh Sharma", csv_path=collision_csv)
    assert rec_mr is not None
    assert rec_mr["status"] == "unmatched"
    assert rec_mr["feedback_percentage"] is None


def test_live_profile_format_unspaced_honorific_matching() -> None:
    """Regression test for the exact live-profile format 'Dr.Uday Kulkarni'."""
    rec = get_student_feedback_record("Dr.Uday Kulkarni")
    assert rec is not None
    assert rec["status"] == "matched"
    assert rec["faculty_name"] == "Dr. Uday Kulkarni"
    assert rec["feedback_percentage"] == 92.0
    assert rec["source_file"] == "synthetic_student_feedback.csv"

    rec_prof = get_student_feedback_record("Prof.Rohan Deshmukh")
    assert rec_prof is not None
    assert rec_prof["status"] == "matched"
    assert rec_prof["faculty_name"] == "Prof. Rohan Deshmukh"
    assert rec_prof["feedback_percentage"] == 95.0


def test_honorific_spacing_and_punctuation_consistency() -> None:
    """Verify Dr.Uday Kulkarni, Dr. Uday Kulkarni, Dr Uday Kulkarni, and Uday Kulkarni resolve consistently."""
    unspaced = get_student_feedback_record("Dr.Uday Kulkarni")
    spaced = get_student_feedback_record("Dr. Uday Kulkarni")
    no_dot = get_student_feedback_record("Dr Uday Kulkarni")
    no_hon = get_student_feedback_record("Uday Kulkarni")

    for r in (unspaced, spaced, no_dot, no_hon):
        assert r is not None
        assert r["status"] == "matched"
        assert r["faculty_name"] == "Dr. Uday Kulkarni"
        assert r["feedback_percentage"] == 92.0


def test_unspaced_different_honorific_rejected() -> None:
    """Prof.Uday Kulkarni must NOT match Dr. Uday Kulkarni."""
    rec = get_student_feedback_record("Prof.Uday Kulkarni")
    assert rec is not None
    assert rec["status"] == "unmatched"
    assert rec["feedback_percentage"] is None

    rec_dr = get_student_feedback_record("Dr.Rohan Deshmukh")
    assert rec_dr is not None
    assert rec_dr["status"] == "unmatched"
    assert rec_dr["feedback_percentage"] is None


def test_unspaced_honorific_collision_safeguards(tmp_path: Path) -> None:
    """Collision rejection and safeguards remain robust with unspaced honorifics."""
    collision_csv = tmp_path / "collision.csv"
    collision_csv.write_text(
        "Faculty Name,Feedback Percentage\n"
        "Dr. Rajesh Sharma,85\n"
        "Prof. Rajesh Sharma,90\n",
        encoding="utf-8",
    )
    # Unspaced matching matches the correct honorific
    rec_dr = get_student_feedback_record("Dr.Rajesh Sharma", csv_path=collision_csv)
    assert rec_dr is not None
    assert rec_dr["status"] == "matched"
    assert rec_dr["faculty_name"] == "Dr. Rajesh Sharma"
    assert rec_dr["feedback_percentage"] == 85.0

    rec_prof = get_student_feedback_record("Prof.Rajesh Sharma", csv_path=collision_csv)
    assert rec_prof is not None
    assert rec_prof["status"] == "matched"
    assert rec_prof["faculty_name"] == "Prof. Rajesh Sharma"
    assert rec_prof["feedback_percentage"] == 90.0

    # Unspaced different honorific fails closed
    rec_mr = get_student_feedback_record("Mr.Rajesh Sharma", csv_path=collision_csv)
    assert rec_mr is not None
    assert rec_mr["status"] == "unmatched"
    assert rec_mr["feedback_percentage"] is None


def test_partial_name_never_matches() -> None:
    # Partial names must NOT match
    rec = get_student_feedback_record("Dr. Uday")
    assert rec is not None
    assert rec["status"] == "unmatched"
    assert rec["feedback_percentage"] is None

    rec2 = get_student_feedback_record("Kulkarni")
    assert rec2 is not None
    assert rec2["status"] == "unmatched"
    assert rec2["feedback_percentage"] is None

    rec3 = get_student_feedback_record("Uday")
    assert rec3 is not None
    assert rec3["status"] == "unmatched"
    assert rec3["feedback_percentage"] is None


def test_missing_faculty_name_handling() -> None:
    rec_none = get_student_feedback_record(None)
    assert rec_none is not None
    assert rec_none["status"] == "missing_faculty_name"
    assert rec_none["feedback_percentage"] is None

    rec_empty = get_student_feedback_record("   ")
    assert rec_empty is not None
    assert rec_empty["status"] == "missing_faculty_name"
    assert rec_empty["feedback_percentage"] is None


# =============================================================================
# 4. Scoring Formula, Rubric Capping, and Category Weighting
# =============================================================================


@pytest.mark.parametrize(
    ("percentage", "cap", "expected"),
    [
        (92.0, 10.0, 9.2),
        (88.0, 10.0, 8.8),
        (95.0, 10.0, 9.5),
        (100.0, 10.0, 10.0),
        (0.0, 10.0, 0.0),
        (50.0, 10.0, 5.0),
        (84.0, 20.0, 16.8),
    ],
)
def test_linear_points_conversion(percentage: float, cap: float, expected: float) -> None:
    assert calculate_student_feedback_points(percentage, cap) == expected


def test_scoring_engine_student_feedback_points_and_weighting() -> None:
    # 92% on cap 10 -> 9.2 raw points
    # Teaching weight is 0.4 -> 9.2 * 0.4 = 3.68 weighted points
    rubric = load_demo_rubric()
    assert rubric["categories"]["teaching"]["weight"] == 0.4
    assert rubric["categories"]["teaching"]["items"]["student_feedback"]["cap"] == 10

    feedback_input = ActivityScoreInput(
        activity_id="feedback:student_feedback",
        category="teaching",
        rubric_code="student_feedback",
        evidence_ids=(),
        quantity=9.2,
        source="student_feedback",
        label="Student Feedback",
        value="92%",
    )

    result = calculate_score([feedback_input], rubric)
    assert result.category_raw_totals["teaching"] == 9.2
    assert result.category_totals["teaching"] == 3.68
    assert result.total == 3.68
    assert len(result.line_items) == 1
    assert result.line_items[0].rubric_code == "student_feedback"
    assert result.line_items[0].points == 9.2
    assert result.line_items[0].source == "student_feedback"


def test_different_feedback_percentages_produce_different_scores() -> None:
    rubric = load_demo_rubric()

    rec_uday = get_student_feedback_record("Dr. Uday Kulkarni")  # 92%
    rec_ananya = get_student_feedback_record("Dr. Ananya Rao")   # 88%
    rec_rohan = get_student_feedback_record("Prof. Rohan Deshmukh")  # 95%

    input_uday = to_student_feedback_score_input(rec_uday, rubric)
    input_ananya = to_student_feedback_score_input(rec_ananya, rubric)
    input_rohan = to_student_feedback_score_input(rec_rohan, rubric)

    assert input_uday is not None
    assert input_ananya is not None
    assert input_rohan is not None

    res_uday = calculate_score([input_uday], rubric)
    res_ananya = calculate_score([input_ananya], rubric)
    res_rohan = calculate_score([input_rohan], rubric)

    # 92% -> 9.2 raw, 9.2 * 0.4 = 3.68
    assert res_uday.category_raw_totals["teaching"] == 9.2
    assert res_uday.category_totals["teaching"] == 3.68
    assert res_uday.total == 3.68

    # 88% -> 8.8 raw, 8.8 * 0.4 = 3.52
    assert res_ananya.category_raw_totals["teaching"] == 8.8
    assert res_ananya.category_totals["teaching"] == 3.52
    assert res_ananya.total == 3.52

    # 95% -> 9.5 raw, 9.5 * 0.4 = 3.8
    assert res_rohan.category_raw_totals["teaching"] == 9.5
    assert res_rohan.category_totals["teaching"] == 3.8
    assert res_rohan.total == 3.8

    assert res_uday.total != res_ananya.total != res_rohan.total


def test_feedback_combined_with_teaching_activities() -> None:
    rubric = load_demo_rubric()

    # Manual course delivery: 20 hours * 0.5 points/hr = 10.0 raw points
    course_input = ActivityScoreInput(
        activity_id="act-1",
        category="teaching",
        rubric_code="course_delivery",
        evidence_ids=("ev-1",),
        quantity=20.0,
        source="activity",
    )
    # Student feedback: 92% -> 9.2 raw points
    feedback_input = ActivityScoreInput(
        activity_id="feedback:student_feedback",
        category="teaching",
        rubric_code="student_feedback",
        evidence_ids=(),
        quantity=9.2,
        source="student_feedback",
    )

    result = calculate_score([course_input, feedback_input], rubric)
    # Total teaching raw: 10.0 + 9.2 = 19.2
    assert result.category_raw_totals["teaching"] == 19.2
    # Teaching weighted: 19.2 * 0.4 = 7.68
    assert result.category_totals["teaching"] == 7.68
    assert result.total == 7.68


def test_rubric_item_cap_enforcement() -> None:
    rubric = load_demo_rubric()
    # Quantity exceeds cap 10
    excessive_input = ActivityScoreInput(
        activity_id="feedback:excessive",
        category="teaching",
        rubric_code="student_feedback",
        evidence_ids=(),
        quantity=15.0,
        source="student_feedback",
    )
    result = calculate_score([excessive_input], rubric)
    # Capped at 10.0 raw points, weighted at 10.0 * 0.4 = 4.0
    assert result.category_raw_totals["teaching"] == 10.0
    assert result.category_totals["teaching"] == 4.0
    assert result.total == 4.0


def test_student_feedback_rejected_for_wrong_category() -> None:
    rubric = load_demo_rubric()
    bad_input = ActivityScoreInput(
        activity_id="feedback:wrong_cat",
        category="research",
        rubric_code="student_feedback",
        evidence_ids=(),
        quantity=9.2,
        source="student_feedback",
    )
    with pytest.raises(ScoringError, match="must belong to teaching"):
        calculate_score([bad_input], rubric)


def test_unmatched_feedback_produces_none_and_zero_score() -> None:
    rubric = load_demo_rubric()
    unmatched = get_student_feedback_record("Dr. NonExistent")
    assert unmatched["status"] == "unmatched"
    assert to_student_feedback_score_input(unmatched, rubric) is None


# =============================================================================
# 5. Graph Workflow Integration and Idempotency
# =============================================================================


def test_graph_api_calculation_includes_matched_student_feedback() -> None:
    graph = build_graph()
    initial_state = {
        "run_id": "r-fb-1",
        "faculty_id": "f-fb-1",
        "faculty_name": "Dr. Uday Kulkarni",
        "cycle_id": "c-fb-1",
        "rubric_id": "DEMO_RUBRIC_v1",
        "attempt": 0,
        "max_attempts": 3,
        "errors": [],
        "audit_events": [],
    }

    result = graph.invoke(initial_state)
    score_res = result.get("score_result")
    assert score_res is not None
    assert score_res["total"] == 3.68
    assert score_res["category_totals"]["teaching"] == 3.68
    assert score_res["category_raw_totals"]["teaching"] == 9.2

    line_items = score_res["line_items"]
    assert len(line_items) == 1
    assert line_items[0]["rubric_code"] == "student_feedback"
    assert line_items[0]["points"] == 9.2
    assert line_items[0]["source"] == "student_feedback"
    assert line_items[0]["value"] == "92%"

    feedback_state = result.get("student_feedback")
    assert feedback_state is not None
    assert feedback_state["status"] == "matched"
    assert feedback_state["feedback_percentage"] == 92.0


def test_graph_repeated_execution_is_idempotent() -> None:
    graph = build_graph()
    initial_state = {
        "run_id": "r-fb-idem",
        "faculty_id": "f-fb-idem",
        "faculty_name": "Dr. Ananya Rao",
        "cycle_id": "c-fb-idem",
        "rubric_id": "DEMO_RUBRIC_v1",
        "attempt": 0,
        "max_attempts": 3,
        "errors": [],
        "audit_events": [],
    }

    first_result = graph.invoke(initial_state)
    assert first_result["score_result"]["total"] == 3.52

    # Second execution using state output from first execution
    second_result = graph.invoke(first_result)
    assert second_result["score_result"]["total"] == 3.52
    assert second_result["score_result"]["category_totals"]["teaching"] == 3.52
    # Ensure line items did not accumulate
    assert len(second_result["score_result"]["line_items"]) == 1


# =============================================================================
# 6. Live Workflow Integration via FastAPI Endpoint
# =============================================================================


def test_live_appraisal_run_with_student_feedback(client, db_session: Session) -> None:
    user = make_user(db_session, "uday@demo.local", ["faculty"])
    profile = make_faculty_profile(db_session, user)
    profile.full_name = "Dr. Uday Kulkarni"
    db_session.flush()

    cycle = make_cycle(db_session)
    db_session.commit()

    token = login(client, user.email)
    response = client.post("/api/v1/appraisals/run", headers=auth_headers(token))
    assert response.status_code == 200, response.text
    data = response.json()

    assert data["approval_status"] == "awaiting_review"
    score_data = data["score"]
    assert score_data["total_score"] == 3.68
    assert score_data["teaching_score"] == 3.68

    line_items = score_data["score_breakdown"]["line_items"]
    assert any(
        item.get("rubric_code") == "student_feedback" and item.get("points") == 9.2
        for item in line_items
    )

    # Check report JSON
    report = db_session.scalar(
        select(AppraisalReport).where(AppraisalReport.id == data["report_id"])
    )
    assert report is not None
    assert report.report_json.get("student_feedback", {}).get("status") == "matched"
    assert report.report_json.get("student_feedback", {}).get("feedback_percentage") == 92.0

    # Check AuditLog
    audit = db_session.scalar(
        select(AuditLog).where(
            AuditLog.action == "appraisal_student_feedback_matched",
            AuditLog.entity_id == str(profile.id),
        )
    )
    assert audit is not None
    assert audit.after["feedback_percentage"] == 92.0
    assert audit.after["status"] == "matched"


def test_live_appraisal_run_with_unmatched_faculty(client, db_session: Session) -> None:
    user = make_user(db_session, "unknown@demo.local", ["faculty"])
    profile = make_faculty_profile(db_session, user)
    profile.full_name = "Dr. Unknown Faculty"
    db_session.flush()

    cycle = make_cycle(db_session)
    db_session.commit()

    token = login(client, user.email)
    response = client.post("/api/v1/appraisals/run", headers=auth_headers(token))
    assert response.status_code == 200, response.text
    data = response.json()

    score_data = data["score"]
    assert score_data["total_score"] == 0.0
    assert score_data["teaching_score"] == 0.0

    # Check AuditLog records unmatched
    audit = db_session.scalar(
        select(AuditLog).where(
            AuditLog.action == "appraisal_student_feedback_unmatched",
            AuditLog.entity_id == str(profile.id),
        )
    )
    assert audit is not None
    assert audit.after["status"] == "unmatched"
    assert audit.after["feedback_percentage"] is None
