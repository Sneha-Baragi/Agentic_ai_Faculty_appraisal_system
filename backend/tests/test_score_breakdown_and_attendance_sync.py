import os
import sys
from datetime import date, datetime, time, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.models import (
    AppraisalCycle,
    AttendanceRecord,
    Evidence,
    FacultyActivity,
    FacultyProfile,
    TeachingActivity,
    TeachingRequirement,
    TimetableEntry,
    User,
)
from app.scoring.engine import (
    ActivityScoreInput,
    calculate_score,
    load_demo_rubric,
)
from app.services.attendance import sync_attendance_to_course_delivery, get_or_create_run
from app.services.reports import _to_html, _to_markdown
from tests.conftest import make_cycle, make_faculty_profile, make_user


def test_scoring_engine_enriched_line_items_and_category_weights():
    activities = [
        ActivityScoreInput("a1", "research", "journal_paper", ("e1",), 2),
        ActivityScoreInput("a2", "teaching", "course_delivery", ("e2",), 20),
        ActivityScoreInput("a3", "administrative", "committee_role", ("e3",), 1),
    ]
    result = calculate_score(activities)

    # Check category weights are present in result
    assert result.category_weights == {"research": 0.4, "teaching": 0.4, "administrative": 0.2}

    # Check line items have category, category_weight, weighted_points, and cap
    for item in result.line_items:
        assert item.category in {"research", "teaching", "administrative"}
        assert item.category_weight == result.category_weights[item.category]
        assert item.weighted_points == round(item.points * item.category_weight, 4)
        assert item.cap is not None
        assert item.status in {"scored", "capped"}

    # Mathematical reconciliation
    for cat, weight in result.category_weights.items():
        assert result.category_totals[cat] == round(result.category_raw_totals[cat] * weight, 4)

    assert result.total == round(sum(result.category_totals.values()), 4)


def test_golden_kulkarni_scoring_reconciliation():
    """
    Test Dr. Kulkarni's baseline:
    Research: H-index 18 (10 raw), i10-index 21 (7 raw), citations 972 (8 raw) -> 25 raw pts
    Teaching: Course delivery 12 hrs (6 raw), Student feedback 92% (9.2 raw) -> 15.2 raw pts
    Administrative: Coordinator 1 role (10 raw) -> 10 raw pts
    """
    activities = [
        # Administrative
        ActivityScoreInput(
            "admin-coord", "administrative", "coordinator", ("e_coord",), 1,
            label="Department Coordinator", source="activity"
        ),
        # Teaching
        ActivityScoreInput(
            "teach-deliv", "teaching", "course_delivery", ("e_teach",), 12,
            label="Course Delivery (CSAI101)", source="activity"
        ),
        ActivityScoreInput(
            "teach-fb", "teaching", "student_feedback", ("e_fb",), 9.2,
            label="Student Feedback (92%)", source="student_feedback"
        ),
        # Research
        ActivityScoreInput(
            "scholar:h_index", "research", "scholar_h_index", (), 10,
            label="Google Scholar - H Index", source="google_scholar"
        ),
        ActivityScoreInput(
            "scholar:i10_index", "research", "scholar_i10_index", (), 7,
            label="Google Scholar - I10 Index", source="google_scholar"
        ),
        ActivityScoreInput(
            "scholar:total_citations", "research", "scholar_total_citations", (), 8,
            label="Google Scholar - Total Citations", source="google_scholar"
        ),
    ]

    result = calculate_score(activities)

    # Verify category raw subtotals
    assert result.category_raw_totals["research"] == 25.0
    assert result.category_raw_totals["teaching"] == 15.2
    assert result.category_raw_totals["administrative"] == 10.0

    # Verify category weighted totals
    assert result.category_totals["research"] == 10.00
    assert result.category_totals["teaching"] == 6.08
    assert result.category_totals["administrative"] == 2.00

    # Total score
    assert result.total == 18.08
    assert result.rating_recommendation == "D"

    # Line item reconciliation
    line_item_weighted_sum = sum(item.weighted_points for item in result.line_items)
    assert round(line_item_weighted_sum, 4) == 18.08

    # Check each line item's raw vs weighted
    items_by_code = {it.rubric_code: it for it in result.line_items}
    assert items_by_code["coordinator"].points == 10.0
    assert items_by_code["coordinator"].weighted_points == 2.00  # 10 * 0.20

    assert items_by_code["course_delivery"].points == 6.0
    assert items_by_code["course_delivery"].weighted_points == 2.40  # 6 * 0.40

    assert items_by_code["student_feedback"].points == 9.2
    assert items_by_code["student_feedback"].weighted_points == 3.68  # 9.2 * 0.40

    assert items_by_code["scholar_h_index"].points == 10.0
    assert items_by_code["scholar_h_index"].weighted_points == 4.00  # 10 * 0.40

    assert items_by_code["scholar_i10_index"].points == 7.0
    assert items_by_code["scholar_i10_index"].weighted_points == 2.80  # 7 * 0.40

    assert items_by_code["scholar_total_citations"].points == 8.0
    assert items_by_code["scholar_total_citations"].weighted_points == 3.20  # 8 * 0.40


