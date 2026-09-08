#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "validate_release", ROOT / "scripts" / "validate_release.py"
)
validate_release = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(validate_release)


def brief() -> dict:
    return {
        "facts": [{"text": "시행일은 2026년 11월 1일이다", "source": "개정안"}],
        "human_review": ["법무 최종 확인"],
        "compliance_triggers": ["personal_data"],
        "compliance_source": {
            "source_ref": "개정안",
            "version": "v1",
            "approved_by": "법무팀",
            "checked_at": "2026-08-13",
        },
    }


def release(copy: str) -> dict:
    return {
        "schema_version": 1,
        "copy_path": "final.md",
        "copy_sha256": validate_release.copy_sha256(copy),
        "status": "internal_review_only",
        "human_reviews": [{"item": "법무 최종 확인", "status": "pending"}],
        "unverified_items": ["동의 철회 경로"],
        "compliance_review": {"status": "pending"},
        "semantic_review": {
            "status": "pending",
            "checks": {
                "facts": "pending",
                "actors": "pending",
                "timings": "pending",
                "conditions": "pending",
                "exceptions": "pending",
                "certainty": "pending",
                "new_claims": "pending",
            },
            "reviewed_by": None,
            "checked_at": None,
        },
        "new_claims": [{"text": "처리 약속", "fact_refs": ["UNVERIFIED"]}],
        "touch_rate": 0.2,
    }


class ReleaseTests(unittest.TestCase):
    def test_internal_review_only_preserves_blockers(self):
        copy = "최종 문안"
        self.assertEqual(validate_release.validate(brief(), copy, release(copy)), [])

    def test_review_complete_rejects_unresolved_items(self):
        copy = "최종 문안"
        data = release(copy)
        data["status"] = "review_complete"
        errors = validate_release.validate(brief(), copy, data)
        self.assertTrue(any("review_complete blocked" in error for error in errors))

    def test_release_state_is_bound_to_copy_hash(self):
        data = release("검토한 문안")
        errors = validate_release.validate(brief(), "바뀐 문안", data)
        self.assertTrue(any("copy_sha256" in error for error in errors))

    def test_resolved_release_can_be_review_complete(self):
        copy = "최종 문안"
        data = release(copy)
        data.update(
            {
                "status": "review_complete",
                "human_reviews": [
                    {
                        "item": "법무 최종 확인",
                        "status": "approved",
                        "reviewed_by": "법무팀",
                        "checked_at": "2026-08-14",
                    }
                ],
                "unverified_items": [],
                "compliance_review": {
                    "status": "verified",
                    "source": brief()["compliance_source"],
                    "checked_by": "법무팀",
                    "checked_at": "2026-08-14",
                },
                "new_claims": [{"text": "시행일 안내", "fact_refs": ["facts[0]"]}],
                "semantic_review": {
                    "status": "review_complete",
                    "checks": {
                        "facts": "complete",
                        "actors": "complete",
                        "timings": "complete",
                        "conditions": "complete",
                        "exceptions": "complete",
                        "certainty": "complete",
                        "new_claims": "complete",
                    },
                    "reviewed_by": "정책팀",
                    "checked_at": "2026-08-14",
                },
            }
        )
        self.assertEqual(validate_release.validate(brief(), copy, data), [])

    def test_high_stakes_release_requires_semantic_review(self):
        copy = "최종 문안"
        data = release(copy)
        del data["semantic_review"]
        errors = validate_release.validate(brief(), copy, data)
        self.assertIn("semantic_review: required for high-stakes brief", errors)

    def test_review_complete_requires_all_seven_semantic_axes(self):
        copy = "최종 문안"
        data = release(copy)
        data["status"] = "review_complete"
        data["semantic_review"]["status"] = "review_complete"
        data["semantic_review"]["checks"] = {
            axis: "complete" for axis in validate_release.SEMANTIC_CHECKS
        }
        del data["semantic_review"]["checks"]["exceptions"]
        data["semantic_review"]["reviewed_by"] = "정책팀"
        data["semantic_review"]["checked_at"] = "2026-08-14"
        errors = validate_release.validate(brief(), copy, data)
        self.assertTrue(any("exact seven axes" in error for error in errors))
        self.assertTrue(any("all seven axes" in error for error in errors))

    def test_semantic_regression_axes_block_review_complete(self):
        fixtures = {
            "actors": ("관리자가 설정한다", "사용자가 설정한다"),
            "conditions": ("승인되면 환불한다", "환불한다"),
            "exceptions": ("예외 없음", "주말에는 예외다"),
            "certainty": ("예정이다", "확정됐다"),
        }
        for axis, (before, after) in fixtures.items():
            with self.subTest(axis=axis, before=before, after=after):
                copy = after
                data = release(copy)
                data["status"] = "review_complete"
                data["copy_sha256"] = validate_release.copy_sha256(copy)
                data["semantic_review"]["checks"] = {
                    check: "complete" for check in validate_release.SEMANTIC_CHECKS
                }
                data["semantic_review"]["checks"][axis] = "issue_found"
                errors = validate_release.validate(brief(), copy, data)
                self.assertTrue(any("semantic review incomplete" in error for error in errors))

    def test_semantic_review_complete_is_validation_not_publication_approval(self):
        copy = "최종 문안"
        data = release(copy)
        data["semantic_review"] = {
            "status": "review_complete",
            "checks": {
                axis: "complete" for axis in validate_release.SEMANTIC_CHECKS
            },
            "reviewed_by": "정책팀",
            "checked_at": "2026-08-14",
        }
        self.assertEqual(data["status"], "internal_review_only")
        self.assertEqual(validate_release.validate(brief(), copy, data), [])

    def test_touch_rate_is_report_only(self):
        copy = "최종 문안"
        data = release(copy)
        data["touch_rate"] = 1.0
        self.assertEqual(validate_release.validate(brief(), copy, data), [])

    def test_review_state_fields_cannot_be_omitted(self):
        copy = "최종 문안"
        for field in ("human_reviews", "unverified_items", "new_claims"):
            data = release(copy)
            del data[field]
            errors = validate_release.validate(brief(), copy, data)
            self.assertTrue(any(error.startswith(f"{field}:") for error in errors))


if __name__ == "__main__":
    unittest.main()
