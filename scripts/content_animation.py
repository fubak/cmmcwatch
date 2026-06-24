#!/usr/bin/env python3
"""Content-aware animation selection for CMMC Watch.

Pure helpers extracted from generate_design.py: infer a coarse sentiment label
from the day's trends/keywords, then map it to an animation intensity balanced
against the design's base animation preference.
"""

SENTIMENT_ANIMATION_MAP = {
    "breaking": "moderate",  # Breaking news: moderate activity
    "urgent": "moderate",  # Urgent news: attention-grabbing
    "positive": "playful",  # Good news: celebratory
    "negative": "subtle",  # Serious news: restrained
    "neutral": "subtle",  # Normal: balanced
    "tech": "moderate",  # Tech news: modern feel
    "entertainment": "playful",  # Entertainment: fun
}


def analyze_content_sentiment(trends: list, keywords: list) -> str:
    """Analyze content to determine appropriate animation intensity."""
    # Keywords that suggest different sentiments
    breaking_words = ["breaking", "just in", "urgent", "developing", "alert"]
    positive_words = [
        "success",
        "breakthrough",
        "wins",
        "celebrates",
        "achieves",
        "record",
    ]
    negative_words = [
        "crisis",
        "disaster",
        "death",
        "crash",
        "fails",
        "warning",
        "threat",
    ]
    entertainment_words = [
        "movie",
        "music",
        "celebrity",
        "game",
        "sports",
        "entertainment",
    ]

    # Count occurrences - handle None values safely
    text_parts = []
    for t in trends:
        title = t.get("title") or ""
        description = t.get("description") or ""
        text_parts.append(f"{title} {description}")
    text = " ".join(text_parts).lower()
    text += " " + " ".join(k for k in keywords if k).lower()

    breaking_count = sum(1 for w in breaking_words if w in text)
    positive_count = sum(1 for w in positive_words if w in text)
    negative_count = sum(1 for w in negative_words if w in text)
    entertainment_count = sum(1 for w in entertainment_words if w in text)

    # Determine dominant sentiment
    if breaking_count >= 2:
        return "breaking"
    if entertainment_count >= 3:
        return "entertainment"
    if positive_count > negative_count and positive_count >= 2:
        return "positive"
    if negative_count > positive_count and negative_count >= 2:
        return "negative"

    return "neutral"


def get_content_aware_animation(trends: list, keywords: list, base_animation: str) -> str:
    """Get animation level adjusted for content sentiment."""
    sentiment = analyze_content_sentiment(trends, keywords)
    suggested = SENTIMENT_ANIMATION_MAP.get(sentiment, "subtle")

    # Balance between personality preference and content sentiment
    animation_levels = ["none", "subtle", "moderate", "playful", "energetic"]
    base_idx = animation_levels.index(base_animation) if base_animation in animation_levels else 1
    suggested_idx = animation_levels.index(suggested) if suggested in animation_levels else 1

    # Average the two, rounding toward the suggested
    final_idx = (base_idx + suggested_idx + 1) // 2
    return animation_levels[min(final_idx, len(animation_levels) - 1)]