def test_reports_show_raw_and_weighted_points():
    activities = [
        ActivityScoreInput("a1", "research", "journal_paper", ("e1",), 2, label="Research Paper"),
        ActivityScoreInput("a2", "teaching", "course_delivery", ("e2",), 10, label="Lectures"),
        ActivityScoreInput("a3", "administrative", "coordinator", ("e3",), 1, label="Coordinator"),
    ]
    score = calculate_score(activities)
    faculty_dict = {"full_name": "Test Faculty", "department": "CS", "employee_code": "F001"}
    cycle_dict = {"name": "2026-2027", "academic_year": "2026-2027"}

    payload = {
        "faculty": faculty_dict,
        "cycle": cycle_dict,
        "score": score.to_dict(),
        "disclaimer": "test disclaimer",
        "activities": [],
        "research_activities": [],
        "teaching_activities": [],
        "administrative_activities": [],
        "evidence_summary": [],
        "research_metrics": {},
    }
    md = _to_markdown(payload)
    assert "raw pts" in md
    assert "weighted" in md
    assert "weight" in md

    html = _to_html(payload)
    assert "raw pts" in html
    assert "weighted pts" in html
    assert "wt" in html


def test_attendance_sync_rules_and_idempotency(db_session: Session):
    user = make_user(db_session, "prof_test@uni.edu", ["faculty"])
    faculty = make_faculty_profile(db_session, user)
    cycle = make_cycle(db_session)

    # Create Timetable entries
    tt1 = TimetableEntry(
        faculty_id=faculty.id,
        course_code="CSAI103",
        section="A",
        day_of_week="Monday",
        start_time=time(10, 0),
        end_time=time(11, 0),
    )
    tt2 = TimetableEntry(
        faculty_id=faculty.id,
        course_code="CSAI104",
        section="B",
        day_of_week="Wednesday",
        start_time=time(14, 0),
        end_time=time(15, 0),
    )
    db_session.add_all([tt1, tt2])
    db_session.flush()

    # Add attendance records:
    # 1. Present in cycle
    att1 = AttendanceRecord(
        faculty_id=faculty.id,
        timetable_entry_id=tt1.id,
        attended_at=datetime(2026, 3, 2, 10, 0, tzinfo=timezone.utc),
        status="present",
    )
    # 2. Present in cycle
    att2 = AttendanceRecord(
        faculty_id=faculty.id,
        timetable_entry_id=tt2.id,
        attended_at=datetime(2026, 3, 4, 14, 0, tzinfo=timezone.utc),
        status="present",
    )
    # 3. Absent in cycle -> MUST NOT earn points
    att3 = AttendanceRecord(
        faculty_id=faculty.id,
        timetable_entry_id=tt1.id,
        attended_at=datetime(2026, 3, 9, 10, 0, tzinfo=timezone.utc),
        status="absent",
    )
    # 4. Out of cycle date -> MUST NOT earn points
    att4 = AttendanceRecord(
        faculty_id=faculty.id,
        timetable_entry_id=tt1.id,
        attended_at=datetime(2025, 12, 15, 10, 0, tzinfo=timezone.utc),
        status="present",
    )
    # 5. Duplicate attendance on same day for same entry -> MUST NOT be counted twice
    att5 = AttendanceRecord(
        faculty_id=faculty.id,
        timetable_entry_id=tt1.id,
        attended_at=datetime(2026, 3, 2, 10, 30, tzinfo=timezone.utc),
        status="present",
    )
    db_session.add_all([att1, att2, att3, att4, att5])
    db_session.commit()

    # First sync
    res1 = sync_attendance_to_course_delivery(db_session, faculty.id, cycle.id)
    assert res1["status"] == "success"
    # Exactly 2 unique present sessions inside the 2026 cycle (1 hr each = 2.0 hrs)
    assert res1["synchronized_hours"] == 2.0
    assert res1["records_processed"] == 2

    # Verify Activities created in database
    sync_act = db_session.query(FacultyActivity).filter(FacultyActivity.id == res1["activity_id"]).first()
    assert sync_act is not None
    assert sync_act.category == "teaching"
    assert sync_act.activity_type == "courses_taught"

    sync_acts = db_session.query(FacultyActivity).filter(
        FacultyActivity.faculty_id == faculty.id,
        FacultyActivity.category == "teaching",
        FacultyActivity.activity_type == "courses_taught",
    ).all()
    # 2 distinct courses CSAI103 and CSAI104, total 2.0 hours
    assert len(sync_acts) == 2
    assert sum(a.teaching.hours for a in sync_acts) == 2.0

    # Verify Evidence was created and attached
    ev = db_session.query(Evidence).filter(Evidence.activity_id == sync_act.id).first()
    assert ev is not None
    assert ev.validation_status == "valid"

    # Second sync (Idempotency test)
    res2 = sync_attendance_to_course_delivery(db_session, faculty.id, cycle.id)
    assert res2["status"] == "success"
    assert res2["synchronized_hours"] == 2.0
    # No duplicate activities created
    sync_acts_after = db_session.query(FacultyActivity).filter(
        FacultyActivity.faculty_id == faculty.id,
        FacultyActivity.category == "teaching",
        FacultyActivity.activity_type == "courses_taught",
    ).all()
    assert len(sync_acts_after) == 2
    assert sum(a.teaching.hours for a in sync_acts_after) == 2.0


