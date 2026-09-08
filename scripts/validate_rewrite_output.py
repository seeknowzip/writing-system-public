#!/usr/bin/env python3
"""Validate a rewrite output against its source and optional diagnostics."""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any, Iterable, NamedTuple


HANGUL_TOKEN_RE = re.compile(r"^[가-힣]+$")
NUMBER_RE = re.compile(r"(?<![A-Za-z0-9])\d+(?:[./:-]\d+)*(?![A-Za-z0-9])")
CAPITALIZED_TOKEN_RE = re.compile(
    r"(?<![A-Za-z0-9])[A-Z][A-Za-z0-9]*(?:[-_][A-Za-z0-9]+)*(?![A-Za-z0-9])"
)
CODE_RE = re.compile(r"`[^`\n]+`")
DATE_RE = re.compile(
    r"(?<!\d)\d{2,4}\.[ \t]*\d{1,2}\.[ \t]*\d{1,2}\."
    r"(?:[ \t]*[~∼-][ \t]*\d{2,4}\.[ \t]*\d{1,2}\.[ \t]*\d{1,2}\.)?"
)
TAG_RE = re.compile(r"<[^>\n]*>")
PAIRED_TAG_RE = re.compile(
    r"<(?P<name>[A-Za-z][A-Za-z0-9:_-]*)(?:[ \t][^<>\n]*?)?>"
    r"[^\n]*?</(?P=name)[ \t]*>",
    re.IGNORECASE,
)
OPEN_QUOTES = {"“": "”", "‘": "’", "「": "」", "『": "』", "《": "》", "〈": "〉"}
CLOSE_QUOTES = {closing: opening for opening, closing in OPEN_QUOTES.items()}
SYMMETRIC_QUOTES = {'"', "'"}


class Sentence(NamedTuple):
    text: str
    normalized: str


class Alignment(NamedTuple):
    source_index: int | None
    output_index: int | None


class Finding(NamedTuple):
    level: str
    code: str
    message: str


class ValidationResult(NamedTuple):
    touched_sentences: int
    errors: tuple[Finding, ...]
    warnings: tuple[Finding, ...]


def normalize_whitespace(text: str) -> str:
    return " ".join(text.split())


def _ascii_quote_is_delimiter(text: str, index: int) -> bool:
    if text[index] == '"':
        return True
    before = text[index - 1] if index else ""
    after = text[index + 1] if index + 1 < len(text) else ""
    return not (before.isalnum() and after.isalnum())


def _protected_sentence_positions(text: str) -> set[int]:
    """Return punctuation positions that belong to dates or markup examples."""
    protected: set[int] = set()
    for pattern in (DATE_RE, TAG_RE, PAIRED_TAG_RE):
        for match in pattern.finditer(text):
            protected.update(range(match.start(), match.end()))
    return protected


def _period_is_list_marker(text: str, index: int) -> bool:
    line_start = max(text.rfind("\n", 0, index), text.rfind("\r", 0, index)) + 1
    prefix = text[line_start : index + 1]
    if index + 1 >= len(text) or not text[index + 1].isspace():
        return False
    return bool(
        re.fullmatch(
            r"[ \t]*(?:\d+|[A-Za-z]|가|나|다|라|마|바|사|아|자|차|카|타|파|하)\.",
            prefix,
        )
    )


def _period_is_nonterminal(text: str, index: int, protected: set[int]) -> bool:
    if index in protected or _period_is_list_marker(text, index):
        return True
    before = text[index - 1] if index else ""
    after = text[index + 1] if index + 1 < len(text) else ""
    if before == "." or after == ".":
        return True
    return before.isdigit() and after.isdigit()


