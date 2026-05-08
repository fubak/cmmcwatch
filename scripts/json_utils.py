#!/usr/bin/env python3
"""
Shared helpers for parsing JSON from LLM output.

LLM responses often contain malformed JSON: trailing commas, missing commas
between fields, embedded control characters, truncated structures.
This module centralizes the repair-and-parse strategies used by both
editorial_generator and generate_design.
"""

import json
import re
from typing import Optional

try:
    from config import setup_logging
except ImportError:
    from scripts.config import setup_logging

logger = setup_logging("pipeline")


def repair_json(json_str: str) -> str:
    """
    Attempt to repair common JSON formatting issues from LLM output.

    Handles: missing commas between elements, trailing commas, truncated
    structures (auto-closes open braces/brackets/strings).
    """
    # Fix missing commas between adjacent elements
    json_str = re.sub(r'"\s*\n\s*"', '",\n"', json_str)
    json_str = re.sub(r"}\s*\n\s*{", "},\n{", json_str)
    json_str = re.sub(r"]\s*\n\s*\[", "],\n[", json_str)
    json_str = re.sub(r'"\s*\n\s*{', '",\n{', json_str)
    json_str = re.sub(r'}\s*\n\s*"', '},\n"', json_str)
    json_str = re.sub(r'"\s*\n\s*\[', '",\n[', json_str)
    json_str = re.sub(r']\s*\n\s*"', '],\n"', json_str)

    # Fix missing comma after value before next key
    json_str = re.sub(r'"\s+("[\w]+"\s*:)', r'", \1', json_str)

    # Fix trailing commas before closing brackets
    json_str = re.sub(r",\s*}", "}", json_str)
    json_str = re.sub(r",\s*]", "]", json_str)

    # Handle truncated JSON by closing open structures
    open_braces = json_str.count("{") - json_str.count("}")
    open_brackets = json_str.count("[") - json_str.count("]")

    # If we appear to be mid-string (unclosed quotes), close it
    stripped = json_str.rstrip()
    if stripped and stripped[-1] not in '}"]':
        if open_braces > 0 or open_brackets > 0:
            quote_count = 0
            i = len(stripped) - 1
            while i >= 0:
                if stripped[i] == '"' and (i == 0 or stripped[i - 1] != "\\"):
                    quote_count += 1
                    if quote_count == 1:
                        break
                i -= 1
            if quote_count % 2 == 1:
                json_str = stripped + '"'

    # Re-count after potential string closure and close remaining structures
    open_braces = json_str.count("{") - json_str.count("}")
    open_brackets = json_str.count("[") - json_str.count("]")

    if open_brackets > 0:
        json_str = json_str.rstrip()
        if json_str.endswith(","):
            json_str = json_str[:-1]
        json_str += "]" * open_brackets

    if open_braces > 0:
        json_str = json_str.rstrip()
        if json_str.endswith(","):
            json_str = json_str[:-1]
        json_str += "}" * open_braces

    return json_str


def _escape_string_contents_match(match):
    """Escape control characters inside a quoted JSON string match."""
    s = match.group(0)
    inner = s[1:-1]  # strip quotes
    inner = inner.replace("\n", "\\n")
    inner = inner.replace("\r", "\\r")
    inner = inner.replace("\t", "\\t")
    inner = re.sub(
        r"[\x00-\x08\x0b\x0c\x0e-\x1f]",
        lambda m: f"\\u{ord(m.group()):04x}",
        inner,
    )
    return f'"{inner}"'


def escape_control_chars_in_strings(json_str: str) -> str:
    """
    Escape raw control characters that appear inside JSON string values.

    Preserves structural whitespace outside strings. Used as a fallback
    when LLMs emit literal newlines/tabs inside string values.
    """
    return re.sub(r'"(?:[^"\\]|\\.)*"', _escape_string_contents_match, json_str)


def parse_llm_json(response: Optional[str], require_object: bool = True) -> Optional[dict]:
    """
    Parse JSON from an LLM response with progressive repair strategies.

    1. Find the first {...} block (or use the whole response).
    2. Try parsing as-is.
    3. Try repair_json (commas, trailing commas, truncation).
    4. Try escape_control_chars_in_strings.
    5. Try repair + escape combination.
    6. Last resort: strip all control characters and re-repair.

    Returns the parsed dict, or None if all strategies fail.
    """
    if not response:
        return None

    if require_object:
        json_match = re.search(r"\{.*\}", response, re.DOTALL)
        payload = json_match.group() if json_match else response
    else:
        payload = response

    # Strategy 1: as-is
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        pass

    # Strategy 2: repair
    try:
        return json.loads(repair_json(payload))
    except json.JSONDecodeError:
        pass

    # Strategy 3: escape control chars in strings
    try:
        return json.loads(escape_control_chars_in_strings(payload))
    except json.JSONDecodeError:
        pass

    # Strategy 4: repair + escape
    try:
        return json.loads(escape_control_chars_in_strings(repair_json(payload)))
    except json.JSONDecodeError:
        pass

    # Strategy 5: brute-strip all control chars then repair
    try:
        stripped = re.sub(r"[\x00-\x09\x0b\x0c\x0e-\x1f]", " ", payload)
        return json.loads(repair_json(stripped))
    except json.JSONDecodeError as e:
        logger.warning(f"JSON parse exhausted all strategies: {e}")
        return None
