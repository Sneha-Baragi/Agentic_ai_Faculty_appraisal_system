from __future__ import annotations

from datetime import datetime, timezone
from html import escape
from typing import Any

DEMO_DISCLAIMER = "DEMO/TEST WEIGHTAGES — NOT OFFICIAL UGC"


def build_report(*, profile: dict[str, Any], cycle: dict[str, Any], activities: list[dict], evidence: list[dict], score: dict[str, Any], approval: dict[str, Any] | None = None, research_metrics: dict[str, Any] | None = None, deep_research_verification: dict[str, Any] | None = None, student_feedback: dict[str, Any] | None = None, memory_context: dict[str, Any] | None = None) -> dict[str, Any]:
    research = [a for a in activities if a.get("category") == "research"]
    teaching = [a for a in activities if a.get("category") == "teaching"]
    admin = [a for a in activities if a.get("category") == "administrative"]
    payload = {
        "disclaimer": DEMO_DISCLAIMER,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "faculty": profile,
        "cycle": cycle,
        "research_activities": research,
        "teaching_activities": teaching,
        "administrative_activities": admin,
        "evidence_summary": [
            {
                "id": e.get("id"),
                "activity_id": e.get("activity_id"),
                "filename": e.get("original_filename"),
                "validation_status": e.get("validation_status"),
                "extraction_status": e.get("extraction_status"),
            }
            for e in evidence
        ],
        "score": {
            "total": score.get("total"),
            "rating": score.get("rating_recommendation"),
            "breakdown": score.get("category_totals"),
            "category_raw_totals": score.get("category_raw_totals"),
            "line_items": score.get("line_items", []),
            "engine_version": score.get("engine_version"),
            "is_demo": score.get("is_demo", True),
        },
        "approval_status": (approval or {}).get("status", "awaiting_review"),
        "approval": approval or {},
    }
    if research_metrics is not None:
        payload["research_metrics"] = research_metrics
    if deep_research_verification is not None:
        payload["deep_research_verification"] = deep_research_verification
    if student_feedback is not None:
        payload["student_feedback"] = student_feedback
    if memory_context is not None:
        payload["memory_context"] = memory_context
        payload["historical_memory"] = memory_context
    html = _to_html(payload)
    return {"json": payload, "html": html, "markdown": _to_markdown(payload)}


def update_report_approval(report, *, status: str, reviewer: str, decided_at: datetime, reason: str | None = None, comment: str | None = None) -> None:
    payload = dict(report.report_json or {})
    payload["approval_status"] = status
    payload["approval"] = {
        "status": status,
        "reviewer": reviewer,
        "decided_at": decided_at.isoformat(),
        "reason": reason,
        "comment": comment,
    }
    report.report_json = payload
    report.summary_md = _to_html(payload)


def _to_markdown(payload: dict[str, Any]) -> str:
    score = payload["score"]
    lines = [
    f"# Appraisal report — {payload['faculty'].get('full_name') or payload['faculty'].get('email')}",
    f"**Cycle:** {payload['cycle'].get('name')} ({payload['cycle'].get('academic_year')})",
    f"**Disclaimer:** {payload['disclaimer']}",
    f"**DEMO total score:** {score.get('total')} / 100 ({score.get('rating')})",
    f"- Research: {(score.get('breakdown') or {}).get('research')} pts weighted ({(score.get('category_raw_totals') or {}).get('research', 'N/A')} raw pts x 40% weight)",
    f"- Teaching: {(score.get('breakdown') or {}).get('teaching')} pts weighted ({(score.get('category_raw_totals') or {}).get('teaching', 'N/A')} raw pts x 40% weight)",
    f"- Administrative: {(score.get('breakdown') or {}).get('administrative')} pts weighted ({(score.get('category_raw_totals') or {}).get('administrative', 'N/A')} raw pts x 20% weight)",
    f"Activities: {len(payload['research_activities'])} research, {len(payload['teaching_activities'])} teaching, {len(payload['administrative_activities'])} administrative",
    f"Evidence files: {len(payload['evidence_summary'])}",
    ]
    line_items = score.get("line_items") or []
    if line_items:
        lines.extend(["", "## Detailed Score Line Items (Reconciled with Category Totals):"])
        for item in line_items:
            label = item.get("label") or item.get("rubric_code")
            value = item.get("value")
            raw_pts = item.get("points")
            wt = item.get("category_weight")
            weighted_pts = item.get("weighted_points")
            calc = f" -> {weighted_pts:.2f} weighted contribution (wt {int(wt*100)}%)" if wt is not None and weighted_pts is not None else ""
            lines.append(f"- {label}{f': {value}' if value is not None else ''}: {raw_pts} raw pts{calc}")
    mem = payload.get("memory_context") or payload.get("historical_memory")
    lines.extend(["", "## Historical Performance (Previous Cycles)"])
    prev_scores = (mem.get("previous_scores") or []) if isinstance(mem, dict) else []
    if prev_scores:
        for idx, item in enumerate(prev_scores, 1):
            if not isinstance(item, dict):
                continue
            cycle_ref = item.get("cycle_id") or f"Cycle #{idx}"
            total_val = item.get("total")
            total_str = f"{total_val}" if total_val is not None else "N/A"
            bk = item.get("breakdown") or {}
            res_pts = bk.get("research_score", bk.get("research", "N/A"))
            teach_pts = bk.get("teaching_score", bk.get("teaching", "N/A"))
            admin_pts = bk.get("administrative_score", bk.get("administrative", "N/A"))
            computed_date = item.get("computed_at") or ""
            date_str = f" ({computed_date[:10]})" if len(computed_date) >= 10 else ""
            lines.append(f"- Previous Cycle ({cycle_ref}){date_str}: Total {total_str} pts")
            lines.append(f"  * Research: {res_pts}, Teaching: {teach_pts}, Administrative: {admin_pts}")
    else:
        lines.append("No prior appraisal cycle records found.")
    return "\n".join(lines)