def split_sentences(text: str) -> list[Sentence]:
    """Split on terminal punctuation or newlines, preserving structured spans."""
    sentences: list[Sentence] = []
    buffer: list[str] = []
    quote_stack: list[str] = []
    pending_quoted_terminal = False
    protected = _protected_sentence_positions(text)

    def flush() -> None:
        nonlocal pending_quoted_terminal
        value = "".join(buffer).strip()
        if value:
            sentences.append(Sentence(value, normalize_whitespace(value)))
        buffer.clear()
        pending_quoted_terminal = False

    for index, char in enumerate(text):
        if char in "\r\n":
            if quote_stack:
                buffer.append(char)
            else:
                flush()
            continue

        buffer.append(char)
        if char in OPEN_QUOTES:
            quote_stack.append(char)
            continue
        if char in CLOSE_QUOTES and quote_stack and quote_stack[-1] == CLOSE_QUOTES[char]:
            quote_stack.pop()
            if not quote_stack and pending_quoted_terminal:
                flush()
            continue
        if char in SYMMETRIC_QUOTES and _ascii_quote_is_delimiter(text, index):
            if quote_stack and quote_stack[-1] == char:
                quote_stack.pop()
                if not quote_stack and pending_quoted_terminal:
                    flush()
            else:
                quote_stack.append(char)
            continue

        if char in ".?!":
            if char == "." and _period_is_nonterminal(text, index, protected):
                continue
            if quote_stack:
                pending_quoted_terminal = True
            else:
                flush()

    flush()
    return sentences


def _align_replace_block(
    source: list[Sentence],
    output: list[Sentence],
    source_offset: int,
    output_offset: int,
) -> list[Alignment]:
    """Align a replace block by minimizing character-difference and gap costs."""
    source_count = len(source)
    output_count = len(output)
    gap_cost = 0.65
    costs = [[0.0] * (output_count + 1) for _ in range(source_count + 1)]
    steps = [[""] * (output_count + 1) for _ in range(source_count + 1)]
    for i in range(1, source_count + 1):
        costs[i][0] = i * gap_cost
        steps[i][0] = "delete"
    for j in range(1, output_count + 1):
        costs[0][j] = j * gap_cost
        steps[0][j] = "insert"

    for i in range(1, source_count + 1):
        for j in range(1, output_count + 1):
            ratio = difflib.SequenceMatcher(
                None,
                source[i - 1].normalized,
                output[j - 1].normalized,
                autojunk=False,
            ).ratio()
            choices = (
                (costs[i - 1][j - 1] + (1.0 - ratio), "pair"),
                (costs[i - 1][j] + gap_cost, "delete"),
                (costs[i][j - 1] + gap_cost, "insert"),
            )
            costs[i][j], steps[i][j] = min(choices, key=lambda choice: choice[0])

    aligned: list[Alignment] = []
    i, j = source_count, output_count
    while i or j:
        step = steps[i][j]
        if step == "pair":
            i -= 1
            j -= 1
            aligned.append(Alignment(source_offset + i, output_offset + j))
        elif step == "delete":
            i -= 1
            aligned.append(Alignment(source_offset + i, None))
        else:
            j -= 1
            aligned.append(Alignment(None, output_offset + j))
    aligned.reverse()
    return aligned


def align_sentences(
    source: list[Sentence], output: list[Sentence]
) -> list[Alignment]:
    matcher = difflib.SequenceMatcher(
        None,
        [sentence.normalized for sentence in source],
        [sentence.normalized for sentence in output],
        autojunk=False,
    )
    aligned: list[Alignment] = []
    for tag, source_start, source_end, output_start, output_end in matcher.get_opcodes():
        if tag == "equal":
            aligned.extend(
                Alignment(source_index, output_index)
                for source_index, output_index in zip(
                    range(source_start, source_end), range(output_start, output_end)
                )
            )
        elif tag == "replace":
            aligned.extend(
                _align_replace_block(
                    source[source_start:source_end],
                    output[output_start:output_end],
                    source_start,
                    output_start,
                )
            )
        elif tag == "delete":
            aligned.extend(
                Alignment(source_index, None)
                for source_index in range(source_start, source_end)
            )
        else:
            aligned.extend(
                Alignment(None, output_index)
                for output_index in range(output_start, output_end)
            )
    return aligned


def word_tokens(sentence: str) -> list[str]:
    tokens: list[str] = []
    for raw_token in sentence.split():
        token = "".join(
            char
            for char in raw_token
            if not unicodedata.category(char).startswith("P") and char != "`"
        )
        if token:
            tokens.append(token)
    return tokens


