from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

DEMO_DISCLAIMER = "DEMO/TEST WEIGHTAGES — NOT OFFICIAL UGC"


def build_report(*, profile: dict[str, Any], cycle: dict[str, Any], activities: list[dict], evidence: list[dict], score: dict[str, Any], approval: dict[str, Any] | None = None) -> dict[str, Any]:
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
            "engine_version": score.get("engine_version"),
            "is_demo": score.get("is_demo", True),
        },
        "approval_status": (approval or {}).get("status", "awaiting_review"),
        "approval": approval or {},
    }
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
    return "\n".join(
        [
            f"# Appraisal report — {payload['faculty'].get('full_name') or payload['faculty'].get('email')}",
            f"**Cycle:** {payload['cycle'].get('name')} ({payload['cycle'].get('academic_year')})",
            f"**Disclaimer:** {payload['disclaimer']}",
            f"**DEMO total:** {score.get('total')} ({score.get('rating')})",
            f"- Research: { (score.get('breakdown') or {}).get('research') }",
            f"- Teaching: { (score.get('breakdown') or {}).get('teaching') }",
            f"- Administrative: { (score.get('breakdown') or {}).get('administrative') }",
            f"Activities: {len(payload['research_activities'])} research, {len(payload['teaching_activities'])} teaching, {len(payload['administrative_activities'])} administrative",
            f"Evidence files: {len(payload['evidence_summary'])}",
        ]
    )


def _to_html(payload: dict[str, Any]) -> str:
    score = payload["score"]
    breakdown = score.get("breakdown") or {}
    return f"""<!DOCTYPE html>
<html><body>
<h1>Faculty Appraisal Report</h1>
<p><strong>{payload['disclaimer']}</strong></p>
<p>Faculty: {payload['faculty'].get('full_name')} ({payload['faculty'].get('email')})</p>
<p>Cycle: {payload['cycle'].get('name')} — {payload['cycle'].get('academic_year')}</p>
<p>DEMO total: {score.get('total')} — {"Final Rating" if payload['approval_status'] in {"approved", "published"} else "Recommended Rating"}: {score.get('rating')}</p>
<ul>
<li>Research: {breakdown.get('research')}</li>
<li>Teaching: {breakdown.get('teaching')}</li>
<li>Administrative: {breakdown.get('administrative')}</li>
</ul>
<p>Evidence files: {len(payload['evidence_summary'])}</p>
<p>Approval status: {payload['approval_status']}</p>
{f"<p>Reviewed by: {payload.get('approval', {}).get('reviewer')}</p>" if payload.get('approval') else ""}
{f"<p>Reviewed on: {payload.get('approval', {}).get('decided_at')}</p>" if payload.get('approval') else ""}
{f"<p>Reason: {payload.get('approval', {}).get('reason')}</p>" if payload.get('approval', {}).get('reason') else ""}
</body></html>"""
