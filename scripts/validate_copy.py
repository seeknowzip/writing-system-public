#!/usr/bin/env python3
"""Check copy against facts and exact-string contracts in a brief."""

from __future__ import annotations

import argparse
from collections import Counter
import json
import re
import sys
from pathlib import Path


UNITS = r"%|년|월|일|시|분|초|주|개월|개|명|원|만원|회|대"
NUMBER_RE = re.compile(rf"\d[\d,]*(?:\.\d+)?(?:\s*(?:{UNITS}))?")
LIST_MARKER_RE = re.compile(
    r"(?m)^\s*(?:#{1,6}\s*)?(?:[*_~]{1,3})?\d+[.)](?:[*_~]{1,3})?\s+"
)
HTML_COMMENT_RE = re.compile(r"<!--[\s\S]*?-->")
RANGE_RE = re.compile(
    rf"(?<!\d)(\d[\d,]*(?:\.\d+)?)\s*({UNITS})?\s*"
    rf"(?:에서|[~∼–—-])\s*(\d[\d,]*(?:\.\d+)?)\s*({UNITS})"
)
KOREAN_NATIVE_RE = re.compile(
    r"(?<![가-힣])(한|두|세|네|다섯|여섯|일곱|여덟|아홉|열)\s*(명|개)"
    r"(?=$|[\s.,!?…\])}>]|[이가은는을를의도만씩]|이다|예요|입니다|다)"
)
KOREAN_MONEY_RE = re.compile(
    r"(?<![가-힣])(일|이|삼|사|오|육|칠|팔|구)만\s*원"
    r"(?=$|[\s.,!?…\])}>]|[이가은는을를의도만씩]|이다|예요|입니다|다)"
)
HEADING_RE = re.compile(r"(?m)^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$")
CTA_LINE_RE = re.compile(r"(?m)^\s*\[([^\]\n]+)\](?:\([^\n)]+\))?\s*$")
SUBJECT_LINE_RE = re.compile(r"(?mi)^\s*(?:subject|제목)\s*:\s*\S.+$")

NATIVE_NUMBERS = {
    "한": 1,
    "두": 2,
    "세": 3,
    "네": 4,
    "다섯": 5,
    "여섯": 6,
    "일곱": 7,
    "여덟": 8,
    "아홉": 9,
    "열": 10,
}
SINO_NUMBERS = {"일": 1, "이": 2, "삼": 3, "사": 4, "오": 5, "육": 6, "칠": 7, "팔": 8, "구": 9}


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"cannot read {path}: {exc}") from exc


def normalize_number(token: str) -> str:
    compact = re.sub(r"\s+", "", token).replace(",", "")
    money = re.fullmatch(r"(\d+(?:\.\d+)?)만원", compact)
    if money:
        value = float(money.group(1)) * 10000
        return f"{int(value) if value.is_integer() else value:g}원"
    return compact


def visible_text(text: str) -> str:
    """Return text that remains visible after Markdown HTML comments are removed."""
    return HTML_COMMENT_RE.sub("", text)


def _mask_span(chars: list[str], start: int, end: int) -> None:
    for index in range(start, end):
        chars[index] = " "


def number_claims(text: str) -> Counter[str]:
    """Extract conservative, normalized numeric claims with occurrence counts."""
    material = LIST_MARKER_RE.sub("", visible_text(text))
    chars = list(material)
    claims: Counter[str] = Counter()

    for match in RANGE_RE.finditer(material):
        left, left_unit, right, right_unit = match.groups()
        unit = left_unit or right_unit
        if left_unit and left_unit != right_unit:
            continue
        claims[f"range:{normalize_number(left)}-{normalize_number(right)}{unit}"] += 1
        _mask_span(chars, *match.span())

    remaining = "".join(chars)
    for match in KOREAN_MONEY_RE.finditer(remaining):
        claims[f"{SINO_NUMBERS[match.group(1)] * 10000}원"] += 1
        _mask_span(chars, *match.span())

    remaining = "".join(chars)
    for match in KOREAN_NATIVE_RE.finditer(remaining):
        claims[f"{NATIVE_NUMBERS[match.group(1)]}{match.group(2)}"] += 1
        _mask_span(chars, *match.span())

    remaining = "".join(chars)
    for match in NUMBER_RE.finditer(remaining):
        claims[normalize_number(match.group(0))] += 1
    return claims


def number_tokens(text: str) -> set[str]:
    return set(number_claims(text))


def allowed_number_tokens(brief: dict) -> set[str]:
    material: list[str] = []
    for fact in brief.get("facts", []):
        if isinstance(fact, dict):
            material.append(str(fact.get("text", "")))
    for field in ("allowed_numbers", "required_strings", "protected_strings"):
        material.extend(str(value) for value in brief.get(field, []))
    return number_tokens("\n".join(material))