def _hangul_parts(char: str) -> tuple[int, int, int]:
    value = ord(char) - 0xAC00
    return value // 588, (value % 588) // 28, value % 28


def possible_syllable_corruption(
    output_token: str, source_tokens: Iterable[str]
) -> str | None:
    """Return a near-identical source token when a Hangul batchim looks damaged."""
    if not HANGUL_TOKEN_RE.fullmatch(output_token):
        return None
    for source_token in sorted(source_tokens):
        if (
            source_token == output_token
            or len(source_token) != len(output_token)
            or not HANGUL_TOKEN_RE.fullmatch(source_token)
        ):
            continue
        differences = [
            index
            for index, (before, after) in enumerate(zip(source_token, output_token))
            if before != after
        ]
        if len(differences) != 1:
            continue
        index = differences[0]
        # A suffix after the damaged syllable is the minimal evidence that these
        # are two forms of the same stem, rather than unrelated words or particles.
        if index == len(source_token) - 1:
            continue
        before_parts = _hangul_parts(source_token[index])
        after_parts = _hangul_parts(output_token[index])
        if before_parts[0] == after_parts[0] and before_parts[2] != after_parts[2]:
            return source_token
    return None


def protected_tokens(text: str) -> set[str]:
    return set(CODE_RE.findall(text)) | set(NUMBER_RE.findall(text)) | set(
        CAPITALIZED_TOKEN_RE.findall(text)
    )


def _diag_hits_by_sentence(
    diag: dict[str, Any], source: list[Sentence], *, allow_legacy: bool = False
) -> dict[int, list[Any]]:
    if not isinstance(diag, dict):
        raise ValueError("diag top level must be an object")
    modern = diag.get("schema_version") == 2
    if not modern and not allow_legacy:
        raise ValueError("diag.schema_version must be 2; legacy records require explicit compatibility mode")
    rows = diag.get("sentences")
    if not isinstance(rows, list):
        raise ValueError("diag.sentences must be an array")
    hits_by_sentence: dict[int, list[Any]] = {}
    for position, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            raise ValueError(f"diag.sentences[{position - 1}] must be an object")
        if modern:
            if "sentence" not in row or not isinstance(row.get("text"), str):
                raise ValueError("diag v2: sentence and source text are required")
            if row.get("decision") not in ("no-op", "change"):
                raise ValueError("diag v2: complete decision required; template is pending")
            if not isinstance(row.get("reason"), str) or not row["reason"].strip():
                raise ValueError("diag v2: reason for the decision required")
        # Historical logs used zero-based `i`; new logs use one-based `sentence`.
        if "sentence" in row:
            sentence_number = row["sentence"]
        elif "i" in row and type(row["i"]) is int:
            sentence_number = row["i"] + 1
        elif "i" in row:
            raise ValueError("diag: i must be a zero-based integer")
        else:
            sentence_number = position
        hits = row.get("hits")
        if type(sentence_number) is not int or not 1 <= sentence_number <= len(source):
            raise ValueError(f"diag.sentences[{position - 1}].sentence must be a positive integer")
        if sentence_number - 1 in hits_by_sentence:
            raise ValueError(f"diag: duplicate sentence {sentence_number}")
        def valid_hit(hit: Any) -> bool:
            if isinstance(hit, str):
                return bool(hit.strip())
            return isinstance(hit, dict) and all(
                isinstance(hit.get(key), str) and bool(hit[key].strip())
                for key in ("id", "evidence")
            )

        if not isinstance(hits, list) or not all(valid_hit(hit) for hit in hits):
            raise ValueError(f"diag.sentences[{position - 1}].hits must be an array of non-empty reasons")
        if modern and bool(hits) != (row["decision"] == "change"):
            raise ValueError("diag v2: hits and decision disagree")
        if "text" in row and (
            not isinstance(row["text"], str)
            or normalize_whitespace(row["text"]) != source[sentence_number - 1].normalized
        ):
            raise ValueError(f"diag: source text mismatch at sentence {sentence_number}")
        hits_by_sentence[sentence_number - 1] = hits
    if set(hits_by_sentence) != set(range(len(source))):
        raise ValueError("diag: every source sentence must have exactly one diagnostic row")
    return hits_by_sentence


