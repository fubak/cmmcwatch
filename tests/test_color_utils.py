#!/usr/bin/env python3
"""Unit tests for the WCAG color-contrast utilities.

These encode *why* the math matters: WCAG 2.1 defines a max contrast ratio of
21:1 (pure black on white), a min of 1:1 (a color against itself), and AA
requires >= 4.5:1 for normal text. A regression in the luminance/ratio formula
or the auto-adjust fallback fails here.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from color_utils import (
    adjust_color_for_contrast,
    calculate_contrast_ratio,
    hex_to_rgb,
    validate_color_contrast,
)


def test_hex_to_rgb_full_shorthand_and_no_hash():
    assert hex_to_rgb("#ffffff") == (255, 255, 255)
    assert hex_to_rgb("000000") == (0, 0, 0)
    assert hex_to_rgb("#fff") == (255, 255, 255)  # 3-digit shorthand expands


def test_contrast_black_on_white_is_wcag_max():
    assert round(calculate_contrast_ratio("#000000", "#ffffff"), 1) == 21.0


def test_contrast_of_a_color_against_itself_is_one():
    assert round(calculate_contrast_ratio("#777777", "#777777"), 2) == 1.0


def test_contrast_is_symmetric():
    assert calculate_contrast_ratio("#123456", "#abcdef") == calculate_contrast_ratio("#abcdef", "#123456")


def test_contrast_bad_input_returns_safe_floor_not_raise():
    assert calculate_contrast_ratio("not-a-color", "#ffffff") == 1.0


def test_validate_aa_threshold():
    assert validate_color_contrast("#000000", "#ffffff") is True  # 21:1 passes AA
    assert validate_color_contrast("#cccccc", "#ffffff") is False  # too low


def test_adjust_keeps_color_when_already_passing():
    assert adjust_color_for_contrast("#000000", "#ffffff") == "#000000"


def test_adjust_picks_dark_text_on_light_background():
    assert adjust_color_for_contrast("#eeeeee", "#ffffff") == "#1a1a1a"


def test_adjust_picks_light_text_on_dark_background():
    assert adjust_color_for_contrast("#222222", "#000000") == "#ffffff"