def test_attendance_sync_double_counting_protection_with_manual_course(db_session: Session):
    user = make_user(db_session, "prof_double@uni.edu", ["faculty"])
    faculty = make_faculty_profile(db_session, user)
    cycle = make_cycle(db_session)

    run = get_or_create_run(db_session, faculty=faculty, cycle=cycle)
    # Faculty manually logged course CSAI101
    manual_act = FacultyActivity(
        run_id=run.id,
        faculty_id=faculty.id,
        cycle_id=cycle.id,
        category="teaching",
        activity_type="course_delivery",
        title="Course Delivery: CSAI101 Lectures",
    )
    db_session.add(manual_act)
    db_session.flush()

    teach_sub = TeachingActivity(
        activity_id=manual_act.id,
        course_code="CSAI101",
        hours=12.0,
    )
    db_session.add(teach_sub)
    db_session.flush()

    # Add evidence for manual activity
    manual_ev = Evidence(
        faculty_id=faculty.id,
        activity_id=manual_act.id,
        cycle_id=cycle.id,
        original_filename="csai101_log.pdf",
        mime="application/pdf",
        file_size=1024,
        checksum_sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        kind="pdf",
        validation_status="valid",
    )
    db_session.add(manual_ev)
    db_session.flush()

    # Now add attendance records:
    # 1 session of CSAI101 (already reported manually)
    # 1 session of CSAI105 (not reported manually)
    tt_manual = TimetableEntry(
        faculty_id=faculty.id,
        course_code="CSAI101",
        section="A",
        day_of_week="Tuesday",
        start_time=time(9, 0),
        end_time=time(10, 0),
    )
    tt_new = TimetableEntry(
        faculty_id=faculty.id,
        course_code="CSAI105",
        section="A",
        day_of_week="Thursday",
        start_time=time(11, 0),
        end_time=time(12, 0),
    )
    db_session.add_all([tt_manual, tt_new])
    db_session.flush()

    att_manual = AttendanceRecord(
        faculty_id=faculty.id,
        timetable_entry_id=tt_manual.id,
        attended_at=datetime(2026, 4, 7, 9, 0, tzinfo=timezone.utc),
        status="present",
    )
    att_new = AttendanceRecord(
        faculty_id=faculty.id,
        timetable_entry_id=tt_new.id,
        attended_at=datetime(2026, 4, 9, 11, 0, tzinfo=timezone.utc),
        status="present",
    )
    db_session.add_all([att_manual, att_new])
    db_session.commit()

    res = sync_attendance_to_course_delivery(db_session, faculty.id, cycle.id)
    # CSAI101 must be skipped to avoid double counting; only CSAI105 should be synced (1.0 hr)
    assert res["synchronized_hours"] == 1.0
    assert res["records_processed"] == 1
    assert any(c["course_code"] == "CSAI101" for c in res["skipped_courses"])