def insertion_mappings(diag: dict[str, Any], hits: dict[int, list[Any]], output_count: int) -> set[int]:
    rows = diag.get("insertions", [])
    if not isinstance(rows, list):
        raise ValueError("diag.insertions must be an array")
    mapped: set[int] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("diag.insertions entries must be objects")
        number = row.get("output_sentence")
        sources = row.get("source_sentences")
        if type(number) is not int or not 1 <= number <= output_count or number - 1 in mapped:
            raise ValueError("diag.insertions: unique valid output_sentence required")
        if (not isinstance(sources, list) or not sources
                or any(type(n) is not int or not hits.get(n - 1) for n in sources)):
            raise ValueError("diag.insertions: every source reference must be a diagnosed sentence")
        if not isinstance(row.get("reason"), str) or not row["reason"].strip():
            raise ValueError("diag.insertions: reason required")
        mapped.add(number - 1)
    return mapped


def reviewed_corruption(
    diag: dict[str, Any] | None, source: str, output: str, token: str, source_token: str
) -> bool:
    """A heuristic false positive needs an exact-output, reasoned review record."""
    if diag is None:
        return False
    reviews = diag.get("warning_reviews", [])
    if not isinstance(reviews, list):
        return False
    for review in reviews:
        if not isinstance(review, dict):
            continue
        if (
            review.get("code") == "possible_syllable_corruption"
            and review.get("token") == token
            and review.get("source_token") == source_token
            and review.get("source_sentence_sha256") == hashlib.sha256(source.encode()).hexdigest()
            and review.get("output_sentence_sha256") == hashlib.sha256(output.encode()).hexdigest()
            and all(isinstance(review.get(k), str) and review[k].strip()
                    for k in ("reason", "reviewed_by", "checked_at"))
        ):
            return True
    return False


def validate(
    source_text: str,
    output_text: str,
    *,
    diag: dict[str, Any] | None = None,
    preserve: Iterable[str] = (),
    allow_legacy_diag: bool = False,
) -> ValidationResult:
    source_sentences = split_sentences(source_text)
    output_sentences = split_sentences(output_text)
    alignment = align_sentences(source_sentences, output_sentences)
    errors: list[Finding] = []
    warnings: list[Finding] = []
    valid_diag = diag is not None
    try:
        hits_by_sentence = _diag_hits_by_sentence(diag, source_sentences, allow_legacy=allow_legacy_diag) if diag is not None else {}
        mapped_insertions = insertion_mappings(diag, hits_by_sentence, len(output_sentences)) if diag is not None else set()
    except (ValueError, TypeError) as error:
        errors.append(Finding("ERROR", "diagnostic_invalid", str(error)))
        valid_diag = False
        hits_by_sentence, mapped_insertions = {}, set()
    source_for_output = {
        item.output_index: item.source_index
        for item in alignment
        if item.output_index is not None
    }

    touched = 0
    for item in alignment:
        if item.source_index is None or item.output_index is None:
            touched += 1
            if valid_diag and item.source_index is not None and not hits_by_sentence[item.source_index]:
                errors.append(Finding(
                    "ERROR", "untouched_sentence_deleted",
                    f"sentence={item.source_index + 1} source={source_sentences[item.source_index].normalized!r}",
                ))
            if valid_diag and item.source_index is None and item.output_index not in mapped_insertions:
                errors.append(Finding(
                    "ERROR", "unmapped_sentence_inserted",
                    f"sentence={item.output_index + 1}: split/insert requires an explicit insertion mapping",
                ))
            continue
        source_sentence = source_sentences[item.source_index]
        output_sentence = output_sentences[item.output_index]
        if source_sentence.normalized == output_sentence.normalized:
            continue
        touched += 1
        if valid_diag and hits_by_sentence.get(item.source_index) == []:
            errors.append(
                Finding(
                    "ERROR",
                    "untouched_sentence_changed",
                    f"sentence={item.source_index + 1} source={source_sentence.normalized!r} output={output_sentence.normalized!r}",
                )
            )

    source_words = set(word_tokens(source_text))
    new_output_words = set(word_tokens(output_text)) - source_words
    for output_index, sentence in enumerate(output_sentences):
        source_index = source_for_output.get(output_index)
        hits = hits_by_sentence.get(source_index) if source_index is not None else None
        for token in dict.fromkeys(word_tokens(sentence.text)):
            if token not in new_output_words:
                continue
            location = f"sentence={output_index + 1} token={token!r}"
            if valid_diag and ((source_index is None and output_index not in mapped_insertions) or hits == []):
                errors.append(Finding("ERROR", "new_token_in_untouched_sentence", location))
            # Compare only with the aligned sentence (or explicitly mapped split sources).
            source_indices = [source_index] if source_index is not None else []
            if valid_diag and source_index is None:
                source_indices = [n - 1 for row in diag.get("insertions", [])
                                  if row["output_sentence"] == output_index + 1 for n in row["source_sentences"]]
            local_source = " ".join(source_sentences[n].text for n in source_indices)
            match = possible_syllable_corruption(token, word_tokens(local_source))
            if match is not None:
                reviewed = reviewed_corruption(diag if valid_diag else None, local_source, sentence.text, token, match)
                (warnings if reviewed else errors).append(
                    Finding(
                        "WARNING" if reviewed else "ERROR",
                        "possible_syllable_corruption",
                        f"{location} source_token={match!r}",
                    )
                )

    for value in preserve:
        if value not in output_text:
            errors.append(
                Finding("ERROR", "preserve_missing", f"value={value!r}")
            )

    source_protected = protected_tokens(source_text)
    output_protected = protected_tokens(output_text)
    for token in sorted(source_protected - output_protected):
        errors.append(
            Finding("ERROR", "protected_token_missing", f"token={token!r}")
        )
    for token in sorted(output_protected - source_protected):
        warnings.append(
            Finding("WARNING", "protected_token_added", f"token={token!r}")
        )

    return ValidationResult(touched, tuple(errors), tuple(warnings))


