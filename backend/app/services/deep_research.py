from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any


def _normalize_text(text: str | None) -> str:
    if not text:
        return ""
    # Lowercase, remove non-alphanumeric except spaces, collapse spaces
    cleaned = re.sub(r"[^\w\s]", "", str(text).lower())
    return " ".join(cleaned.split())


def _parse_year(val: Any) -> int | None:
    if val is None:
        return None
    if isinstance(val, int):
        return val if val > 1000 else None
    if isinstance(val, str):
        val = val.strip()
        if val.isdigit() and len(val) == 4:
            return int(val)
        # Try to find 4-digit year in string
        match = re.search(r"\b(19\d\d|20\d\d)\b", val)
        if match:
            return int(match.group(1))
    return None


def verify_research_claim(
    *,
    claim: dict[str, Any],
    scholar_metrics: dict[str, Any] | None,
    evidence_summary: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Verify a faculty research claim against Google Scholar snapshot and evidence records.

    Deterministic and conservative verification rules:
    - Matching title & year + valid evidence + verified Scholar identity -> verified (confidence 1.0)
    - Title match but year/venue conflict -> discrepant (confidence 0.5, human review required)
    - Missing valid evidence, missing Scholar match, or unverified identity -> unverified (confidence 0.0, human review required)
    """
    now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    sources_consulted = ["activity_record"]

    title = claim.get("title") or ""
    norm_title = _normalize_text(title)
    claim_year = _parse_year(claim.get("year"))
    claim_venue = _normalize_text(claim.get("venue"))

    # Evidence inspection
    supporting_evidence_refs: list[str] = []
    has_valid_evidence = False
    if evidence_summary:
        sources_consulted.append("activity_evidence_vault")
        for ev in evidence_summary:
            ev_id = str(ev.get("id") or "")
            filename = ev.get("filename") or ev.get("original_filename") or ev_id
            val_status = ev.get("validation_status")
            if val_status in {"valid", "supported"}:
                has_valid_evidence = True
                if filename not in supporting_evidence_refs:
                    supporting_evidence_refs.append(filename)

    # Check evidence_ids directly on claim if passed
    claim_evidence_ids = claim.get("evidence_ids") or []
    if claim_evidence_ids and not supporting_evidence_refs:
        supporting_evidence_refs = [str(eid) for eid in claim_evidence_ids]

    # Scholar snapshot inspection
    scholar_status = (scholar_metrics or {}).get("status")
    scholar_error = (scholar_metrics or {}).get("error_category")
    scholar_verified = (scholar_status == "retrieved" and not scholar_error)
    publications: list[dict[str, Any]] = []

    if scholar_metrics is not None:
        sources_consulted.append("google_scholar_author")
        if scholar_verified:
            publications = scholar_metrics.get("publications") or []

    # Search Scholar publications for matching title
    matched_pub: dict[str, Any] | None = None
    if scholar_verified and norm_title:
        for pub in publications:
            pub_title = _normalize_text(pub.get("title"))
            if norm_title and pub_title and (norm_title == pub_title or norm_title in pub_title or pub_title in norm_title):
                matched_pub = pub
                break

    discrepancies: list[str] = []

    # Check for discrepancies if title matched a publication
    if matched_pub:
        pub_year = _parse_year(matched_pub.get("year"))
        if claim_year is not None and pub_year is not None and claim_year != pub_year:
            discrepancies.append(
                f"Publication year mismatch: claim states {claim_year}, but Scholar record shows {pub_year}."
            )

        pub_venue = _normalize_text(matched_pub.get("publication"))
        if claim_venue and pub_venue and claim_venue != pub_venue and claim_venue not in pub_venue and pub_venue not in claim_venue:
            discrepancies.append(
                f"Venue mismatch: claim states '{claim.get('venue')}', but Scholar record shows '{matched_pub.get('publication')}'."
            )

    # Determine status & confidence according to conservative rules
    if matched_pub and discrepancies:
        status = "discrepant"
        confidence = 0.5
        human_review_required = True
        explanation = (
            "Claimed research paper title matches Scholar records, but discrepancies "
            f"were identified: {'; '.join(discrepancies)}."
        )
    elif matched_pub and scholar_verified and has_valid_evidence and not discrepancies:
        status = "verified"
        confidence = 1.0
        human_review_required = False
        explanation = (
            "Research claim successfully verified against Google Scholar publication record "
            "and valid supporting evidence."
        )
    else:
        status = "unverified"
        confidence = 0.0
        human_review_required = True
        reasons = []
        if not has_valid_evidence:
            reasons.append("no valid supporting evidence document attached")
        if not scholar_verified:
            if scholar_error == "identity_unverified":
                reasons.append("Google Scholar identity is unverified")
            elif scholar_status == "unavailable":
                reasons.append("Google Scholar profile retrieval failed or was unavailable")
            else:
                reasons.append("Google Scholar data unverified")
        elif not matched_pub:
            reasons.append("claim title could not be matched in verified Scholar publications")

        explanation = f"Research claim could not be verified: {', '.join(reasons)}."

    return {
        "claim": {
            "title": title,
            "year": claim_year,
            "venue": claim.get("venue"),
            "authors": claim.get("authors"),
            "activity_id": claim.get("activity_id"),
        },
        "status": status,
        "confidence": confidence,
        "sources_consulted": sources_consulted,
        "supporting_evidence_references": supporting_evidence_refs,
        "discrepancies": discrepancies,
        "retrieved_at": now_iso,
        "human_review_required": human_review_required,
        "explanation": explanation,
    }


def run_deep_research_verification(
    *,
    activities: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
    research_metrics: dict[str, Any] | None,
) -> dict[str, Any]:
    research_activities = [a for a in activities if a.get("category") == "research"]
    verifications: list[dict[str, Any]] = []

    verified_count = 0
    discrepant_count = 0
    unverified_count = 0

    for act in research_activities:
        extras = act.get("extras") or {}
        date_str = act.get("activity_date") or act.get("date") or ""
        date_str = str(date_str) if date_str else ""
        year_val = extras.get("year") or (date_str[:4] if date_str and date_str[:4].isdigit() else None)

        claim = {
            "title": act.get("title") or "",
            "year": year_val,
            "venue": extras.get("venue"),
            "authors": extras.get("authors"),
            "activity_id": str(act.get("id")) if act.get("id") else None,
            "evidence_ids": act.get("evidence_ids") or [],
        }

        act_id = str(act.get("id")) if act.get("id") else None
        act_evidence = [e for e in evidence if str(e.get("activity_id")) == act_id] if act_id else []

        result = verify_research_claim(
            claim=claim,
            scholar_metrics=research_metrics,
            evidence_summary=act_evidence,
        )
        verifications.append(result)

        if result["status"] == "verified":
            verified_count += 1
        elif result["status"] == "discrepant":
            discrepant_count += 1
        else:
            unverified_count += 1

    return {
        "total_claims_analyzed": len(verifications),
        "verified_count": verified_count,
        "discrepant_count": discrepant_count,
        "unverified_count": unverified_count,
        "claim_verifications": verifications,
        "evaluated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
