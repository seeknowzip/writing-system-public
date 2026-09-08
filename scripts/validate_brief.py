#!/usr/bin/env python3
"""Validate the deterministic input contract for writing-system."""

from __future__ import annotations

import argparse
from datetime import date
import json
import sys
from pathlib import Path


GENRES = {
    "landing",
    "marketing",
    "social",
    "editorial",
    "guide",
    "faq",
    "notice",
    "press",
    "ui",
}
CHANNEL_FORMATS = {
    "email": {"subject_body"},
    "app": {"app_notice", "ui_copy"},
    "web": {"landing_page", "help_article", "article", "web_notice", "ui_copy"},
    "instagram": {"caption"},
    "linkedin": {"post"},
    "blog": {"article"},
    "press_wire": {"press_release"},
}
REQUIRED_TEXT = (
    "genre",
    "channel",
    "delivery_format",
    "audience",
    "situation",
    "purpose",
    "primary_action",
)
LIST_FIELDS = (
    "facts",
    "required_strings",
    "protected_strings",
    "forbidden_strings",
)
OPTIONAL_LIST_FIELDS = (
    "allowed_numbers",
    "avoided_terms",
    "allowed_cta_labels",
    "required_sections",
    "human_review",
    "compliance_triggers",
)
COMPLIANCE_TRIGGERS = {"advertising", "payment", "personal_data", "incident", "regulated"}
COMPLIANCE_SOURCE_FIELDS = ("source_ref", "version", "approved_by", "checked_at")
OPTIONAL_CREATIVE_TEXT = ("reader_tension", "positioning")


def load_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("brief root must be an object")
    return data


def validate(data: dict) -> list[str]:
    errors: list[str] = []
    if "allowed_terms" in data:
        errors.append(
            "allowed_terms: unsupported because free-form copy has no deterministic "
            "closed vocabulary; use protected_strings or avoided_terms"
        )
    for field in REQUIRED_TEXT:
        value = data.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{field}: non-empty string required")

    if data.get("genre") not in GENRES:
        errors.append(f"genre: must be one of {', '.join(sorted(GENRES))}")

    channel = data.get("channel")
    delivery_format = data.get("delivery_format")
    if channel not in CHANNEL_FORMATS:
        errors.append(f"channel: must be one of {', '.join(sorted(CHANNEL_FORMATS))}")
    elif delivery_format not in CHANNEL_FORMATS[channel]:
        allowed = ", ".join(sorted(CHANNEL_FORMATS[channel]))
        errors.append(
            f"delivery_format: {delivery_format!r} is not valid for {channel!r}; "
            f"expected one of {allowed}"
        )

    for field in LIST_FIELDS:
        if field not in data:
            errors.append(f"{field}: required field (use an empty list when none)")
        elif not isinstance(data[field], list):
            errors.append(f"{field}: must be a list")

    for field in OPTIONAL_LIST_FIELDS:
        if field in data and not isinstance(data[field], list):
            errors.append(f"{field}: must be a list")

    facts = data.get("facts", [])
    if isinstance(facts, list):
        for index, fact in enumerate(facts):
            prefix = f"facts[{index}]"
            if not isinstance(fact, dict):
                errors.append(f"{prefix}: must be an object")
                continue
            if not isinstance(fact.get("text"), str) or not fact["text"].strip():
                errors.append(f"{prefix}.text: non-empty string required")
            source_ok = isinstance(fact.get("source"), str) and fact["source"].strip()
            if not source_ok and fact.get("assumption") is not True:
                errors.append(f"{prefix}: source required unless assumption is true")

    for field in (*LIST_FIELDS[1:], *(item for item in OPTIONAL_LIST_FIELDS if item != "required_sections")):
        values = data.get(field, [])
        if not isinstance(values, list):
            continue
        for index, value in enumerate(values):
            if not isinstance(value, (str, int, float)) or str(value).strip() == "":
                errors.append(f"{field}[{index}]: non-empty scalar required")

    sections = data.get("required_sections", [])
    if isinstance(sections, list):
        for index, section in enumerate(sections):
            prefix = f"required_sections[{index}]"
            if isinstance(section, str) and section.strip():
                continue
            if not isinstance(section, dict):
                errors.append(f"{prefix}: non-empty string or object required")
                continue
            label = section.get("label")
            kind = section.get("kind")
            if not isinstance(label, str) or not label.strip():
                errors.append(f"{prefix}.label: non-empty string required")
            if kind not in {"heading", "label"}:
                errors.append(f"{prefix}.kind: must be 'heading' or 'label'")

    voice = data.get("voice")
    if not isinstance(voice, dict):
        errors.append("voice: object required")
    elif not isinstance(voice.get("register"), str) or not voice["register"].strip():
        errors.append("voice.register: non-empty string required")
    elif "rules" in voice:
        if not isinstance(voice["rules"], list):
            errors.append("voice.rules: must be a list")
        elif any(not isinstance(rule, str) or not rule.strip() for rule in voice["rules"]):
            errors.append("voice.rules: list of non-empty strings required")

    for field in OPTIONAL_CREATIVE_TEXT:
        value = data.get(field)
        if value is not None and (not isinstance(value, str) or not value.strip()):
            errors.append(f"{field}: non-empty string or null required")

    customer_language = data.get("customer_language")
    if customer_language is not None:
        if not isinstance(customer_language, list):
            errors.append("customer_language: must be a list or null")
        else:
            for index, phrase in enumerate(customer_language):
                prefix = f"customer_language[{index}]"
                if not isinstance(phrase, dict):
                    errors.append(f"{prefix}: object required")
                    continue
                for field in ("text", "source"):
                    value = phrase.get(field)
                    if not isinstance(value, str) or not value.strip():
                        errors.append(f"{prefix}.{field}: non-empty string required")

    max_cta = data.get("max_cta_types")
    if max_cta is not None and (not isinstance(max_cta, int) or max_cta < 0):
        errors.append("max_cta_types: non-negative integer required")

    triggers = data.get("compliance_triggers", [])
    if isinstance(triggers, list):
        for index, trigger in enumerate(triggers):
            if trigger not in COMPLIANCE_TRIGGERS:
                errors.append(f"compliance_triggers[{index}]: unknown trigger {trigger!r}")
    else:
        triggers = []
    source = data.get("compliance_source")
    if triggers and not isinstance(source, dict):
        errors.append("compliance_source: object required when compliance_triggers is not empty")
    if isinstance(source, dict):
        for field in COMPLIANCE_SOURCE_FIELDS:
            value = source.get(field)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"compliance_source.{field}: non-empty string required")
        checked_at = source.get("checked_at")
        if isinstance(checked_at, str) and checked_at.strip():
            try:
                date.fromisoformat(checked_at)
            except ValueError:
                errors.append("compliance_source.checked_at: YYYY-MM-DD required")
    elif source not in (None, ""):
        errors.append("compliance_source: must be an object or null")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("brief", type=Path)
    args = parser.parse_args()

    try:
        data = load_json(args.brief)
        errors = validate(data)
    except ValueError as exc:
        errors = [str(exc)]

    if errors:
        print("BRIEF_INVALID")
        for error in errors:
            print(f"- {error}")
        return 1

    print(f"BRIEF_OK genre={data['genre']} facts={len(data['facts'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
