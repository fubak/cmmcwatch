#!/usr/bin/env python3
"""WCAG color-contrast utilities for CMMC Watch.

Pure functions (hex parsing + WCAG 2.1 relative-luminance / contrast-ratio math)
extracted from generate_design.py so they can be reused and unit-tested in
isolation. WCAG AA requires a 4.5:1 contrast ratio for normal text.
"""


def hex_to_rgb(hex_color: str) -> tuple:
    """Convert hex color to RGB tuple."""
    hex_color = hex_color.lstrip("#")
    if len(hex_color) == 3:
        hex_color = "".join([c * 2 for c in hex_color])
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))


def get_relative_luminance(rgb: tuple) -> float:
    """Calculate relative luminance per WCAG 2.1 specification."""

    def channel_luminance(c):
        c = c / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = rgb
    return 0.2126 * channel_luminance(r) + 0.7152 * channel_luminance(g) + 0.0722 * channel_luminance(b)


def calculate_contrast_ratio(color1: str, color2: str) -> float:
    """Calculate WCAG contrast ratio between two hex colors."""
    try:
        lum1 = get_relative_luminance(hex_to_rgb(color1))
        lum2 = get_relative_luminance(hex_to_rgb(color2))
        lighter = max(lum1, lum2)
        darker = min(lum1, lum2)
        return (lighter + 0.05) / (darker + 0.05)
    except (ValueError, TypeError):
        return 1.0  # Return lowest ratio if calculation fails


def validate_color_contrast(text_color: str, bg_color: str, min_ratio: float = 4.5) -> bool:
    """Check if text color has sufficient contrast against background (WCAG AA)."""
    ratio = calculate_contrast_ratio(text_color, bg_color)
    return ratio >= min_ratio


def adjust_color_for_contrast(text_color: str, bg_color: str, min_ratio: float = 4.5) -> str:
    """Adjust text color to meet minimum contrast ratio if needed."""
    if validate_color_contrast(text_color, bg_color, min_ratio):
        return text_color

    # Determine if background is light or dark
    bg_lum = get_relative_luminance(hex_to_rgb(bg_color))

    # Use white or black based on background luminance
    if bg_lum > 0.5:
        return "#1a1a1a"  # Dark text for light backgrounds
    else:
        return "#ffffff"  # Light text for dark backgrounds
