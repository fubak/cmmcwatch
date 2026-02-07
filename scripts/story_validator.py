#!/usr/bin/env python3
"""
Story Validator - AI-powered story validation, categorization, and deduplication.

Uses a single batch AI call to:
1. Validate story relevance to CMMC/NIST compliance
2. Correct miscategorized stories
3. Detect semantic duplicates (same story from different sources)
4. Filter out irrelevant content

Designed to work within free tier API limits by using batch processing.
"""

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Set, Tuple

import requests
from config import setup_logging

logger = setup_logging("story_validator")


@dataclass
class ValidationResult:
    """Result of story validation."""

    is_relevant: bool
    relevance_score: float  # 0.0 to 1.0
    correct_category: str
    category_confidence: float
    duplicate_of: Optional[str] = None  # URL of the original story if duplicate
    rejection_reason: Optional[str] = None


@dataclass
class DuplicateCluster:
    """A cluster of stories covering the same event/topic."""

    canonical_url: str  # Best story to keep
    canonical_title: str
    duplicate_urls: List[str]
    duplicate_titles: List[str]


class StoryValidator:
    """
    Validates stories using AI for relevance, categorization, and deduplication.

    Uses batch processing to stay within free tier limits.
    """

    # Categories for CMMC Watch
    VALID_CATEGORIES = [
        "cmmc_program",  # Core CMMC news (cmmc, c3pao, cyber-ab)
        "nist_compliance",  # NIST 800-171, DFARS, FedRAMP, FISMA
        "intelligence_threats",  # Espionage, nation-state actors, APTs
        "insider_threats",  # Insider risks, employee recruitment, data theft
        "defense_industrial_base",  # DoD contractors, DIB news
        "federal_cybersecurity",  # General federal cyber news
    ]

    # Irrelevant content patterns to filter
    IRRELEVANT_PATTERNS = [
        # Career/job posts
        r"mentorship\s+monday",
        r"career\s+(question|advice)",
        r"looking\s+for\s+(job|work|position)",
        r"(hiring|job)\s+thread",
        r"certification\s+(training|advice|bootcamp)",
        # Non-US/Non-security content (keep espionage stories even if foreign)
        r"\b(eu\s+mandate|ciro)\b",
        # Generic Reddit threads
        r"^\[?megathread\]?",
        r"weekly\s+(discussion|thread)",
        r"daily\s+(discussion|thread)",
        # Personal stories
        r"^(leaving|quitting|my\s+experience)",
    ]

    # Maximum age for stories (filter old pinned posts)
    MAX_STORY_AGE_DAYS = 14

    def __init__(
        self,
        groq_key: Optional[str] = None,
        openrouter_key: Optional[str] = None,
        google_key: Optional[str] = None,
    ):
        self.groq_key = groq_key or os.getenv("GROQ_API_KEY")
        self.openrouter_key = openrouter_key or os.getenv("OPENROUTER_API_KEY")
        self.google_key = google_key or os.getenv("GOOGLE_AI_API_KEY")
        self.session = requests.Session()

    def validate_stories(self, stories: List[Dict], use_ai: bool = True) -> Tuple[List[Dict], List[Dict]]:
        """
        Validate all stories and return filtered list.

        Args:
            stories: List of story dicts with title, description, category, url, timestamp
            use_ai: Whether to use AI for validation (falls back to rules if False)

        Returns:
            Tuple of (valid_stories, rejected_stories)
        """
        logger.info(f"Validating {len(stories)} stories...")

        # Step 1: Quick rule-based filtering (removes obvious junk)
        stories, quick_rejected = self._quick_filter(stories)
        logger.info(f"  Quick filter removed {len(quick_rejected)} stories")

        # Step 2: Filter old stories (removes stale Reddit pinned posts)
        stories, old_rejected = self._filter_old_stories(stories)
        logger.info(f"  Age filter removed {len(old_rejected)} old stories")

        # Step 3: Basic deduplication (exact/near-exact titles)
        stories, basic_dups = self._basic_deduplicate(stories)
        logger.info(f"  Basic dedup removed {len(basic_dups)} duplicates")

        if not stories:
            return [], quick_rejected + old_rejected + basic_dups

        # Step 4: AI-powered validation (if enabled and keys available)
        if use_ai and self._has_ai_keys():
            stories, ai_rejected, category_corrections = self._ai_validate(stories)
            logger.info(f"  AI validation removed {len(ai_rejected)} stories")
            logger.info(f"  AI corrected {category_corrections} categories")

            # Step 5: AI-powered semantic deduplication
            stories, semantic_dups = self._semantic_deduplicate(stories)
            logger.info(f"  Semantic dedup removed {len(semantic_dups)} duplicates")

            rejected = quick_rejected + old_rejected + basic_dups + ai_rejected + semantic_dups
        else:
            logger.info("  Skipping AI validation (no API keys or disabled)")
            rejected = quick_rejected + old_rejected + basic_dups

        logger.info(f"  Final: {len(stories)} valid, {len(rejected)} rejected")
        return stories, rejected

    def _quick_filter(self, stories: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
        """Quick rule-based filtering for obviously irrelevant content."""
        valid = []
        rejected = []

        for story in stories:
            # LinkedIn influencer posts are curated — skip pattern filtering
            if story.get("source") == "cmmc_linkedin":
                valid.append(story)
                continue

            title = (story.get("title") or "").lower()
            description = (story.get("description") or "").lower()
            content = f"{title} {description}"

            # Check against irrelevant patterns
            is_irrelevant = False
            for pattern in self.IRRELEVANT_PATTERNS:
                if re.search(pattern, content, re.IGNORECASE):
                    story["rejection_reason"] = f"Matched irrelevant pattern: {pattern}"
                    is_irrelevant = True
                    break

            if is_irrelevant:
                rejected.append(story)
            else:
                valid.append(story)

        return valid, rejected

    def _filter_old_stories(self, stories: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
        """Filter out stories older than MAX_STORY_AGE_DAYS."""
        valid = []
        rejected = []
        cutoff = datetime.now() - timedelta(days=self.MAX_STORY_AGE_DAYS)

        for story in stories:
            timestamp = story.get("timestamp")
            if timestamp:
                # Handle both datetime objects and strings
                if isinstance(timestamp, str):
                    try:
                        timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                    except ValueError:
                        try:
                            timestamp = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
                        except ValueError:
                            timestamp = None

                if timestamp and timestamp < cutoff:
                    story["rejection_reason"] = f"Too old: {timestamp.strftime('%Y-%m-%d')}"
                    rejected.append(story)
                    continue

            valid.append(story)

        return valid, rejected

    def _basic_deduplicate(self, stories: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
        """Basic deduplication using title similarity."""
        if not stories:
            return [], []

        valid = []
        rejected = []
        seen_titles: Set[str] = set()

        for story in stories:
            title = story.get("title", "")
            # Normalize title for comparison
            normalized = re.sub(r"[^\w\s]", "", title.lower())
            normalized = " ".join(normalized.split()[:10])  # First 10 words

            # Check for duplicates
            is_dup = False
            for seen in seen_titles:
                if SequenceMatcher(None, normalized, seen).ratio() > 0.85:
                    story["rejection_reason"] = f"Duplicate of: {seen[:50]}"
                    is_dup = True
                    break

            if is_dup:
                rejected.append(story)
            else:
                valid.append(story)
                seen_titles.add(normalized)

        return valid, rejected

    def _has_ai_keys(self) -> bool:
        """Check if any AI API keys are available."""
        return bool(self.groq_key or self.openrouter_key or self.google_key)

    def _ai_validate(self, stories: List[Dict]) -> Tuple[List[Dict], List[Dict], int]:
        """
        Use AI to validate stories for relevance and correct categories.

        Returns: (valid_stories, rejected_stories, category_correction_count)
        """
        if not stories:
            return [], [], 0

        # Build the validation prompt
        prompt = self._build_validation_prompt(stories)

        # Call AI API
        response = self._call_ai(prompt)
        if not response:
            logger.warning("AI validation failed, keeping all stories")
            return stories, [], 0

        # Parse AI response
        try:
            validation_results = self._parse_validation_response(response, stories)
        except Exception as e:
            logger.warning(f"Failed to parse AI response: {e}")
            return stories, [], 0

        # Apply validation results
        valid = []
        rejected = []
        corrections = 0

        for story, result in zip(stories, validation_results):
            is_linkedin = story.get("source") == "cmmc_linkedin"
            if not result.is_relevant and not is_linkedin:
                story["rejection_reason"] = result.rejection_reason or "AI marked as irrelevant"
                rejected.append(story)
            else:
                # Apply category correction if needed
                if result.correct_category != story.get("category"):
                    story["original_category"] = story.get("category")
                    story["category"] = result.correct_category
                    corrections += 1
                valid.append(story)

        return valid, rejected, corrections

    def _build_validation_prompt(self, stories: List[Dict]) -> str:
        """Build the AI validation prompt for batch processing."""
        # Format stories for the prompt
        story_list = []
        for i, story in enumerate(stories):
            story_list.append(
                f"{i + 1}. Title: {story.get('title', '')[:100]}\n"
                f"   Description: {(story.get('description') or '')[:150]}\n"
                f"   Current Category: {story.get('category', 'unknown')}\n"
                f"   Source: {story.get('source', 'unknown')}"
            )

        stories_text = "\n".join(story_list)

        return f"""You are a content moderator for CMMC Watch, a news aggregator focused on:
- CMMC (Cybersecurity Maturity Model Certification) program news
- NIST 800-171/800-172 compliance
- Defense Industrial Base (DIB) cybersecurity
- Federal cybersecurity policy affecting defense contractors
- Espionage, counterintelligence, and nation-state cyber threats
- Insider threats and security clearance issues

Analyze these {len(stories)} stories and determine:
1. Is each story RELEVANT to CMMC Watch's focus? (true/false)
2. What is the CORRECT category? Choose from:
   - cmmc_program: Core CMMC news (CMMC certification, C3PAO, Cyber-AB, assessments)
   - nist_compliance: NIST frameworks, DFARS, FedRAMP, FISMA, CUI
   - intelligence_threats: Espionage, spying, nation-state hackers, APTs, foreign agents, counterintelligence
   - insider_threats: Insider risks, employee recruitment by adversaries, data exfiltration, dark web recruitment
   - defense_industrial_base: DoD contractors, Pentagon, defense contracts, DIB
   - federal_cybersecurity: CISA, federal cyber policy, government IT security
3. If irrelevant, WHY?

RELEVANT content includes (keep these!):
- Espionage cases (spying for China, Russia, etc.) - categorize as intelligence_threats
- Nation-state hacking (APT groups, Chinese/Russian/DPRK hackers) - categorize as intelligence_threats
- Insider threat cases and dark web recruitment - categorize as insider_threats
- Foreign agent arrests and indictments - categorize as intelligence_threats
- Security clearance issues - categorize as insider_threats

IRRELEVANT content includes:
- Career advice, job hunting, certification training questions
- Generic EU/NATO European political affairs (unless espionage-related)
- Generic cybersecurity news not specific to federal/defense/national security
- SEC, SBA, or other non-cyber federal agencies
- Personal career stories or rants
- AI deepfakes, consumer privacy (unless federal policy)
- Reddit community posts (Discord invites, megathreads)

STORIES TO VALIDATE:
{stories_text}

Respond with ONLY a valid JSON array. Each element must have:
- index: story number (1-based)
- relevant: boolean
- category: one of the 4 valid categories
- reason: string (only if relevant=false, explain why)

Example:
[
  {{"index": 1, "relevant": true, "category": "cmmc_program"}},
  {{"index": 2, "relevant": false, "category": "federal_cybersecurity", "reason": "Canadian financial news, not US federal"}},
  {{"index": 3, "relevant": true, "category": "defense_industrial_base"}}
]"""

    def _call_ai(self, prompt: str) -> Optional[str]:
        """Call AI API with fallback chain."""
        # Try Groq first (fast, good free tier)
        if self.groq_key:
            result = self._call_groq(prompt)
            if result:
                return result

        # Try OpenRouter (free models available)
        if self.openrouter_key:
            result = self._call_openrouter(prompt)
            if result:
                return result

        # Try Google AI
        if self.google_key:
            result = self._call_google(prompt)
            if result:
                return result

        return None

    def _call_groq(self, prompt: str) -> Optional[str]:
        """Call Groq API."""
        try:
            logger.info("  Calling Groq for validation...")
            response = self.session.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.groq_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "llama-3.3-70b-versatile",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 4000,
                    "temperature": 0.1,  # Low temp for consistent classification
                },
                timeout=60,
            )
            response.raise_for_status()
            result = response.json().get("choices", [{}])[0].get("message", {}).get("content")
            if result:
                logger.info("  Groq validation successful")
                return result
        except Exception as e:
            logger.warning(f"  Groq validation failed: {e}")
        return None

    def _call_openrouter(self, prompt: str) -> Optional[str]:
        """Call OpenRouter API with free model."""
        try:
            logger.info("  Calling OpenRouter for validation...")
            response = self.session.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.openrouter_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://cmmcwatch.com",
                    "X-Title": "CMMCWatch",
                },
                json={
                    "model": "meta-llama/llama-3.3-70b-instruct:free",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 4000,
                    "temperature": 0.1,
                },
                timeout=90,
            )
            response.raise_for_status()
            result = response.json().get("choices", [{}])[0].get("message", {}).get("content")
            if result:
                logger.info("  OpenRouter validation successful")
                return result
        except Exception as e:
            logger.warning(f"  OpenRouter validation failed: {e}")
        return None

    def _call_google(self, prompt: str) -> Optional[str]:
        """Call Google AI (Gemini) API."""
        try:
            logger.info("  Calling Google AI for validation...")
            model = "gemini-2.0-flash"
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
            response = self.session.post(
                url,
                headers={
                    "x-goog-api-key": self.google_key,
                    "Content-Type": "application/json",
                },
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "maxOutputTokens": 4000,
                        "temperature": 0.1,
                    },
                },
                timeout=60,
            )
            response.raise_for_status()
            data = response.json()
            candidates = data.get("candidates", [])
            if candidates:
                content = candidates[0].get("content", {})
                parts = content.get("parts", [])
                if parts:
                    text = parts[0].get("text", "")
                    if text:
                        logger.info("  Google AI validation successful")
                        return text
        except Exception as e:
            logger.warning(f"  Google AI validation failed: {e}")
        return None

    def _parse_validation_response(self, response: str, stories: List[Dict]) -> List[ValidationResult]:
        """Parse AI validation response into ValidationResult objects."""
        # Extract JSON from response
        json_match = re.search(r"\[.*\]", response, re.DOTALL)
        if not json_match:
            raise ValueError("No JSON array found in response")

        json_str = json_match.group()

        # Clean up common JSON issues
        json_str = re.sub(r",\s*]", "]", json_str)  # Remove trailing commas
        json_str = re.sub(r",\s*}", "}", json_str)

        results_data = json.loads(json_str)

        # Build results list matching original story order
        results = []
        results_by_index = {r.get("index"): r for r in results_data}

        for i, story in enumerate(stories):
            idx = i + 1  # 1-based index
            if idx in results_by_index:
                r = results_by_index[idx]
                results.append(
                    ValidationResult(
                        is_relevant=r.get("relevant", True),
                        relevance_score=1.0 if r.get("relevant", True) else 0.0,
                        correct_category=r.get("category", story.get("category", "federal_cybersecurity")),
                        category_confidence=0.9,
                        rejection_reason=r.get("reason"),
                    )
                )
            else:
                # Default: keep the story with original category
                results.append(
                    ValidationResult(
                        is_relevant=True,
                        relevance_score=0.7,
                        correct_category=story.get("category", "federal_cybersecurity"),
                        category_confidence=0.5,
                    )
                )

        return results

    def _semantic_deduplicate(self, stories: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
        """
        Use AI to detect semantic duplicates (same story, different sources).

        Returns: (unique_stories, duplicate_stories)
        """
        if len(stories) < 2:
            return stories, []

        # Build prompt for duplicate detection
        prompt = self._build_duplicate_prompt(stories)

        response = self._call_ai(prompt)
        if not response:
            logger.warning("AI duplicate detection failed, keeping all stories")
            return stories, []

        try:
            clusters = self._parse_duplicate_response(response, stories)
        except Exception as e:
            logger.warning(f"Failed to parse duplicate response: {e}")
            return stories, []

        # Apply duplicate clusters
        urls_to_remove: Set[str] = set()
        for cluster in clusters:
            urls_to_remove.update(cluster.duplicate_urls)

        valid = []
        rejected = []
        for story in stories:
            url = story.get("url", "")
            if url in urls_to_remove:
                story["rejection_reason"] = "Semantic duplicate"
                rejected.append(story)
            else:
                valid.append(story)

        return valid, rejected

    def _build_duplicate_prompt(self, stories: List[Dict]) -> str:
        """Build prompt for semantic duplicate detection."""
        story_list = []
        for i, story in enumerate(stories):
            story_list.append(f"{i + 1}. [{story.get('source', 'unknown')}] {story.get('title', '')[:80]}")

        stories_text = "\n".join(story_list)

        return f"""Analyze these {len(stories)} news stories and identify DUPLICATE CLUSTERS.

A duplicate cluster contains stories that cover THE SAME EVENT or NEWS from different sources.
Example: "Pentagon announces $100M drone challenge" and "DIU offers $100M for drone swarms" are duplicates.

STORIES:
{stories_text}

Find all duplicate clusters. For each cluster:
1. Pick the BEST story to keep (prefer professional news sources over Reddit, prefer more detailed titles)
2. List the duplicate story numbers to remove

Respond with ONLY a valid JSON array of clusters. Each cluster:
- keep: story number to keep (1-based)
- remove: array of story numbers to remove (duplicates of 'keep')

Example:
[
  {{"keep": 3, "remove": [7, 12]}},
  {{"keep": 5, "remove": [9]}}
]

If NO duplicates found, respond with: []"""

    def _parse_duplicate_response(self, response: str, stories: List[Dict]) -> List[DuplicateCluster]:
        """Parse AI duplicate detection response."""
        # Extract JSON from response
        json_match = re.search(r"\[.*\]", response, re.DOTALL)
        if not json_match:
            return []

        json_str = json_match.group()
        json_str = re.sub(r",\s*]", "]", json_str)
        json_str = re.sub(r",\s*}", "}", json_str)

        clusters_data = json.loads(json_str)

        clusters = []
        for c in clusters_data:
            keep_idx = c.get("keep", 0) - 1  # Convert to 0-based
            remove_indices = [i - 1 for i in c.get("remove", [])]

            if 0 <= keep_idx < len(stories) and remove_indices:
                keep_story = stories[keep_idx]
                dup_stories = [stories[i] for i in remove_indices if 0 <= i < len(stories)]

                clusters.append(
                    DuplicateCluster(
                        canonical_url=keep_story.get("url", ""),
                        canonical_title=keep_story.get("title", ""),
                        duplicate_urls=[s.get("url", "") for s in dup_stories],
                        duplicate_titles=[s.get("title", "") for s in dup_stories],
                    )
                )

        return clusters


def validate_trends(trends: List[Dict], use_ai: bool = True) -> List[Dict]:
    """
    Convenience function to validate a list of trend dicts.

    Args:
        trends: List of trend dicts from collect_trends
        use_ai: Whether to use AI validation

    Returns:
        Filtered and validated list of trends
    """
    validator = StoryValidator()
    valid, rejected = validator.validate_stories(trends, use_ai=use_ai)

    if rejected:
        logger.info(f"Rejected {len(rejected)} stories:")
        for r in rejected[:10]:  # Log first 10
            logger.info(f"  - {r.get('title', '')[:50]}: {r.get('rejection_reason', 'unknown')}")
        if len(rejected) > 10:
            logger.info(f"  ... and {len(rejected) - 10} more")

    return valid


if __name__ == "__main__":
    # Test with sample stories
    from dotenv import load_dotenv

    load_dotenv()

    sample_stories = [
        {
            "title": "CMMC Level 2 Assessment Requirements Updated",
            "description": "DoD releases new guidance on CMMC Level 2 certification assessments",
            "category": "cmmc_program",
            "source": "cmmc_rss_fedscoop",
            "url": "https://example.com/1",
            "timestamp": datetime.now().isoformat(),
        },
        {
            "title": "Mentorship Monday - Career Questions Thread",
            "description": "Weekly thread for career advice and questions",
            "category": "nist_compliance",
            "source": "cmmc_reddit_cybersecurity",
            "url": "https://example.com/2",
            "timestamp": datetime.now().isoformat(),
        },
        {
            "title": "Denmark Bolsters Greenland Forces",
            "description": "NATO allies increase military presence",
            "category": "nist_compliance",
            "source": "cmmc_rss_breaking_defense",
            "url": "https://example.com/3",
            "timestamp": datetime.now().isoformat(),
        },
        {
            "title": "CISA Director Vacancy Impacts Cyber Operations",
            "description": "Federal cybersecurity agency continues without permanent leadership",
            "category": "federal_cybersecurity",
            "source": "cmmc_rss_fedscoop",
            "url": "https://example.com/4",
            "timestamp": datetime.now().isoformat(),
        },
    ]

    valid = validate_trends(sample_stories, use_ai=True)
    print(f"\nValid stories: {len(valid)}")
    for s in valid:
        print(f"  - [{s['category']}] {s['title']}")
