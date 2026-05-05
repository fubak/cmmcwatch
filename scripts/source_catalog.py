#!/usr/bin/env python3
"""Canonical source catalog for CMMC Watch collectors and health checks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional


DEFAULT_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

HEADER_PROFILES: Dict[str, Dict[str, str]] = {
    "default": {},
    "reddit": {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 "
            "CMMCWatch/1.0"
        ),
        "Accept": "application/rss+xml, application/xml;q=0.9, */*;q=0.8",
    },
    # Breaking Defense blocks some request signatures; simple UA is more reliable.
    "breaking_defense": {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/rss+xml, application/xml;q=0.9, */*;q=0.8",
    },
}

DOMAIN_FETCH_PROFILES: Dict[str, Dict[str, object]] = {
    "breakingdefense.com": {
        "attempts": 2,
        "retry_delay": 0.6,
        "headers_profile": "breaking_defense",
        "timeout": 15.0,
    },
}


@dataclass(frozen=True)
class SourceSpec:
    key: str
    name: str
    url: str
    category: str
    kind: str  # rss | json | html
    source_key: Optional[str] = None  # Trend.source key
    collector: Optional[str] = None
    selector: Optional[str] = None
    json_count_path: Optional[str] = None
    timeout_seconds: Optional[float] = None
    headers_profile: str = "default"
    fallback_url: Optional[str] = None
    tier: int = 4
    source_type: str = "other"
    risk: str = "medium"
    language: str = "en"
    parser: str = "rss"
    healthcheck: bool = True


def _rss(
    key: str,
    name: str,
    url: str,
    category: str,
    collector: str,
    *,
    source_key: Optional[str] = None,
    timeout_seconds: Optional[float] = None,
    headers_profile: str = "default",
    fallback_url: Optional[str] = None,
    tier: int = 2,
    source_type: str = "compliance",
    risk: str = "low",
    parser: str = "rss",
) -> SourceSpec:
    return SourceSpec(
        key=key,
        name=name,
        url=url,
        category=category,
        kind="rss",
        source_key=source_key or key,
        collector=collector,
        timeout_seconds=timeout_seconds,
        headers_profile=headers_profile,
        fallback_url=fallback_url,
        tier=tier,
        source_type=source_type,
        risk=risk,
        parser=parser,
    )


COLLECTOR_SOURCES: List[SourceSpec] = [
    _rss("cmmc_fedscoop", "FedScoop", "https://fedscoop.com/feed/", "cmmc", "cmmc_rss", tier=2),
    _rss("cmmc_defensescoop", "DefenseScoop", "https://defensescoop.com/feed/", "cmmc", "cmmc_rss", tier=2),
    _rss(
        "cmmc_fnn",
        "Federal News Network",
        "https://federalnewsnetwork.com/category/technology-main/cybersecurity/feed/",
        "cmmc",
        "cmmc_rss",
        tier=2,
    ),
    _rss(
        "cmmc_nextgov",
        "Nextgov Cybersecurity",
        "https://www.nextgov.com/rss/cybersecurity/",
        "cmmc",
        "cmmc_rss",
        tier=2,
    ),
    _rss("cmmc_govcon", "GovCon Wire", "https://www.govconwire.com/feed/", "cmmc", "cmmc_rss", tier=2),
    _rss("cmmc_securityweek", "SecurityWeek", "https://www.securityweek.com/feed/", "cmmc", "cmmc_rss", tier=2),
    _rss("cmmc_cyberscoop", "Cyberscoop", "https://cyberscoop.com/feed/", "cmmc", "cmmc_rss", tier=2),
    _rss(
        "cmmc_breakingdefense",
        "Breaking Defense",
        "https://breakingdefense.com/feed/",
        "cmmc",
        "cmmc_rss",
        headers_profile="breaking_defense",
        fallback_url=(
            "https://news.google.com/rss/search?"
            "q=site:breakingdefense.com+(CMMC+OR+defense+cybersecurity)+when:7d&hl=en-US&gl=US&ceid=US:en"
        ),
        tier=2,
    ),
    _rss("cmmc_defenseone", "Defense One", "https://www.defenseone.com/rss/all/", "cmmc", "cmmc_rss", tier=2),
    _rss(
        "cmmc_defensenews",
        "Defense News",
        "https://www.defensenews.com/arc/outboundfeeds/rss/?outputType=xml",
        "cmmc",
        "cmmc_rss",
        tier=2,
    ),
    _rss("cmmc_executivegov", "ExecutiveGov", "https://executivegov.com/feed/", "cmmc", "cmmc_rss", tier=2),
    _rss("cmmc_industrialcyber", "Industrial Cyber", "https://industrialcyber.co/feed/", "cmmc", "cmmc_rss", tier=2),
    _rss("cmmc_intelnews", "IntelNews", "https://intelnews.org/feed/", "cmmc", "cmmc_rss", tier=3),
    _rss("cmmc_csis", "CSIS", "https://www.csis.org/rss/analysis/all", "cmmc", "cmmc_rss", tier=2),
    _rss("cmmc_cyberpress", "Cyberpress", "https://cyberpress.org/feed/", "cmmc", "cmmc_rss", tier=3),
    _rss(
        "cmmc_reuters_security",
        "Reuters Security",
        "https://www.reuters.com/arc/outboundfeeds/v3/rss/section/world/cybersecurity/?outputType=xml",
        "cmmc",
        "cmmc_rss",
        tier=1,
        source_type="news",
    ),
    _rss(
        "cmmc_doj_national_security",
        "DOJ National Security",
        "https://www.justice.gov/feeds/opa/justice-news.xml",
        "cmmc",
        "cmmc_rss",
        tier=1,
        source_type="gov",
    ),
    _rss(
        "cmmc_nist_csrc",
        "NIST CSRC",
        "https://csrc.nist.gov/csrc/media/feeds/metafeeds/all.rss",
        "cmmc",
        "cmmc_rss",
        tier=1,
        source_type="gov",
    ),
    _rss("cmmc_cmmcaudit", "CMMC Audit Blog", "https://cmmcaudit.org/feed/", "cmmc", "cmmc_rss", tier=3),
    _rss("cmmc_cyberab", "Cyber-AB News", "https://cyberab.org/feed/", "cmmc", "cmmc_rss", tier=2),
    # Reddit feeds
    _rss(
        "cmmc_reddit_cmmc",
        "Reddit CMMC",
        "https://www.reddit.com/r/CMMC/.rss",
        "cmmc",
        "cmmc_reddit",
        headers_profile="reddit",
        tier=4,
        source_type="social",
        risk="medium",
    ),
    _rss(
        "cmmc_reddit_nistcontrols",
        "Reddit NISTControls",
        "https://www.reddit.com/r/NISTControls/.rss",
        "cmmc",
        "cmmc_reddit",
        headers_profile="reddit",
        tier=4,
        source_type="social",
        risk="medium",
    ),
    _rss(
        "cmmc_reddit_federalemployees",
        "Reddit FederalEmployees",
        "https://www.reddit.com/r/FederalEmployees/.rss",
        "cmmc",
        "cmmc_reddit",
        headers_profile="reddit",
        tier=4,
        source_type="social",
        risk="medium",
    ),
    _rss(
        "cmmc_reddit_cybersecurity",
        "Reddit Cybersecurity",
        "https://www.reddit.com/r/cybersecurity/.rss",
        "cmmc",
        "cmmc_reddit",
        headers_profile="reddit",
        tier=4,
        source_type="social",
        risk="medium",
    ),
]


COLLECTOR_SOURCES_BY_GROUP: Dict[str, List[SourceSpec]] = {}
SOURCE_BY_KEY: Dict[str, SourceSpec] = {}
SOURCE_BY_SOURCE_KEY: Dict[str, SourceSpec] = {}

for source in COLLECTOR_SOURCES:
    SOURCE_BY_KEY[source.key] = source
    if source.collector:
        COLLECTOR_SOURCES_BY_GROUP.setdefault(source.collector, []).append(source)
    if source.source_key and source.source_key not in SOURCE_BY_SOURCE_KEY:
        SOURCE_BY_SOURCE_KEY[source.source_key] = source


def get_collector_sources(group: str) -> List[SourceSpec]:
    return list(COLLECTOR_SOURCES_BY_GROUP.get(group, []))


def get_health_sources() -> List[SourceSpec]:
    return [source for source in COLLECTOR_SOURCES if source.healthcheck]


def get_source_by_key(key: str) -> Optional[SourceSpec]:
    return SOURCE_BY_KEY.get(key)


def get_source_by_source_key(source_key: str) -> Optional[SourceSpec]:
    return SOURCE_BY_SOURCE_KEY.get(source_key)