def parse_preserve(value: str | None) -> list[str]:
    if value is None:
        return []
    parsed = json.loads(value)
    if not isinstance(parsed, list) or not all(isinstance(item, str) for item in parsed):
        raise ValueError("--preserve must be a JSON array of strings")
    return parsed


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--diagnostic-template", action="store_true", help="Print source-bound diagnostic rows; does not diagnose the text")
    parser.add_argument("--diag", type=Path)
    parser.add_argument("--legacy-diagnostic", action="store_true", help="Historical diagnostics only; does not certify a new v2 diagnosis")
    parser.add_argument("--preserve")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        source_text = args.source.read_text(encoding="utf-8")
        if args.diagnostic_template:
            print(json.dumps({"schema_version": 2, "sentences": [
                {"sentence": i, "text": sentence.text, "decision": "pending", "reason": "", "hits": []}
                for i, sentence in enumerate(split_sentences(source_text), 1)
            ]}, ensure_ascii=False, indent=2))
            return 0
        if args.output is None:
            raise ValueError("--output is required unless --diagnostic-template is used")
        output_text = args.output.read_text(encoding="utf-8")
        diag = (
            json.loads(args.diag.read_text(encoding="utf-8"))
            if args.diag is not None
            else None
        )
        if args.diag is not None and not isinstance(diag, dict):
            raise ValueError("diag top level must be an object")
        preserve = parse_preserve(args.preserve)
        result = validate(source_text, output_text, diag=diag, preserve=preserve, allow_legacy_diag=args.legacy_diagnostic)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
        print(f"ERROR: input_invalid: {error}")
        print("ERROR touched_sentences=0 errors=1 warnings=0")
        return 1

    for finding in (*result.errors, *result.warnings):
        print(f"{finding.level}: {finding.code}: {finding.message}")
    status = "ERROR" if result.errors else "OK"
    print(
        f"{status} touched_sentences={result.touched_sentences} "
        f"errors={len(result.errors)} warnings={len(result.warnings)}"
    )
    return 1 if result.errors else 0


if __name__ == "__main__":
    sys.exit(main())
