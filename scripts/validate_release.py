#!/usr/bin/env python3
"""Validate that review state is bound to the exact final copy."""

from __future__ import annotations

import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
import sys


STATUSES = {"internal_review_only", "review_complete"}
REVIEW_STATUSES = {"pending", "approved", "rejected"}
SEMANTIC_STATUSES = {"pending", "review_complete"}
SEMANTIC_CHECK_STATUSES = {"pending", "complete", "issue_found"}
SEMANTIC_CHECKS = {
    "facts",
    "actors",
    "timings",
    "conditions",
    "exceptions",
    "certainty",
    "new_claims",
}
HIGH_STAKES_TRIGGERS = {"payment", "personal_data", "incident", "regulated"}


def copy_sha256(copy: str) -> str:
    return hashlib.sha256(copy.encode("utf-8")).hexdigest()


def valid_date(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def is_high_stakes(brief: dict) -> bool:
    triggers = brief.get("compliance_triggers", [])
    return bool(brief.get("human_review")) or bool(
        isinstance(triggers, list) and HIGH_STAKES_TRIGGERS.intersection(triggers)
    )


def validate_semantic_review(
    brief: dict,
    release: dict,
    blockers: list[str],
) -> list[str]:
    """Validate review bookkeeping, not the meaning of free-form copy."""
    errors: list[str] = []
    semantic = release.get("semantic_review")
    required = is_high_stakes(brief)
    if semantic is None:
        if required:
            errors.append("semantic_review: required for high-stakes brief")
        return errors
    if not isinstance(semantic, dict):
        return ["semantic_review: object required"]

    semantic_status = semantic.get("status")
    if semantic_status not in SEMANTIC_STATUSES:
        errors.append(
            "semantic_review.status: must be one of "
            + ", ".join(sorted(SEMANTIC_STATUSES))
        )

    checks = semantic.get("checks")
    if not isinstance(checks, dict):
        errors.append("semantic_review.checks: object required")
        checks = {}
    if set(checks) != SEMANTIC_CHECKS:
        missing = sorted(SEMANTIC_CHECKS - set(checks))
        extra = sorted(set(checks) - SEMANTIC_CHECKS)
        errors.append(
            f"semantic_review.checks: exact seven axes required; "
            f"missing={missing}, extra={extra}"
        )
    for axis, value in checks.items():
        if axis in SEMANTIC_CHECKS and value not in SEMANTIC_CHECK_STATUSES:
            errors.append(f"semantic_review.checks.{axis}: invalid status")

    incomplete = [axis for axis in sorted(SEMANTIC_CHECKS) if checks.get(axis) != "complete"]
    if incomplete:
        blockers.append("semantic review incomplete: " + ", ".join(incomplete))

    reviewed_by = semantic.get("reviewed_by")
    checked_at = semantic.get("checked_at")
    if semantic_status == "review_complete":
        if incomplete:
            errors.append("semantic_review.review_complete: all seven axes must be complete")
        if not isinstance(reviewed_by, str) or not reviewed_by.strip():
            errors.append("semantic_review.reviewed_by: required when review_complete")
        if not valid_date(checked_at):
            errors.append("semantic_review.checked_at: YYYY-MM-DD required when review_complete")
    else:
        if reviewed_by is not None and (not isinstance(reviewed_by, str) or not reviewed_by.strip()):
            errors.append("semantic_review.reviewed_by: non-empty string or null required")
        if checked_at is not None and not valid_date(checked_at):
            errors.append("semantic_review.checked_at: YYYY-MM-DD or null required")

    return errors


def validate(brief: dict, copy: str, release: dict) -> list[str]:
    errors: list[str] = []
    blockers: list[str] = []

    for field in ("human_reviews", "unverified_items", "new_claims"):
        if field not in release:
            errors.append(f"{field}: required field (use an empty list when none)")

    if release.get("schema_version") != 1:
        errors.append("schema_version: must be 1")

    copy_path = release.get("copy_path")
    if not isinstance(copy_path, str) or not copy_path.strip():
        errors.append("copy_path: non-empty string required")

    expected_hash = copy_sha256(copy)
    if release.get("copy_sha256") != expected_hash:
        errors.append("copy_sha256: does not match the supplied copy")

    status = release.get("status")
    if status not in STATUSES:
        errors.append(f"status: must be one of {', '.join(sorted(STATUSES))}")

    review_entries = release.get("human_reviews", [])
    if not isinstance(review_entries, list):
        errors.append("human_reviews: list required")
        review_entries = []
    reviews_by_item: dict[str, dict] = {}
    for index, entry in enumerate(review_entries):
        prefix = f"human_reviews[{index}]"
        if not isinstance(entry, dict):
            errors.append(f"{prefix}: object required")
            continue
        item = entry.get("item")
        review_status = entry.get("status")
        if not isinstance(item, str) or not item.strip():
            errors.append(f"{prefix}.item: non-empty string required")
            continue
        if item in reviews_by_item:
            errors.append(f"{prefix}.item: duplicate review item {item!r}")
        reviews_by_item[item] = entry
        if review_status not in REVIEW_STATUSES:
            errors.append(f"{prefix}.status: invalid review status")
        if review_status == "approved":
            if not isinstance(entry.get("reviewed_by"), str) or not entry["reviewed_by"].strip():
                errors.append(f"{prefix}.reviewed_by: required when approved")
            if not valid_date(entry.get("checked_at")):
                errors.append(f"{prefix}.checked_at: YYYY-MM-DD required when approved")
        else:
            blockers.append(f"human review {item!r} is {review_status!r}")

    required_reviews = [str(item) for item in brief.get("human_review", [])]
    for item in required_reviews:
        if item not in reviews_by_item:
            blockers.append(f"missing human review state for {item!r}")

    unknown_reviews = set(reviews_by_item) - set(required_reviews)
    for item in sorted(unknown_reviews):
        errors.append(f"human_reviews: item not present in brief: {item!r}")

    unverified_items = release.get("unverified_items", [])
    if not isinstance(unverified_items, list) or any(
        not isinstance(item, str) or not item.strip() for item in unverified_items
    ):
        errors.append("unverified_items: list of non-empty strings required")
    elif unverified_items:
        blockers.append(f"unverified items remain: {len(unverified_items)}")

    new_claims = release.get("new_claims", [])
    if not isinstance(new_claims, list):
        errors.append("new_claims: list required")
        new_claims = []
    valid_fact_refs = {f"facts[{index}]" for index, _ in enumerate(brief.get("facts", []))}
    for index, claim in enumerate(new_claims):
        prefix = f"new_claims[{index}]"
        if not isinstance(claim, dict):
            errors.append(f"{prefix}: object required")
            continue
        if not isinstance(claim.get("text"), str) or not claim["text"].strip():
            errors.append(f"{prefix}.text: non-empty string required")
        fact_refs = claim.get("fact_refs")
        if not isinstance(fact_refs, list) or not fact_refs:
            errors.append(f"{prefix}.fact_refs: non-empty list required")
            continue
        for ref in fact_refs:
            if ref == "UNVERIFIED":
                blockers.append(f"{prefix} is UNVERIFIED")
            elif ref not in valid_fact_refs:
                errors.append(f"{prefix}.fact_refs: unknown fact reference {ref!r}")

    triggers = brief.get("compliance_triggers", [])
    compliance_review = release.get("compliance_review")
    if triggers:
        if not isinstance(compliance_review, dict):
            blockers.append("missing compliance review state")
        elif compliance_review.get("status") != "verified":
            blockers.append("compliance review is not verified")
        else:
            if compliance_review.get("source") != brief.get("compliance_source"):
                errors.append("compliance_review.source: does not match brief compliance_source")
            if not isinstance(compliance_review.get("checked_by"), str) or not compliance_review["checked_by"].strip():
                errors.append("compliance_review.checked_by: required when verified")
            if not valid_date(compliance_review.get("checked_at")):
                errors.append("compliance_review.checked_at: YYYY-MM-DD required when verified")

    touch_rate = release.get("touch_rate")
    if not isinstance(touch_rate, (int, float)) or isinstance(touch_rate, bool) or not 0 <= touch_rate <= 1:
        errors.append("touch_rate: number from 0 to 1 required")

    errors.extend(validate_semantic_review(brief, release, blockers))

    semantic = release.get("semantic_review")
    if status == "review_complete" and is_high_stakes(brief):
        if not isinstance(semantic, dict) or semantic.get("status") != "review_complete":
            blockers.append("semantic review status is not review_complete")

    if status == "review_complete" and blockers:
        errors.extend(f"review_complete blocked: {blocker}" for blocker in blockers)

    return errors


def read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read JSON {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return data


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--brief", type=Path, required=True)
    parser.add_argument("--copy", dest="copy_path", type=Path, required=True)
    parser.add_argument("--status", dest="status_path", type=Path, required=True)
    args = parser.parse_args()

    try:
        brief = read_json(args.brief)
        copy = args.copy_path.read_text(encoding="utf-8")
        release = read_json(args.status_path)
        errors = validate(brief, copy, release)
    except (OSError, ValueError) as exc:
        errors = [str(exc)]
        release = {}

    if errors:
        print("RELEASE_INVALID")
        for error in errors:
            print(f"- {error}")
        return 1

    print(f"RELEASE_OK status={release['status']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
