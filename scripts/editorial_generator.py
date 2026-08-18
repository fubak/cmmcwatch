#!/usr/bin/env python3
"""
Editorial Article Generator for CMMC Watch

Generates AI-written editorial articles that synthesize top stories into
cohesive narratives. Articles are permanently retained (not archived).

URL Structure: /articles/YYYY/MM/DD/slug/index.html
"""

import json
import os
import re
import tempfile
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import requests

# Site configuration
SITE_NAME = "CMMC Watch"
SITE_URL = "https://cmmcwatch.com"

try:
    from ai_providers import (
        call_google_ai,
        call_huggingface,
        call_ollama,
        call_openai_compatible,
    )
    from article_renderer import render_article_html
    from articles_index_renderer import render_articles_index
    from config import setup_logging
    from json_utils import parse_llm_json, repair_json
    from rate_limiter import (
        check_before_call,
        get_rate_limiter,
        mark_provider_exhausted,
    )
except ImportError:
    from scripts.ai_providers import (
        call_google_ai,
        call_huggingface,
        call_ollama,
        call_openai_compatible,
    )
    from scripts.article_renderer import render_article_html
    from scripts.articles_index_renderer import render_articles_index
    from scripts.config import setup_logging
    from scripts.json_utils import parse_llm_json, repair_json
    from scripts.rate_limiter import (
        check_before_call,
        get_rate_limiter,
        mark_provider_exhausted,
    )

logger = setup_logging("pipeline")

# JSON Schemas for Gemini Structured Outputs
EDITORIAL_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "description": "Compelling headline (6-12 words)"},
        "slug": {"type": "string", "description": "URL-friendly slug with dashes"},
        "summary": {
            "type": "string",
            "description": "1-2 sentence meta description for SEO",
        },
        "mood": {
            "type": "string",
            "description": "One word describing tone (hopeful, concerned, transformative, etc.)",
        },
        "content": {
            "type": "string",
            "description": "Full article content with HTML formatting",
        },
        "key_themes": {
            "type": "array",
            "items": {"type": "string"},
            "description": "3-5 key themes",
        },
        "predictions": {
            "type": "array",
            "items": {"type": "string"},
            "description": "2-3 specific predictions",
        },
    },
    "required": ["title", "slug", "summary", "mood", "content", "key_themes"],
}

BRIEF_SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {
            "type": "string",
            "description": "Punchy 4-9 word headline for the day's brief",
        },
        "dek": {
            "type": "string",
            "description": "One-sentence standfirst summarizing the day",
        },
        "bullets": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "One-sentence takeaway (no HTML)",
                    },
                    "story_index": {
                        "type": "integer",
                        "description": "0-based index of the source story this bullet is about",
                    },
                },
                "required": ["text", "story_index"],
            },
            "description": "3-5 'what matters today' bullets",
        },
        "op_ed_paragraphs": {
            "type": "array",
            "items": {"type": "string"},
            "description": "2-4 short analysis paragraphs (plain text, no HTML)",
        },
    },
    "required": ["headline", "bullets", "op_ed_paragraphs"],
}

STORY_SUMMARIES_SCHEMA = {
    "type": "object",
    "properties": {
        "stories": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "explanation": {
                        "type": "string",
                        "description": "2-3 sentence explanation of why this matters",
                    },
                    "impact_areas": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Areas of impact",
                    },
                },
                "required": ["explanation"],
            },
        }
    },
    "required": ["stories"],
}


@dataclass
class EditorialArticle:
    """Represents a generated editorial article."""

    title: str
    slug: str
    date: str  # YYYY-MM-DD
    summary: str  # 1-2 sentence summary for meta description
    content: str  # Full HTML content
    word_count: int
    top_stories: List[str]  # Titles of stories synthesized
    keywords: List[str]
    mood: str  # Overall mood/tone of the article
    url: str  # Full URL path


@dataclass
class BriefBullet:
    """A single 'what matters today' bullet linked to its source story."""

    text: str
    source_name: str
    source_url: str
    source_title: str


@dataclass
class FrontPageBrief:
    """Executive brief that leads the front page: sourced bullets + short op-ed."""

    headline: str
    dek: str  # one-line standfirst under the headline
    bullets: List[BriefBullet]
    op_ed_paragraphs: List[str]  # plain text, rendered escaped in <p> tags
    date: str  # YYYY-MM-DD


@dataclass
class WhyThisMatters:
    """Context explanation for a top story."""

    story_title: str
    story_url: str
    explanation: str  # 2-3 sentence explanation
    impact_areas: List[str]  # e.g., ["technology", "privacy", "business"]