def normalized_line(value: str) -> str:
    value = value.strip()
    value = re.sub(r"^#{1,6}\s+", "", value)
    value = re.sub(r"\s+#+$", "", value)
    value = re.sub(r"^(?:\*\*|__)(.*)(?:\*\*|__)$", r"\1", value)
    return value.strip()


def section_present(section: object, copy: str) -> bool:
    if isinstance(section, dict):
        label = str(section.get("label", "")).strip()
        kind = section.get("kind")
    else:
        label = str(section).strip()
        kind = None
    if not label:
        return False

    visible = visible_text(copy)
    headings = {normalized_line(match.group(1)) for match in HEADING_RE.finditer(visible)}
    lines = {normalized_line(line) for line in visible.splitlines() if line.strip()}
    if kind == "heading":
        return label in headings
    if kind == "label":
        return label in lines
    return label in headings or label in lines


def structured_ctas(copy: str) -> Counter[str]:
    return Counter(match.group(1).strip() for match in CTA_LINE_RE.finditer(visible_text(copy)))


def validate(brief: dict, copy: str, before: str | None) -> list[str]:
    errors: list[str] = []
    visible_copy = visible_text(copy)

    for field in ("required_strings", "protected_strings"):
        for value in brief.get(field, []):
            if str(value) not in visible_copy:
                errors.append(f"missing {field}: {value!r}")

    for field in ("forbidden_strings", "avoided_terms"):
        for value in brief.get(field, []):
            if str(value) in visible_copy:
                errors.append(f"found {field}: {value!r}")

    for section in brief.get("required_sections", []):
        if not section_present(section, copy):
            errors.append(f"missing required section: {section!r}")

    primary_action = brief.get("primary_action")
    if isinstance(primary_action, str) and primary_action.strip() and primary_action not in visible_copy:
        errors.append(f"missing primary_action: {primary_action!r}")

    if brief.get("channel") == "email" and brief.get("delivery_format") == "subject_body":
        if not SUBJECT_LINE_RE.search(visible_copy):
            errors.append("missing email subject line: use '제목:' or 'Subject:'")

    copy_claims = number_claims(copy)
    copy_numbers = set(copy_claims)
    allowed_numbers = allowed_number_tokens(brief)
    for token in sorted(copy_numbers - allowed_numbers):
        errors.append(f"new numeric/date token not in fact ledger: {token!r}")

    allowed_ctas = {str(value) for value in brief.get("allowed_cta_labels", [])}
    found_ctas = structured_ctas(copy)
    cta_contract_enabled = "allowed_cta_labels" in brief or "max_cta_types" in brief
    if cta_contract_enabled and not found_ctas:
        errors.append(
            "CTA contract enabled but no structured CTA slot found; "
            "use a standalone [label] or [label](url) line"
        )
    if "allowed_cta_labels" in brief:
        for value in sorted(set(found_ctas) - allowed_ctas):
            errors.append(f"CTA label not in allowed_cta_labels: {value!r}")
    max_cta = brief.get("max_cta_types")
    if isinstance(max_cta, int) and len(found_ctas) > max_cta:
        errors.append(
            f"CTA types exceed max_cta_types: {len(found_ctas)} > {max_cta}"
        )

    if before is not None:
        visible_before = visible_text(before)
        for value in brief.get("protected_strings", []):
            value = str(value)
            if value in visible_before and value not in visible_copy:
                errors.append(f"protected string lost after rewrite: {value!r}")
        before_claims = number_claims(before)
        introduced = set(copy_claims) - set(before_claims) - allowed_numbers
        for token in sorted(introduced):
            errors.append(f"numeric/date token introduced after rewrite: {token!r}")
        for token, count in sorted((before_claims - copy_claims).items()):
            errors.append(f"numeric/date claim lost after rewrite: {token!r} x{count}")
        for token, count in sorted((copy_claims - before_claims).items()):
            if token not in introduced:
                errors.append(f"numeric/date claim count increased after rewrite: {token!r} x{count}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--brief", type=Path, required=True)
    parser.add_argument("--copy", dest="copy_path", type=Path, required=True)
    parser.add_argument("--before", type=Path)
    args = parser.parse_args()

    try:
        brief = json.loads(read_text(args.brief))
        copy = read_text(args.copy_path)
        before = read_text(args.before) if args.before else None
        errors = validate(brief, copy, before)
    except (ValueError, json.JSONDecodeError) as exc:
        errors = [str(exc)]
        brief = {}
        copy = ""

    if errors:
        print("COPY_INVALID")
        for error in errors:
            print(f"- {error}")
        return 1

    print(
        "COPY_OK "
        f"required={len(brief.get('required_strings', []))} "
        f"protected={len(brief.get('protected_strings', []))} "
        f"numbers={sum(number_claims(copy).values())}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