def test_attendance_sync_faculty_isolation(db_session: Session):
    user_a = make_user(db_session, "prof_a@uni.edu", ["faculty"])
    user_b = make_user(db_session, "prof_b@uni.edu", ["faculty"])
    fac_a = make_faculty_profile(db_session, user_a, employee_code="FA-01")
    fac_b = make_faculty_profile(db_session, user_b, employee_code="FB-02")
    cycle = make_cycle(db_session)

    tt_a = TimetableEntry(
        faculty_id=fac_a.id, course_code="A101", section="A", day_of_week="Monday",
        start_time=time(10, 0), end_time=time(11, 0),
    )
    tt_b = TimetableEntry(
        faculty_id=fac_b.id, course_code="B101", section="B", day_of_week="Monday",
        start_time=time(10, 0), end_time=time(11, 0),
    )
    db_session.add_all([tt_a, tt_b])
    db_session.flush()

    db_session.add(AttendanceRecord(
        faculty_id=fac_a.id, timetable_entry_id=tt_a.id,
        attended_at=datetime(2026, 5, 4, 10, 0, tzinfo=timezone.utc), status="present",
    ))
    db_session.add(AttendanceRecord(
        faculty_id=fac_b.id, timetable_entry_id=tt_b.id,
        attended_at=datetime(2026, 5, 4, 10, 0, tzinfo=timezone.utc), status="present",
    ))
    db_session.commit()

    res_a = sync_attendance_to_course_delivery(db_session, fac_a.id, cycle.id)
    assert res_a["synchronized_hours"] == 1.0

    # Ensure fac_b has no synced activities yet
    acts_b = db_session.query(FacultyActivity).filter(FacultyActivity.faculty_id == fac_b.id).all()
    assert len(acts_b) == 0


def test_attendance_sync_api_endpoint(client, db_session: Session):
    user = make_user(db_session, "api_fac@uni.edu", ["faculty"])
    faculty = make_faculty_profile(db_session, user)
    cycle = make_cycle(db_session)

    token = create_access_token(subject=str(user.id), roles=[r.name for r in user.roles])
    headers = {"Authorization": f"Bearer {token}"}

    # Add a timetable entry and attendance record
    tt = TimetableEntry(
        faculty_id=faculty.id, course_code="CS500", section="A", day_of_week="Tuesday",
        start_time=time(10, 0), end_time=time(11, 0),
    )
    db_session.add(tt)
    db_session.flush()
    db_session.add(AttendanceRecord(
        faculty_id=faculty.id, timetable_entry_id=tt.id,
        attended_at=datetime(2026, 6, 2, 10, 0, tzinfo=timezone.utc), status="present",
    ))
    db_session.commit()

    resp = client.post("/api/v1/attendance/sync", json={"cycle_id": str(cycle.id)}, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["synchronized_hours"] == 1.0
    assert data["records_processed"] == 1
