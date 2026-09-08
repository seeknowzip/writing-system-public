#!/usr/bin/env python3

from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "validate_rewrite_output", ROOT / "scripts" / "validate_rewrite_output.py"
)
validate_rewrite_output = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(validate_rewrite_output)


def legacy_validate(*args, **kwargs):
    return validate_rewrite_output.validate(*args, **kwargs, allow_legacy_diag=True)


def diag_for(*hits: list[str]) -> dict:
    return {
        "sentences": [
            {"sentence": index, "hits": sentence_hits}
            for index, sentence_hits in enumerate(hits, start=1)
        ]
    }


def strip_frontmatter(text: str) -> str:
    if not text.startswith("---\n"):
        return text
    _, separator, body = text[4:].partition("\n---\n")
    if not separator:
        raise AssertionError("fixture frontmatter is not closed")
    return body


class RewriteOutputValidatorTests(unittest.TestCase):
    def test_undiagnosed_condition_cannot_be_deleted(self):
        result = legacy_validate(
            "상품은 배송됩니다. 환불은 불가합니다.", "상품은 배송됩니다.", diag=diag_for([], [])
        )
        self.assertIn("untouched_sentence_deleted", [f.code for f in result.errors])

    def test_incomplete_duplicate_stale_or_invalid_diagnostics_fail_even_for_noop(self):
        source = "첫 문장입니다. 둘째 문장입니다."
        bad = [
            {"sentences": []}, diag_for([]),
            {"sentences": [{"sentence": 1, "hits": []}, {"sentence": 1, "hits": ["FT16"]}]},
            {"sentences": [{"sentence": True, "hits": []}, {"sentence": 2, "hits": []}]},
            {"sentences": [{"sentence": 1, "text": "다른 원문", "hits": []}, {"sentence": 2, "hits": []}]},
        ]
        for diag in bad:
            with self.subTest(diag=diag):
                result = legacy_validate(source, source, diag=diag)
                self.assertIn("diagnostic_invalid", [f.code for f in result.errors])

    def test_identical_source_does_not_skip_explicit_protection(self):
        result = legacy_validate("안내입니다.", "안내입니다.", preserve=["필수 문구"])
        self.assertIn("preserve_missing", [f.code for f in result.errors])

    def test_inserted_sentence_requires_mapping_even_with_only_existing_words(self):
        source = "신청 가능합니다. 취소 불가합니다."
        result = legacy_validate(source, source + " 신청 불가합니다.", diag=diag_for(["FT16"], []))
        self.assertIn("unmapped_sentence_inserted", [f.code for f in result.errors])

    def test_diagnosed_sentence_can_split_with_explicit_mapping(self):
        diag = diag_for(["FT16"])
        diag["insertions"] = [{"output_sentence": n, "source_sentences": [1], "reason": "조건을 별도 문장으로 분리"} for n in (1, 2)]
        result = legacy_validate("신청 가능하며 취소 불가합니다.", "신청 가능합니다. 취소 불가합니다.", diag=diag)
        self.assertEqual(result.errors, ())

    def test_reasoned_false_positive_review_is_bound_to_exact_text(self):
        # An observed heuristic collision: a legitimate antonym during an explicit correction.
        source, output = "항목이 있습니다.", "항목이 없습니다."
        diag = diag_for(["사용자 정정 반영"])
        review = {"code": "possible_syllable_corruption", "token": "없습니다", "source_token": "있습니다",
                  "source_sentence_sha256": hashlib.sha256(source.encode()).hexdigest(),
                  "output_sentence_sha256": hashlib.sha256(output.encode()).hexdigest(),
                  "reason": "사용자가 존재 여부를 명시적으로 정정함", "reviewed_by": "test-reviewer", "checked_at": "2026-09-06"}
        diag["warning_reviews"] = [review]
        self.assertEqual(legacy_validate(source, output, diag=diag).errors, ())
        review["output_sentence_sha256"] = "0" * 64
        self.assertIn("possible_syllable_corruption", [f.code for f in legacy_validate(source, output, diag=diag).errors])

    def test_sentence_split_uses_punctuation_and_newlines(self):
        sentences = validate_rewrite_output.split_sentences(
            '첫 문장입니다. "인용문은 두 문장입니다. 그래도 하나입니다."\n마지막인가요?'
        )
        self.assertEqual(
            [sentence.normalized for sentence in sentences],
            [
                "첫 문장입니다.",
                '"인용문은 두 문장입니다. 그래도 하나입니다."',
                "마지막인가요?",
            ],
        )

    def test_sentence_split_preserves_structured_periods(self):
        sentences = validate_rewrite_output.split_sentences(
            "가. 점수는 77.892점, 기간은 2022.12.1.∼2027.11.30.으로 정했습니다. "
            "근거는 <ref>내부 문장. 보충.</ref>입니다.\n"
            "나. 기다려 주세요... 아직 끝나지 않았습니다."
        )
        self.assertEqual(
            [sentence.normalized for sentence in sentences],
            [
                "가. 점수는 77.892점, 기간은 2022.12.1.∼2027.11.30.으로 정했습니다.",
                "근거는 <ref>내부 문장. 보충.</ref>입니다.",
                "나. 기다려 주세요... 아직 끝나지 않았습니다.",
            ],
        )

    def test_normal_output_passes(self):
        source = "첫 문장은 둡니다. 표현을 길게 작성했습니다."
        output = "첫 문장은 둡니다. 표현을 짧게 썼습니다."
        result = legacy_validate(
            source, output, diag=diag_for([], ["FT15"])
        )
        self.assertEqual(result.errors, ())
        self.assertEqual(result.touched_sentences, 1)

    def test_untouched_sentence_change_is_error(self):
        result = legacy_validate(
            "범위를 나눴습니다.",
            "범위를 나내습니다.",
            diag=diag_for([]),
        )
        self.assertTrue(
            any(
                finding.code == "untouched_sentence_changed"
                for finding in result.errors
            )
        )
        self.assertTrue(
            any(
                finding.code == "new_token_in_untouched_sentence"
                for finding in result.errors
            )
        )

    def test_three_observed_corruptions_are_detected_without_diag(self):
        cases = (
            ("범위를 나눴습니다.", "범위를 나내습니다."),
            ("순서를 바꿨습니다.", "순서를 바꿖습니다."),
            ("어디에서 멈췄는지.", "어디에서 멈춼는지."),
        )
        for source, output in cases:
            with self.subTest(output=output):
                result = legacy_validate(source, output)
                self.assertTrue(
                    any(
                        finding.code == "possible_syllable_corruption"
                        for finding in result.errors
                    )
                )

    def test_changed_sentence_with_hits_blocks_unreviewed_corruption(self):
        result = legacy_validate(
            "순서를 바꿨습니다.",
            "순서를 바꿖습니다.",
            diag=diag_for(["FT15"]),
        )
        self.assertTrue(any(finding.code == "possible_syllable_corruption" for finding in result.errors))

    def test_new_word_is_compared_against_the_entire_source(self):
        result = legacy_validate(
            "기존어는 여기 있습니다. 둘째 문장입니다.",
            "여기 있습니다. 기존어는 둘째 문장입니다.",
            diag=diag_for(["FT15"], []),
        )
        self.assertFalse(
            any(
                finding.code == "new_token_in_untouched_sentence"
                and "기존어는" in finding.message
                for finding in result.errors
            )
        )

    def test_new_word_in_inserted_sentence_is_unpointed(self):
        result = legacy_validate(
            "첫 문장입니다.",
            "첫 문장입니다. 추가 문장입니다.",
            diag=diag_for(["FT15"]),
        )
        self.assertTrue(
            any(
                finding.code == "new_token_in_untouched_sentence"
                and "추가" in finding.message
                for finding in result.errors
            )
        )

    def test_particle_change_is_not_reported_as_syllable_corruption(self):
        result = legacy_validate(
            "결과와 상태를 확인합니다.",
            "결과와 상태로 판단합니다.",
        )
        self.assertFalse(
            any(
                finding.code == "possible_syllable_corruption"
                for finding in result.warnings
            )
        )

    def test_preserve_list_is_enforced_without_diag(self):
        result = legacy_validate(
            "검수 중 상태입니다.",
            "검토 상태입니다.",
            preserve=["검수 중"],
        )
        self.assertTrue(
            any(finding.code == "preserve_missing" for finding in result.errors)
        )

    def test_protected_token_sets_are_checked_without_diag(self):
        result = legacy_validate(
            "2026-09-03 Codex에서 `검수 중`을 확인합니다.",
            "Notion에서 확인합니다.",
        )
        missing = {
            finding.message
            for finding in result.errors
            if finding.code == "protected_token_missing"
        }
        self.assertTrue(any("2026-09-03" in message for message in missing))
        self.assertTrue(any("Codex" in message for message in missing))
        self.assertTrue(any("`검수 중`" in message for message in missing))
        self.assertTrue(
            any(
                finding.code == "protected_token_added" and "Notion" in finding.message
                for finding in result.warnings
            )
        )

    def test_structured_diagnostic_preserves_legacy_evidence(self):
        result = legacy_validate(
            "검토를 진행하는 것이 가능합니다.", "검토할 수 있습니다.",
            diag=diag_for([{"id": "FT17", "evidence": "진행하는 것이 가능합니다"}]),
        )
        self.assertEqual(result.errors, ())

    def test_structured_diagnostic_requires_evidence(self):
        result = legacy_validate(
            "검토합니다.", "검토합니다.", diag=diag_for([{"id": "FT17"}]),
        )
        self.assertTrue(any(f.code == "diagnostic_invalid" for f in result.errors))

    def test_whitespace_only_change_does_not_change_untouched_sentence(self):
        result = legacy_validate(
            "첫 문장을 그대로 둡니다.",
            "첫  문장을 그대로 둡니다.",
            diag=diag_for([]),
        )
        self.assertEqual(result.errors, ())

    def test_cli_returns_one_and_prints_summary_for_error(self):
        with tempfile.TemporaryDirectory() as directory:
            source_path = Path(directory) / "source.md"
            output_path = Path(directory) / "output.md"
            diag_path = Path(directory) / "diag.json"
            source_path.write_text("범위를 나눴습니다.", encoding="utf-8")
            output_path.write_text("범위를 나내습니다.", encoding="utf-8")
            diag_path.write_text(json.dumps(diag_for([])), encoding="utf-8")
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = validate_rewrite_output.main(
                    [
                        "--source",
                        str(source_path),
                        "--output",
                        str(output_path),
                        "--legacy-diagnostic",
                        "--diag",
                        str(diag_path),
                    ]
                )
        self.assertEqual(exit_code, 1)
        self.assertIn("ERROR: untouched_sentence_changed", stdout.getvalue())
        self.assertRegex(
            stdout.getvalue(), r"ERROR touched_sentences=1 errors=\d+ warnings=\d+"
        )

    def test_cli_accepts_json_preserve_array(self):
        with tempfile.TemporaryDirectory() as directory:
            source_path = Path(directory) / "source.md"
            output_path = Path(directory) / "output.md"
            source_path.write_text("Codex를 씁니다.", encoding="utf-8")
            output_path.write_text("Codex를 씁니다.", encoding="utf-8")
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = validate_rewrite_output.main(
                    [
                        "--source",
                        str(source_path),
                        "--output",
                        str(output_path),
                        "--preserve",
                        '["Codex"]',
                    ]
                )
        self.assertEqual(exit_code, 0)
        self.assertIn("OK touched_sentences=0 errors=0 warnings=0", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
