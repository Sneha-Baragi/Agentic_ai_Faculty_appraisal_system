from app.scoring.engine import (
    ENGINE_VERSION,
    ActivityScoreInput,
    ScoringError,
    calculate_score,
    load_demo_rubric,
)


def test_demo_rubric_is_labelled() -> None:
    rubric = load_demo_rubric()
    assert rubric["is_demo"] is True
    assert "DEMO/TEST" in rubric["disclaimer"]
    assert "NOT OFFICIAL UGC" in rubric["disclaimer"]


def test_golden_total_from_engine_only() -> None:
    activities = [
        ActivityScoreInput("a1", "research", "journal_paper", ("e1",), 2),
        ActivityScoreInput("a2", "teaching", "course_delivery", ("e2",), 20),
        ActivityScoreInput("a3", "administrative", "committee_role", ("e3",), 1),
    ]
    result = calculate_score(activities)
    assert result.engine_version == ENGINE_VERSION
    assert result.total == 13.6
    assert result.category_totals["research"] == 8.0
    assert result.category_totals["teaching"] == 4.0
    assert result.category_totals["administrative"] == 1.6
    assert result.rating_recommendation == "D"
    assert result.line_items[0].evidence_ids == ["e1"]
    assert result.is_demo is True


def test_item_cap_is_applied() -> None:
    activities = [
        ActivityScoreInput("p1", "research", "patent", ("e1",), 3),
    ]
    result = calculate_score(activities)
    # 3 * 20 = 60 raw, cap 20, weight 0.4 => 8.0
    assert result.total == 8.0
    assert result.category_totals["research"] == 8.0


def test_unknown_rubric_code_rejected() -> None:
    activities = [ActivityScoreInput("a1", "research", "invented_by_llm", ("e1",), 1)]
    try:
        calculate_score(activities)
        assert False, "expected ScoringError"
    except ScoringError as exc:
        assert "Unknown rubric code" in str(exc)


def test_missing_evidence_rejected() -> None:
    activities = [ActivityScoreInput("a1", "research", "journal_paper", tuple(), 1)]
    try:
        calculate_score(activities)
        assert False, "expected ScoringError"
    except ScoringError as exc:
        assert "no supporting evidence" in str(exc)


def test_engine_ignores_fabricated_total_by_not_accepting_one() -> None:
    result = calculate_score([])
    assert result.total == 0.0
    assert "total" not in ActivityScoreInput.__dataclass_fields__