def _to_html(payload: dict[str, Any]) -> str:
    score = payload["score"]
    breakdown = score.get("breakdown") or {}
    research_metrics = payload.get("research_metrics") or {}
    research_metrics_notice = ""
    if research_metrics.get("status") == "unavailable":
        issue_escaped = escape(str(research_metrics.get('error_category', 'unavailable')))
        research_metrics_notice = (
            "<p><strong>Google Scholar metrics could not be verified. "
            "Research metrics require human review. "
            f"Issue: {issue_escaped}.</strong></p>"
        )
    line_items = score.get("line_items") or []
    score_lines_html = ""
    if line_items:
        rendered_items = []
        for item in line_items:
            label = escape(str(item.get("label") or item.get("rubric_code") or "Score item"))
            value = item.get("value")
            value_html = f" — {escape(str(value))}" if value is not None else ""
            raw_pts = item.get("points", 0)
            wt = item.get("category_weight")
            weighted_pts = item.get("weighted_points")
            if wt is not None and weighted_pts is not None:
                contrib_html = f" &mdash; <strong>{raw_pts} raw pts</strong> &times; {int(wt*100)}% wt &rarr; <strong>+{weighted_pts:.2f} weighted pts</strong>"
            else:
                contrib_html = f": {raw_pts} raw pts"
            rendered_items.append(
                f"<li>{label}{value_html}{contrib_html}</li>"
            )
        score_lines_html = "<h2>Score line items</h2><ul>" + "".join(rendered_items) + "</ul>"

    mem = payload.get("memory_context") or payload.get("historical_memory")
    prev_scores = (mem.get("previous_scores") or []) if isinstance(mem, dict) else []
    if prev_scores:
        rendered_history = []
        for idx, item in enumerate(prev_scores, 1):
            if not isinstance(item, dict):
                continue
            cycle_ref = escape(str(item.get("cycle_id") or f"Cycle #{idx}"))
            total_val = item.get("total")
            total_str = escape(str(total_val)) if total_val is not None else "N/A"
            bk = item.get("breakdown") or {}
            res_pts = escape(str(bk.get("research_score", bk.get("research", "N/A"))))
            teach_pts = escape(str(bk.get("teaching_score", bk.get("teaching", "N/A"))))
            admin_pts = escape(str(bk.get("administrative_score", bk.get("administrative", "N/A"))))
            computed_date = item.get("computed_at") or ""
            date_str = f" ({escape(computed_date[:10])})" if len(computed_date) >= 10 else ""
            rendered_history.append(
                f"<li><strong>Previous Cycle ({cycle_ref}){date_str}:</strong> Total {total_str} pts"
                f"<ul><li>Research: {res_pts}</li><li>Teaching: {teach_pts}</li><li>Administrative: {admin_pts}</li></ul></li>"
            )
        historical_html = "<h2>Historical Performance (Previous Cycles)</h2><ul>" + "".join(rendered_history) + "</ul>"
    else:
        historical_html = "<h2>Historical Performance (Previous Cycles)</h2><p>No prior appraisal cycle records found.</p>"

    faculty_info = payload.get("faculty") or {}
    faculty_name = escape(str(faculty_info.get("full_name") or "Unnamed Faculty"))
    faculty_email = escape(str(faculty_info.get("email") or "No Email"))
    cycle_info = payload.get("cycle") or {}
    cycle_name = escape(str(cycle_info.get("name") or "Appraisal Cycle"))
    cycle_year = escape(str(cycle_info.get("academic_year") or ""))
    disclaimer_text = escape(str(payload.get("disclaimer") or DEMO_DISCLAIMER))
    approval_data = payload.get("approval") or {}
    reviewer_text = escape(str(approval_data.get("reviewer") or ""))
    decided_at_text = escape(str(approval_data.get("decided_at") or ""))
    reason_text = escape(str(approval_data.get("reason") or ""))
    comment_text = escape(str(approval_data.get("comment") or ""))

    return f"""<!DOCTYPE html>
<html><body>
<h1>Faculty Appraisal Report</h1>
{research_metrics_notice}
<p><strong>{disclaimer_text}</strong></p>
<p>Faculty: {faculty_name} ({faculty_email})</p>
<p>Cycle: {cycle_name} — {cycle_year}</p>
<p>DEMO total: {escape(str(score.get('total')))} — {"Final Rating" if payload.get('approval_status') in {"approved", "published"} else "Recommended Rating"}: {escape(str(score.get('rating')))}</p>
<ul>
<li>Research: {escape(str(breakdown.get('research')))}</li>
<li>Teaching: {escape(str(breakdown.get('teaching')))}</li>
<li>Administrative: {escape(str(breakdown.get('administrative')))}</li>
</ul>
<p>Evidence files: {len(payload.get('evidence_summary', []))}</p>
{score_lines_html}
{historical_html}
<p>Approval status: {escape(str(payload.get('approval_status')))}</p>
{f"<p>Reviewed by: {reviewer_text}</p>" if approval_data.get('reviewer') else ""}
{f"<p>Reviewed on: {decided_at_text}</p>" if approval_data.get('decided_at') else ""}
{f"<p>Reason: {reason_text}</p>" if approval_data.get('reason') else ""}
{f"<p>Comment: {comment_text}</p>" if approval_data.get('comment') else ""}
</body></html>"""