class EditorialGenerator:
    """
    Generates editorial articles and 'Why This Matters' context.

    Uses Groq API for AI-powered content generation with rich context.
    """

    # Rate limiting: minimum seconds between API calls to stay under 30 req/min
    MIN_CALL_INTERVAL = 3.0
    MAX_RETRY_WAIT = 10  # Cap retry waits to prevent long delays

    def __init__(
        self,
        groq_key: Optional[str] = None,
        openrouter_key: Optional[str] = None,
        google_key: Optional[str] = None,
        public_dir: Optional[Path] = None,
        ollama_url: Optional[str] = None,
    ):
        self.groq_key = groq_key or os.getenv("GROQ_API_KEY")
        self.openrouter_key = openrouter_key or os.getenv("OPENROUTER_API_KEY")
        self.google_key = google_key or os.getenv("GOOGLE_AI_API_KEY")
        self.ollama_url = ollama_url or os.getenv("OLLAMA_URL", "http://localhost:11434")
        self.public_dir = public_dir or Path(__file__).parent.parent / "public"
        self.articles_dir = self.public_dir / "articles"
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "CMMC Watch/1.0 (Editorial Generator)"})
        self._last_call_time = 0.0  # Track last API call for rate limiting

    def _get_design_tokens(self, design: Optional[Dict]) -> Dict:
        """Normalize design tokens for editorial templates."""
        tokens = {
            "primary_color": "#667eea",
            "accent_color": "#4facfe",
            "bg_color": "#0f0f23",
            "text_color": "#ffffff",
            "muted_color": "#a1a1aa",
            "border_color": "#27272a",
            "card_bg": "rgba(255,255,255,0.03)",
            "font_primary": "Playfair Display",
            "font_secondary": "Inter",
            "radius": "1rem",
            "transition": "200ms",
            "base_mode": "dark-mode",
        }

        if not design:
            return tokens

        tokens.update(
            {
                "primary_color": design.get("color_accent", tokens["primary_color"]),
                "accent_color": design.get("color_accent_secondary", tokens["accent_color"]),
                "bg_color": design.get("color_bg", tokens["bg_color"]),
                "text_color": design.get("color_text", tokens["text_color"]),
                "muted_color": design.get("color_muted", tokens["muted_color"]),
                "border_color": design.get("color_border", tokens["border_color"]),
                "card_bg": design.get("color_card_bg", tokens["card_bg"]),
                "font_primary": design.get("font_primary", tokens["font_primary"]),
                "font_secondary": design.get("font_secondary", tokens["font_secondary"]),
                "radius": design.get("card_radius", tokens["radius"]),
                "transition": design.get("transition_speed", tokens["transition"]),
                "base_mode": ("dark-mode" if design.get("is_dark_mode", True) else "light-mode"),
            }
        )

        return tokens

    def generate_front_page_brief(
        self, trends: List[Dict], keywords: List[str], design: Optional[Dict] = None
    ) -> FrontPageBrief:
        """
        Generate the executive brief that leads the front page.

        Produces a headline, a one-line dek, 3-5 sourced takeaway bullets, and
        2-4 short op-ed paragraphs. Bullets reference source stories by index so
        their links are always real (never hallucinated).

        Always returns a FrontPageBrief: if no AI provider is available or the
        call fails, a deterministic fallback built from the top stories is used.
        """
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")
        top_stories = [t for t in trends if t.get("title") and t.get("url")][:10]

        if len(top_stories) < 3:
            logger.warning("BRIEF: fewer than 3 usable stories, using fallback")
            return self._fallback_brief(top_stories, today)

        has_ollama = self._check_ollama_available()
        if not (has_ollama or self.groq_key or self.openrouter_key or self.google_key):
            logger.info("BRIEF: no AI provider configured, using fallback brief")
            return self._fallback_brief(top_stories, today)

        numbered = "\n".join(
            f"{i}. [{(s.get('source') or 'unknown').replace('_', ' ').title()}] {s.get('title')}"
            + (f"\n   Summary: {(s.get('description') or '')[:200]}" if s.get("description") else "")
            for i, s in enumerate(top_stories)
        )

        prompt = f"""## ROLE
You are the executive editor of CMMC Watch, writing the daily front-page brief read by
defense contractors, compliance officers, and CISOs. Be sharp, specific, and useful.

## TODAY'S STORIES (cite by index)
{numbered}

TRENDING KEYWORDS: {", ".join(keywords[:15])}
DATE: {now.strftime("%B %d, %Y")}

## TASK
1. Write 3-5 "what matters today" bullets. Each bullet is ONE plain-text sentence and
   MUST set "story_index" to the 0-based index of the story it summarizes.
2. Write a punchy 4-9 word "headline" and a one-sentence "dek".
3. Write 2-4 short op-ed paragraphs (plain text, no HTML) that synthesize the day's
   stories into a clear point of view — connect threads, name the stakes, take a stance.

## RULES
- Ground every claim in the stories above; do not invent facts or sources.
- Plain text only (no HTML, no markdown). Keep bullets scannable.
- Each bullet's story_index must be a valid index from the list above.

Respond with ONLY a valid JSON object:
{{
  "headline": "4-9 word headline",
  "dek": "one-sentence standfirst",
  "bullets": [{{"text": "one sentence", "story_index": 0}}],
  "op_ed_paragraphs": ["paragraph one", "paragraph two"]
}}"""

        try:
            data = self._call_google_ai_structured(prompt, BRIEF_SCHEMA, max_tokens=4096)
            if not data:
                response = self._call_groq(prompt, max_tokens=4096)
                data = self._parse_json_response(response)

            if not data or not data.get("bullets"):
                logger.warning("BRIEF: AI returned no bullets, using fallback")
                return self._fallback_brief(top_stories, today)

            bullets = []
            for raw in data.get("bullets", []):
                text = (raw.get("text") or "").strip()
                if not text:
                    continue
                idx = raw.get("story_index")
                story = top_stories[idx] if isinstance(idx, int) and 0 <= idx < len(top_stories) else None
                if story is None:
                    continue
                bullets.append(
                    BriefBullet(
                        text=text,
                        source_name=(story.get("source") or "").replace("_", " ").title(),
                        source_url=story.get("url", ""),
                        source_title=story.get("title", ""),
                    )
                )

            if not bullets:
                logger.warning("BRIEF: no valid bullets after mapping, using fallback")
                return self._fallback_brief(top_stories, today)

            # Keep the front page stable regardless of how many items the model returns
            bullets = bullets[:5]
            op_ed = [p.strip() for p in (data.get("op_ed_paragraphs") or []) if p and p.strip()][:4]

            logger.info(f"BRIEF: generated {len(bullets)} bullets, {len(op_ed)} op-ed paragraphs")
            return FrontPageBrief(
                headline=(data.get("headline") or "Today in CMMC & Compliance").strip(),
                dek=(data.get("dek") or "").strip(),
                bullets=bullets,
                op_ed_paragraphs=op_ed,
                date=today,
            )
        except Exception:
            logger.exception("BRIEF: generation failed, using fallback")
            return self._fallback_brief(top_stories, today)

    def _fallback_brief(self, stories: List[Dict], date: str) -> FrontPageBrief:
        """Deterministic brief from the top stories (no AI).

        Bullets are built from stories that have both a title and URL, so the
        list is empty only when no usable stories are provided (callers should
        not assume at least one bullet).
        """
        bullets = [
            BriefBullet(
                text=s.get("title", ""),
                source_name=(s.get("source") or "").replace("_", " ").title(),
                source_url=s.get("url", ""),
                source_title=s.get("title", ""),
            )
            for s in stories[:5]
            if s.get("title") and s.get("url")
        ]
        return FrontPageBrief(
            headline="Today in CMMC & Compliance",
            dek="The day's most important compliance and Defense Industrial Base news.",
            bullets=bullets,
            op_ed_paragraphs=[],
            date=date,
        )

    def generate_editorial(
        self, trends: List[Dict], keywords: List[str], design: Optional[Dict] = None
    ) -> Optional[EditorialArticle]:
        """
        Generate a daily editorial article synthesizing top stories.

        Args:
            trends: List of trend dictionaries
            keywords: Extracted keywords
            design: Current design spec for styling

        Returns:
            EditorialArticle if successful, None otherwise
        """
        # Check if at least one AI provider is available
        has_ollama = self._check_ollama_available()
        has_api_keys = self.groq_key or self.openrouter_key or self.google_key
        if not has_ollama and not has_api_keys:
            logger.error("ARTICLE GENERATION FAILED: No AI provider available (no API keys configured)")
            return None

        if len(trends) < 3:
            logger.error(f"ARTICLE GENERATION FAILED: Insufficient trends ({len(trends)} found, need at least 3)")
            return None

        # Check if an article for today already exists (prevent duplicates)
        today = datetime.now().strftime("%Y-%m-%d")
        today_parts = today.split("-")
        today_dir = self.articles_dir / today_parts[0] / today_parts[1] / today_parts[2]
        if today_dir.exists() and any(today_dir.iterdir()):
            existing_articles = list(today_dir.glob("*/metadata.json"))
            if existing_articles:
                try:
                    metadata_path = existing_articles[0]
                    with open(metadata_path, encoding="utf-8") as f:
                        metadata = json.load(f)

                    # Check if existing article is truncated (missing Conclusion)
                    html_path = metadata_path.parent / "index.html"
                    is_truncated = False
                    if html_path.exists():
                        html_content = html_path.read_text(encoding="utf-8")
                        if "Conclusion" not in html_content:
                            is_truncated = True

                    if not is_truncated:
                        logger.info(f"Loading existing editorial for {today}: {metadata.get('title', 'Unknown')}")
                        return EditorialArticle(
                            title=metadata.get("title", ""),
                            slug=metadata.get("slug", ""),
                            date=metadata.get("date", today),
                            summary=metadata.get("summary", ""),
                            content="",  # Content not needed for display card
                            word_count=metadata.get("word_count", 0),
                            top_stories=metadata.get("top_stories", []),
                            keywords=metadata.get("keywords", []),
                            mood=metadata.get("mood", "informative"),
                            url=metadata.get("url", ""),
                        )

                    # Truncated article — remove and regenerate
                    import shutil

                    logger.warning("Existing article is truncated (missing Conclusion), regenerating")
                    shutil.rmtree(metadata_path.parent)

                except Exception as e:
                    logger.warning(f"Failed to load existing article: {e}; generating a new one")

        # Build rich context from top stories
        top_stories = trends[:8]
        context = self._build_editorial_context(top_stories, keywords)

        # Extract a central question from the top stories
        central_themes = self._identify_central_themes(top_stories, keywords)

        prompt = f"""## ROLE
You're a senior editorial writer for CMMC Watch, known for combining factual rigor with a whimsical, memorable voice. Your writing is:
- Evidence-based but never dry
- Structured but not formulaic
- Insightful but accessible
- Memorable without being gimmicky

## TASK
Write a concise daily editorial article (strictly 400-500 words) that synthesizes today's top trending stories into a cohesive narrative, analyzes patterns and connections, and provides actionable insights. You MUST stay under 500 words.

{context}

## CENTRAL QUESTION/THESIS
Based on these stories, address this central theme: {central_themes["question"]}

Your thesis should take a clear stance on this question and defend it throughout the piece.

## SCOPE & BOUNDARIES
- Focus on the intersection of these stories and what they reveal about broader trends
- Do NOT simply summarize each story - synthesize and analyze
- Stay grounded in the evidence from today's stories
- Make specific, falsifiable claims rather than vague assertions
- Don't claim you don't know things, just use the context provided

## EVIDENCE REQUIREMENTS
- Reference specific stories from the provided list to support claims
- For each major claim, cite which story/stories provide evidence
- Distinguish between direct evidence, reasonable inference, and speculation
- If making predictions, state the confidence level and reasoning

## REQUIRED STRUCTURE (use these as <h2> sections):
Keep each section tight — 1 short paragraph each. Total MUST be 400-500 words.

1. **The Lead** (2-3 sentences) — Hook with a surprising connection, state thesis
2. **What People Think** (2-3 sentences) — Steelman the conventional wisdom
3. **What's Actually Happening** (1 paragraph) — Your deeper analysis connecting multiple stories with evidence
4. **The Hidden Tradeoffs** (2-3 sentences) — Costs and downsides not being discussed
5. **What This Means Next** (2-3 sentences) — Concrete predictions with timeframes
6. **Conclusion** (2-3 sentences) — Circle back to hook, leave something memorable

## STYLE RULES
- Use active voice and strong verbs
- Vary sentence length for rhythm
- Include one memorable metaphor or analogy
- Write for smart readers who haven't followed every story
- Avoid jargon unless you define it

## RIGOR CHECKLIST (ensure all are true):
- [ ] Every major claim is supported by evidence from the stories
- [ ] The thesis is clear and could be disagreed with
- [ ] Counterarguments are addressed honestly
- [ ] Predictions are specific enough to be falsifiable
- [ ] The piece adds insight beyond summarizing headlines

Respond with ONLY a valid JSON object:
{{
  "title": "Compelling headline (6-12 words, intriguing but not clickbait)",
  "slug": "url-friendly-slug-with-dashes",
  "summary": "1-2 sentence meta description for SEO that captures the thesis",
  "mood": "One word describing the overall tone (e.g., hopeful, concerned, transformative, skeptical, optimistic)",
  "content": "Full article content with HTML formatting. Use <h2> for section headers (The Lead, What People Think, etc.), <p> for paragraphs, <strong> for emphasis, <blockquote> for key insights.",
  "key_themes": ["theme1", "theme2", "theme3"],
  "predictions": ["specific prediction 1", "specific prediction 2"]
}}"""

        try:
            # Try structured output first (guaranteed valid JSON from Gemini)
            # Use 16384 tokens — generous headroom for a 500-word HTML article in JSON
            data = self._call_google_ai_structured(prompt, EDITORIAL_SCHEMA, max_tokens=16384)

            # Fall back to regular LLM call + JSON parsing if structured output fails
            if not data:
                logger.info("Structured output unavailable, falling back to regular LLM call")
                response = self._call_groq(prompt, max_tokens=16384)
                data = self._parse_json_response(response)

            if not data or not data.get("content"):
                logger.error("ARTICLE GENERATION FAILED: AI returned invalid/empty response (no content field)")
                return None

            # Validate content completeness - check for required sections
            content = data.get("content", "")
            required_sections = ["The Lead", "Conclusion"]
            missing_sections = [section for section in required_sections if section not in content]

            # If truncated, retry with fallback LLM
            if missing_sections:
                logger.warning(f"Article truncated (missing: {missing_sections}), retrying with fallback...")
                response = self._call_groq(prompt, max_tokens=16384)
                retry_data = self._parse_json_response(response)
                if retry_data and retry_data.get("content"):
                    retry_content = retry_data.get("content", "")
                    retry_missing = [s for s in required_sections if s not in retry_content]
                    if len(retry_missing) < len(missing_sections):
                        logger.info("Retry produced more complete article, using it")
                        data = retry_data
                        content = retry_content
                    else:
                        logger.warning("Retry also truncated, using original")

            # Build article object
            today = datetime.now().strftime("%Y-%m-%d")
            slug = self._sanitize_slug(data.get("slug", "daily-editorial"))

            article = EditorialArticle(
                title=data.get("title", "Today's Analysis"),
                slug=slug,
                date=today,
                summary=data.get("summary", ""),
                content=content,
                word_count=len(content.split()),
                top_stories=[t.get("title", "") for t in top_stories[:5]],
                keywords=data.get("key_themes", keywords[:5]),
                mood=data.get("mood", "informative"),
                url=f"/articles/{today.replace('-', '/')}/{slug}/",
            )

            # Save the article
            self._save_article(article, design)

            logger.info(f"Generated editorial: {article.title} ({article.word_count} words)")
            return article

        except Exception as e:
            logger.error(f"Editorial generation failed: {e}")
            return None

    def generate_why_this_matters(self, trends: List[Dict], count: int = 3) -> List[WhyThisMatters]:
        """
        Generate 'Why This Matters' context for top stories (batched into single API call).

        Args:
            trends: List of trend dictionaries
            count: Number of stories to generate context for

        Returns:
            List of WhyThisMatters objects
        """
        has_ollama = self._check_ollama_available()
        has_api_keys = self.groq_key or self.openrouter_key or self.google_key
        if not has_ollama and not has_api_keys:
            return []

        top_stories = trends[:count]
        if not top_stories:
            return []

        # Build batched prompt for all stories
        stories_data = []
        for i, story in enumerate(top_stories):
            title = story.get("title", "") or ""
            desc = (story.get("description") or "")[:200]
            stories_data.append(f"{i + 1}. TITLE: {title}\n   CONTEXT: {desc}")

        stories_text = "\n\n".join(stories_data)

        prompt = f"""Analyze these news stories and explain why each matters to readers.

STORIES:
{stories_text}

For EACH story, write a brief "Why This Matters" explanation (2-3 sentences) that:
1. Explains the broader significance of this story
2. Connects it to readers' lives or larger trends
3. Is accessible to a general audience

Respond with ONLY a valid JSON object:
{{
  "stories": [
    {{
      "story_number": 1,
      "explanation": "2-3 sentence explanation of why story 1 matters",
      "impact_areas": ["area1", "area2"]
    }},
    {{
      "story_number": 2,
      "explanation": "2-3 sentence explanation of why story 2 matters",
      "impact_areas": ["area1", "area2"]
    }},
    {{
      "story_number": 3,
      "explanation": "2-3 sentence explanation of why story 3 matters",
      "impact_areas": ["area1", "area2"]
    }}
  ]
}}"""

        try:
            # Try structured output first (guaranteed valid JSON from Gemini)
            data = self._call_google_ai_structured(prompt, STORY_SUMMARIES_SCHEMA, max_tokens=600)

            # Fall back to regular LLM call + JSON parsing if structured output fails
            if not data:
                logger.info("Structured output unavailable for story summaries, falling back")
                response = self._call_groq(prompt, max_tokens=600)
                data = self._parse_json_response(response)

            results = []
            if data and data.get("stories"):
                for i, item in enumerate(data["stories"]):
                    if i < len(top_stories) and item.get("explanation"):
                        story = top_stories[i]
                        results.append(
                            WhyThisMatters(
                                story_title=story.get("title", "") or "",
                                story_url=story.get("url", "") or "",
                                explanation=item.get("explanation", ""),
                                impact_areas=item.get("impact_areas", []),
                            )
                        )
            return results
        except Exception as e:
            logger.warning(f"Why This Matters batch generation failed: {e}")
            return []

    def _build_editorial_context(self, stories: List[Dict], keywords: List[str]) -> str:
        """Build rich context for editorial generation."""
        story_lines = []
        for i, s in enumerate(stories):
            title = s.get("title") or ""
            source = (s.get("source") or "unknown").replace("_", " ").title()
            desc = (s.get("description") or "")[:200]
            story_lines.append(f"{i + 1}. [{source}] {title}")
            if desc:
                story_lines.append(f"   Summary: {desc}")

        # Categorize stories
        categories = {}
        for s in stories:
            src = s.get("source", "other")
            if src in ["hackernews", "lobsters", "tech_rss", "github_trending"]:
                cat = "Technology"
            elif src in ["news_rss", "wikipedia"]:
                cat = "World News"
            elif src == "reddit":
                cat = "Social/Viral"
            else:
                cat = "General"
            categories[cat] = categories.get(cat, 0) + 1

        cat_summary = ", ".join(f"{v} {k}" for k, v in categories.items())

        return f"""TODAY'S TOP STORIES ({len(stories)} stories, {cat_summary}):
{chr(10).join(story_lines)}

TRENDING KEYWORDS: {", ".join(keywords[:20])}
DATE: {datetime.now().strftime("%B %d, %Y")}"""

    def _identify_central_themes(self, stories: List[Dict], keywords: List[str]) -> Dict:
        """
        Identify central themes and generate a thesis question from stories.

        Uses pattern matching and keyword analysis to find connective threads.
        """
        # Categorize stories by domain
        tech_count = 0
        social_count = 0
        business_count = 0
        science_count = 0

        for story in stories:
            source = (story.get("source") or "").lower()
            title = (story.get("title") or "").lower()

            if source in ["hackernews", "lobsters", "github_trending"] or any(
                kw in title
                for kw in [
                    "ai",
                    "tech",
                    "software",
                    "code",
                    "app",
                    "google",
                    "apple",
                    "microsoft",
                ]
            ):
                tech_count += 1
            if source == "reddit" or "viral" in title or "trend" in title:
                social_count += 1
            if any(
                kw in title
                for kw in [
                    "market",
                    "stock",
                    "company",
                    "ceo",
                    "billion",
                    "deal",
                    "startup",
                ]
            ):
                business_count += 1
            if any(kw in title for kw in ["study", "research", "science", "space", "health", "climate"]):
                science_count += 1

        # Detect recurring keywords
        keyword_freq = {}
        for kw in keywords[:30]:
            kw_lower = kw.lower()
            for story in stories:
                if (
                    kw_lower in (story.get("title") or "").lower()
                    or kw_lower in (story.get("description") or "").lower()
                ):
                    keyword_freq[kw] = keyword_freq.get(kw, 0) + 1

        # Find most connected keywords (appear in multiple stories)
        connected_keywords = sorted(
            [(k, v) for k, v in keyword_freq.items() if v >= 2],
            key=lambda x: x[1],
            reverse=True,
        )[:5]

        # Generate central question based on dominant theme
        if tech_count >= 4:
            if any("ai" in kw.lower() for kw, _ in connected_keywords):
                question = "How is AI reshaping the technology landscape, and who stands to win or lose?"
            else:
                question = "What do today's tech stories reveal about where innovation is heading?"
        elif business_count >= 3:
            question = "What market forces are driving today's biggest business stories, and what do they signal?"
        elif science_count >= 3:
            question = "How might today's scientific developments change our understanding or daily lives?"
        elif social_count >= 3:
            question = "What are today's viral moments telling us about culture and public attention?"
        elif connected_keywords:
            top_keyword = connected_keywords[0][0]
            question = f"What does the prominence of '{top_keyword}' in today's news reveal about current priorities?"
        else:
            question = "What common thread connects today's seemingly disparate top stories?"

        return {
            "question": question,
            "dominant_category": max(
                [
                    ("technology", tech_count),
                    ("business", business_count),
                    ("science", science_count),
                    ("social", social_count),
                ],
                key=lambda x: x[1],
            )[0],
            "connected_keywords": [kw for kw, _ in connected_keywords],
        }

    def _save_article(self, article: EditorialArticle, design: Optional[Dict] = None):
        """Save editorial article to permanent storage."""
        # Create directory structure: /articles/YYYY/MM/DD/slug/
        date_parts = article.date.split("-")
        article_dir = self.articles_dir / date_parts[0] / date_parts[1] / date_parts[2] / article.slug
        article_dir.mkdir(parents=True, exist_ok=True)

        tokens = self._get_design_tokens(design)

        # Get related articles for internal linking
        related_articles = self._get_related_articles(article.date, article.slug, limit=3)

        # Generate HTML
        html = self._generate_article_html(article, tokens, related_articles)

        # Save index.html
        (article_dir / "index.html").write_text(html, encoding="utf-8")

        # Save metadata JSON for sitemap/index generation
        metadata = asdict(article)
        (article_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")

        logger.info(f"Saved article to {article_dir}")

    def _generate_article_html(
        self,
        article: EditorialArticle,
        tokens: Dict,
        related_articles: Optional[List[Dict]] = None,
    ) -> str:
        """Generate full HTML page for an editorial article."""
        return render_article_html(article, tokens, related_articles)

    def _call_groq(
        self,
        prompt: str,
        max_tokens: int = 800,
        max_retries: int = 1,
        task_complexity: str = "complex",
    ) -> Optional[str]:
        """
        Call LLM API with smart provider routing based on task complexity.

        For simple tasks: OpenCode (free) > Mistral (free) > Hugging Face (free) > Groq > OpenRouter > Google AI
        For complex tasks: Mistral > Google AI > OpenRouter > OpenCode > Hugging Face > Groq

        Note: Editorial defaults to 'complex' as it requires high-quality writing.
        """
        # Only probe Ollama when explicitly configured — a 5s timeout on every
        # call burns the daily job when nothing is listening on :11434.
        if os.getenv("OLLAMA_URL") or os.getenv("OLLAMA_HOST"):
            result = self._call_ollama(prompt, max_tokens)
            if result:
                return result

        if task_complexity == "simple":
            # For simple tasks, prioritize free models to save quota
            result = self._call_opencode(prompt, max_tokens, max_retries)
            if result:
                return result

            result = self._call_mistral(prompt, max_tokens, max_retries)
            if result:
                return result

            result = self._call_huggingface(prompt, max_tokens, max_retries)
            if result:
                return result

            result = self._call_groq_direct(prompt, max_tokens, max_retries)
            if result:
                return result

            result = self._call_openrouter(prompt, max_tokens, max_retries)
            if result:
                return result

            return self._call_google_ai(prompt, max_tokens, max_retries)
        else:
            # Groq is the documented primary. Try it first so a configured-but-failing
            # free-tier chain cannot burn the 15-minute daily job.
            result = self._call_groq_direct(prompt, max_tokens, max_retries)
            if result:
                return result

            result = self._call_google_ai(prompt, max_tokens, max_retries)
            if result:
                return result

            result = self._call_openrouter(prompt, max_tokens, max_retries)
            if result:
                return result

            result = self._call_mistral(prompt, max_tokens, max_retries)
            if result:
                return result

            result = self._call_opencode(prompt, max_tokens, max_retries)
            if result:
                return result

            return self._call_huggingface(prompt, max_tokens, max_retries)

    def _check_ollama_available(self) -> bool:
        """Check if Ollama is running and accessible."""
        try:
            response = self.session.get(f"{self.ollama_url}/api/tags", timeout=5)
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False

    def _call_ollama(self, prompt: str, max_tokens: int = 800) -> Optional[str]:
        """Call local Ollama (delegates to shared ai_providers)."""
        return call_ollama(prompt, max_tokens, self.session, self.ollama_url, timeout=180)

    def _call_google_ai(self, prompt: str, max_tokens: int = 800, max_retries: int = 1) -> Optional[str]:
        """Call Google AI Gemini (delegates to shared ai_providers)."""
        return call_google_ai(prompt, max_tokens, max_retries, self.session, self.google_key)

    def _call_google_ai_structured(
        self, prompt: str, schema: dict, max_tokens: int = 4000, max_retries: int = 1
    ) -> Optional[Dict]:
        """
        Call Google AI with structured output (guaranteed valid JSON).

        Uses Gemini's response_mime_type and response_schema to ensure
        the response matches the provided JSON schema.
        """
        if not self.google_key:
            logger.info("No Google AI API key available, skipping structured output")
            return None

        # Check rate limits before calling
        rate_limiter = get_rate_limiter()
        status = check_before_call("google")

        if not status.is_available:
            logger.warning(f"Google AI not available: {status.error}")
            return None

        if status.wait_seconds > 0:
            logger.info(f"Waiting {status.wait_seconds:.1f}s for Google AI rate limit...")
            time.sleep(status.wait_seconds)

        # Use Gemini 2.5 Flash Lite with structured output
        model = "gemini-2.5-flash-lite"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

        for attempt in range(max_retries):
            try:
                logger.info(f"Trying Google AI {model} with structured output (attempt {attempt + 1}/{max_retries})")
                response = self.session.post(
                    url,
                    headers={
                        "x-goog-api-key": self.google_key,
                        "Content-Type": "application/json",
                    },
                    json={
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {
                            "maxOutputTokens": max_tokens,
                            "temperature": 0.7,
                            "response_mime_type": "application/json",
                            "response_schema": schema,
                        },
                    },
                    timeout=90,  # Longer timeout for structured output
                )
                response.raise_for_status()

                # Update rate limiter tracking
                rate_limiter._last_call_time["google"] = time.time()

                # Parse response - should be valid JSON
                data = response.json()
                candidates = data.get("candidates", [])
                if candidates:
                    # Check finish reason — MAX_TOKENS means content was truncated
                    finish_reason = candidates[0].get("finishReason", "")
                    if finish_reason == "MAX_TOKENS":
                        logger.warning(
                            f"Google AI structured output hit token limit ({max_tokens} tokens) — content likely truncated"
                        )

                    content = candidates[0].get("content", {})
                    parts = content.get("parts", [])
                    if parts:
                        text = parts[0].get("text", "")
                        if text:
                            try:
                                result = json.loads(text)
                                logger.info(
                                    f"Google AI structured output success with {model} (finishReason={finish_reason})"
                                )
                                return result
                            except json.JSONDecodeError as e:
                                # Shouldn't happen with structured output, but fallback to repair
                                logger.warning(f"Structured output JSON parse error (unexpected): {e}")
                                repaired = self._repair_json(text)
                                return json.loads(repaired)

            except requests.exceptions.HTTPError as e:
                if response.status_code == 429:
                    # Check if this is a quota exhaustion (daily limit) vs temporary rate limit
                    try:
                        error_data = response.json()
                        error_msg = str(error_data).lower()
                        if "quota" in error_msg or "exhausted" in error_msg or "daily" in error_msg:
                            # This is a quota exhaustion - mark provider as exhausted
                            mark_provider_exhausted("google", "daily quota exceeded")
                            return None
                    except (
                        ValueError,
                        requests.exceptions.JSONDecodeError,
                    ) as parse_err:
                        logger.debug(f"Could not parse 429 error body as JSON: {parse_err}")

                    # Temporary rate limit - wait and retry
                    retry_after = response.headers.get("Retry-After", "10")
                    try:
                        wait_time = min(float(retry_after), self.MAX_RETRY_WAIT)
                    except ValueError:
                        wait_time = self.MAX_RETRY_WAIT
                    logger.warning(
                        f"Google AI rate limited, waiting {wait_time}s (attempt {attempt + 1}/{max_retries})"
                    )
                    time.sleep(wait_time)
                    continue
                logger.error(f"Google AI structured output failed: {e}")
                return None
            except Exception as e:
                logger.error(f"Google AI structured output failed: {e}")
                return None

        logger.warning("Google AI structured output: Max retries exceeded")
        return None

    def _call_openrouter(self, prompt: str, max_tokens: int = 800, max_retries: int = 1) -> Optional[str]:
        """Call OpenRouter API (delegates to shared ai_providers)."""
        return call_openai_compatible(
            "openrouter",
            prompt,
            max_tokens,
            max_retries,
            self.session,
            api_key=self.openrouter_key,
        )

    def _call_groq_direct(self, prompt: str, max_tokens: int = 800, max_retries: int = 1) -> Optional[str]:
        """Call Groq API (delegates to shared ai_providers)."""
        return call_openai_compatible("groq", prompt, max_tokens, max_retries, self.session, api_key=self.groq_key)

    def _call_opencode(self, prompt: str, max_tokens: int = 800, max_retries: int = 1) -> Optional[str]:
        """Call OpenCode API (delegates to shared ai_providers)."""
        return call_openai_compatible("opencode", prompt, max_tokens, max_retries, self.session)

    def _call_huggingface(self, prompt: str, max_tokens: int = 800, max_retries: int = 1) -> Optional[str]:
        """Call Hugging Face Inference API (delegates to shared ai_providers)."""
        return call_huggingface(prompt, max_tokens, max_retries, self.session)

    def _call_mistral(self, prompt: str, max_tokens: int = 800, max_retries: int = 1) -> Optional[str]:
        """Call Mistral API (delegates to shared ai_providers)."""
        return call_openai_compatible("mistral", prompt, max_tokens, max_retries, self.session)

    def _repair_json(self, json_str: str) -> str:
        """Delegate to shared json_utils.repair_json."""
        return repair_json(json_str)

    def _parse_json_response(self, response: Optional[str]) -> Optional[Dict]:
        """Parse JSON from LLM response (delegates to shared json_utils)."""
        return parse_llm_json(response)

    def _sanitize_slug(self, slug: str) -> str:
        """Sanitize slug for URL usage."""
        # Convert to lowercase, replace spaces with dashes
        slug = slug.lower().strip()
        slug = re.sub(r"[^a-z0-9\-]", "-", slug)
        slug = re.sub(r"-+", "-", slug)  # Remove duplicate dashes
        slug = slug.strip("-")
        return slug[:60] or "daily-editorial"  # Max 60 chars

    def get_all_articles(self) -> List[Dict]:
        """Get metadata for all saved articles (for sitemap/index)."""
        articles = []

        if not self.articles_dir.exists():
            return articles

        # Walk through year/month/day/slug directories
        for metadata_file in self.articles_dir.rglob("metadata.json"):
            try:
                with open(metadata_file, encoding="utf-8") as f:
                    articles.append(json.load(f))
            except Exception as e:
                logger.warning(f"Failed to load {metadata_file}: {e}")

        # Sort by date descending
        articles.sort(key=lambda x: x.get("date", ""), reverse=True)
        return articles

    def validate_articles(self) -> Dict[str, List[str]]:
        """
        Validate all existing articles for completeness.

        Checks that each article has all required sections.

        Returns:
            Dict with 'complete' and 'incomplete' lists of article slugs
        """
        required_sections = [
            "The Lead",
            "What People Think",
            "What's Actually Happening",
            "The Hidden Tradeoffs",
            "What This Means Next",
            "Conclusion",
        ]

        results = {"complete": [], "incomplete": []}

        if not self.articles_dir.exists():
            return results

        for metadata_file in self.articles_dir.rglob("metadata.json"):
            try:
                with open(metadata_file, encoding="utf-8") as f:
                    metadata = json.load(f)

                content = metadata.get("content", "")
                slug = metadata.get("slug", "unknown")
                date = metadata.get("date", "unknown")
                article_id = f"{date}/{slug}"

                missing = [s for s in required_sections if s not in content]

                if missing:
                    logger.warning(f"Article {article_id} missing sections: {missing}")
                    results["incomplete"].append(article_id)
                else:
                    results["complete"].append(article_id)

            except Exception as e:
                logger.error(f"Failed to validate {metadata_file}: {e}")

        logger.info(
            f"Validation complete: {len(results['complete'])} complete, {len(results['incomplete'])} incomplete"
        )
        return results

    def fix_truncated_articles(self, design: Optional[Dict] = None) -> int:
        """
        Attempt to fix truncated/incomplete articles by regenerating content.

        For each incomplete article, this re-runs the AI generation using
        the stored top_stories as context, then updates the metadata and HTML.

        Args:
            design: Optional design spec for styling

        Returns:
            Number of articles fixed
        """
        # First, find incomplete articles
        validation = self.validate_articles()
        incomplete = validation.get("incomplete", [])

        if not incomplete:
            logger.info("No incomplete articles found")
            return 0

        fixed_count = 0
        tokens = self._get_design_tokens(design)

        for article_id in incomplete:
            try:
                # Parse date/slug from article_id (format: "YYYY-MM-DD/slug")
                date_str, slug = article_id.split("/", 1)
                date_parts = date_str.split("-")

                # Load existing metadata
                article_dir = self.articles_dir / date_parts[0] / date_parts[1] / date_parts[2] / slug
                metadata_file = article_dir / "metadata.json"

                if not metadata_file.exists():
                    logger.warning(f"Metadata file not found: {metadata_file}")
                    continue

                with open(metadata_file, encoding="utf-8") as f:
                    metadata = json.load(f)

                logger.info(f"Attempting to fix: {article_id}")

                # Build a focused prompt using the existing top_stories
                top_stories = metadata.get("top_stories", [])
                existing_title = metadata.get("title", "")
                existing_mood = metadata.get("mood", "informative")

                if not top_stories:
                    logger.warning(f"No top_stories in metadata for {article_id}")
                    continue

                # Create a regeneration prompt
                stories_text = "\n".join(f"- {story}" for story in top_stories)
                prompt = f"""You previously started writing an editorial article but it was truncated.
Please write a COMPLETE article based on these source stories:

{stories_text}

The article title is: "{existing_title}"
The mood/tone should be: {existing_mood}

IMPORTANT: Keep it to 400-500 words. You MUST include ALL of the following sections:
1. The Lead (2-3 sentences) - Hook and central thesis
2. What People Think (2-3 sentences) - Conventional wisdom
3. What's Actually Happening (1 paragraph) - Your deeper analysis
4. The Hidden Tradeoffs (2-3 sentences) - Costs not being discussed
5. What This Means Next (2-3 sentences) - Concrete predictions
6. Conclusion (2-3 sentences) - Circle back to hook

Use HTML formatting: <h2> for section headers, <p> for paragraphs, <strong> for emphasis.

Respond with ONLY a valid JSON object:
{{
  "content": "Full article content with HTML formatting including ALL 6 sections ending with Conclusion. MUST be under 500 words."
}}"""

                # Call AI with high token limit
                response = self._call_groq(prompt, max_tokens=16384)
                data = self._parse_json_response(response)

                if not data or not data.get("content"):
                    logger.warning(f"Failed to regenerate content for {article_id}")
                    continue

                new_content = data.get("content", "")

                # Validate the new content has required sections
                if "Conclusion" not in new_content:
                    logger.warning(f"Regenerated content still missing Conclusion for {article_id}")
                    continue

                # Update metadata
                metadata["content"] = new_content
                metadata["word_count"] = len(new_content.split())

                # Save updated metadata atomically — a crash mid-write would
                # corrupt the article state file the regen pipeline depends on.
                with tempfile.NamedTemporaryFile(
                    "w",
                    dir=metadata_file.parent,
                    suffix=".tmp",
                    delete=False,
                    encoding="utf-8",
                ) as tmp:
                    json.dump(metadata, tmp, indent=2)
                    tmp_path = Path(tmp.name)
                os.replace(tmp_path, metadata_file)

                # Reconstruct article and regenerate HTML
                article = EditorialArticle(
                    title=metadata.get("title", ""),
                    slug=metadata.get("slug", ""),
                    date=metadata.get("date", ""),
                    summary=metadata.get("summary", ""),
                    content=new_content,
                    word_count=metadata.get("word_count", 0),
                    top_stories=metadata.get("top_stories", []),
                    keywords=metadata.get("keywords", []),
                    mood=metadata.get("mood", "informative"),
                    url=metadata.get("url", ""),
                )

                related_articles = self._get_related_articles(article.date, article.slug, limit=3)
                html = self._generate_article_html(article, tokens, related_articles)
                (article_dir / "index.html").write_text(html, encoding="utf-8")

                logger.info(f"Fixed article: {article_id} ({article.word_count} words)")
                fixed_count += 1

            except Exception as e:
                logger.error(f"Failed to fix {article_id}: {e}")

        logger.info(f"Fixed {fixed_count} of {len(incomplete)} incomplete articles")
        return fixed_count

    def cleanup_orphaned_articles(self, dry_run: bool = False) -> List[str]:
        """
        Find and remove orphaned article directories (metadata.json without index.html).

        These orphans occur when article generation fails partway through, or when
        the cache contains stale metadata from failed runs.

        Args:
            dry_run: If True, only report orphans without deleting them

        Returns:
            List of paths that were (or would be) removed
        """
        orphans = []

        if not self.articles_dir.exists():
            return orphans

        for metadata_file in self.articles_dir.rglob("metadata.json"):
            article_dir = metadata_file.parent
            index_file = article_dir / "index.html"

            if not index_file.exists():
                orphans.append(str(article_dir))

                if dry_run:
                    logger.warning(f"ORPHAN (dry-run): {article_dir} - has metadata.json but no index.html")
                else:
                    logger.warning(f"REMOVING ORPHAN: {article_dir} - has metadata.json but no index.html")
                    try:
                        # Remove the entire article directory
                        import shutil

                        shutil.rmtree(article_dir)
                    except Exception as e:
                        logger.error(f"Failed to remove orphan {article_dir}: {e}")

        if orphans:
            logger.info(f"Found {len(orphans)} orphaned article(s)")
        else:
            logger.info("No orphaned articles found")

        return orphans

    def regenerate_all_article_pages(self, design: Optional[Dict] = None) -> int:
        """
        Regenerate HTML pages for all existing articles from their metadata.

        This updates the HTML (header, footer, styling) without regenerating
        the AI-written content.

        Args:
            design: Optional design spec for colors

        Returns:
            Number of articles regenerated
        """
        if not self.articles_dir.exists():
            logger.info("No articles directory found")
            return 0

        tokens = self._get_design_tokens(design)

        count = 0
        for metadata_file in self.articles_dir.rglob("metadata.json"):
            try:
                with open(metadata_file, encoding="utf-8") as f:
                    metadata = json.load(f)

                # Reconstruct EditorialArticle from metadata
                article = EditorialArticle(
                    title=metadata.get("title", ""),
                    slug=metadata.get("slug", ""),
                    date=metadata.get("date", ""),
                    summary=metadata.get("summary", ""),
                    content=metadata.get("content", ""),
                    word_count=metadata.get("word_count", 0),
                    top_stories=metadata.get("top_stories", []),
                    keywords=metadata.get("keywords", []),
                    mood=metadata.get("mood", "informative"),
                    url=metadata.get("url", ""),
                )

                # Get related articles for internal linking
                related_articles = self._get_related_articles(article.date, article.slug, limit=3)

                # Generate new HTML
                html = self._generate_article_html(article, tokens, related_articles)

                # Save to index.html in same directory as metadata.json
                article_dir = metadata_file.parent
                (article_dir / "index.html").write_text(html, encoding="utf-8")

                logger.info(f"Regenerated: {article.title}")
                count += 1

            except Exception as e:
                logger.warning(f"Failed to regenerate {metadata_file}: {e}")

        logger.info(f"Regenerated {count} article pages")
        return count

    def _get_related_articles(self, current_date: str, current_slug: str, limit: int = 3) -> List[Dict]:
        """Get related articles for internal linking (excludes current article)."""
        all_articles = self.get_all_articles()
        related = []

        for article in all_articles:
            # Skip current article
            if article.get("date") == current_date and article.get("slug") == current_slug:
                continue
            related.append(article)
            if len(related) >= limit:
                break

        return related

    def generate_articles_index(self, design: Optional[Dict] = None) -> str:
        """
        Generate an enhanced index page with search, filter, sort, and pagination.

        Features:
        - Full-text search across title, summary, keywords
        - Filter by date range, mood, word count
        - Sort by date, length, or alphabetically
        - Pagination (20 per page)
        - Month grouping with dividers
        - View toggle (list/compact)
        - Stats bar
        - Keyboard navigation
        - URL state persistence
        """
        articles = self.get_all_articles()

        tokens = self._get_design_tokens(design)

        # Calculate stats
        total_articles = len(articles)
        total_words = sum(a.get("word_count", 0) for a in articles)
        reading_hours = round(total_words / 200 / 60, 1)  # 200 wpm

        # Get unique moods for filter
        moods = sorted(set(a.get("mood", "informative") for a in articles))

        # Escape article data for JSON embedding
        # The data comes from our own metadata files (trusted), but we still escape for HTML safety
        from html_utils import json_for_script

        articles_json = json_for_script(
            [
                {
                    "title": a.get("title", ""),
                    "date": a.get("date", ""),
                    "url": (a.get("url", "") if str(a.get("url", "")).startswith("/articles/") else ""),
                    "summary": a.get("summary", "") or "",
                    "mood": a.get("mood", "informative"),
                    "word_count": a.get("word_count", 0),
                    "keywords": a.get("keywords", []),
                }
                for a in articles
            ]
        )

        html = render_articles_index(
            tokens,
            articles_json,
            total_articles,
            total_words,
            reading_hours,
            moods,
        )

        # Save index
        self.articles_dir.mkdir(parents=True, exist_ok=True)
        (self.articles_dir / "index.html").write_text(html, encoding="utf-8")

        logger.info(f"Generated enhanced articles index with {total_articles} articles")
        return html


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Editorial Generator CLI")
    parser.add_argument(
        "--regenerate-html",
        action="store_true",
        help="Regenerate HTML for all existing articles (updates header/footer without re-running AI)",
    )
    parser.add_argument(
        "--regenerate-index",
        action="store_true",
        help="Regenerate the articles index page",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate all articles for completeness (checks for required sections)",
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Fix truncated articles by regenerating their content using AI",
    )
    parser.add_argument(
        "--cleanup-orphans",
        action="store_true",
        help="Remove orphaned article directories (metadata.json without index.html)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="With --cleanup-orphans, only report orphans without deleting",
    )

    args = parser.parse_args()

    gen = EditorialGenerator()

    if args.cleanup_orphans:
        orphans = gen.cleanup_orphaned_articles(dry_run=args.dry_run)
        if args.dry_run:
            print(f"Found {len(orphans)} orphaned article(s) (dry-run, not deleted)")
        else:
            print(f"Removed {len(orphans)} orphaned article(s)")
        # Also regenerate the index after cleanup
        if not args.dry_run and orphans:
            gen.generate_articles_index()
            print("Regenerated articles index")
    elif args.regenerate_html:
        # Clean up orphans before regenerating HTML
        gen.cleanup_orphaned_articles(dry_run=False)
        count = gen.regenerate_all_article_pages()
        print(f"Regenerated {count} article pages")
    elif args.regenerate_index:
        # Clean up orphans before regenerating index
        gen.cleanup_orphaned_articles(dry_run=False)
        gen.generate_articles_index()
        print("Regenerated articles index")
    elif args.validate:
        results = gen.validate_articles()
        print("\nArticle Validation Results:")
        print(f"  Complete: {len(results['complete'])}")
        print(f"  Incomplete: {len(results['incomplete'])}")
        if results["incomplete"]:
            print("\nIncomplete articles:")
            for article in results["incomplete"]:
                print(f"  - {article}")
    elif args.fix:
        print("Checking for truncated articles...")
        fixed = gen.fix_truncated_articles()
        if fixed > 0:
            print(f"\nFixed {fixed} truncated article(s)")
            print("Run --validate again to verify")
        else:
            print("No truncated articles found or none could be fixed")
    else:
        parser.print_help()
