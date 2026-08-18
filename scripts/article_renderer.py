#!/usr/bin/env python3
"""Article HTML rendering for CMMC Watch.

``render_article_html`` was extracted verbatim from
``EditorialGenerator._generate_article_html`` to keep editorial_generator.py
smaller. It is a pure function of its inputs (article data, design tokens,
related articles) with no I/O or network, so its output is deterministic.
"""

import html
import json
from datetime import datetime
from typing import TYPE_CHECKING, Dict, List, Optional

try:
    from html_utils import sanitize_article_html, sanitize_hex_color
    from shared_components import (
        build_footer,
        build_header,
        get_footer_styles,
        get_header_styles,
        get_theme_script,
    )
except ImportError:
    from scripts.html_utils import sanitize_article_html, sanitize_hex_color
    from scripts.shared_components import (
        build_footer,
        build_header,
        get_footer_styles,
        get_header_styles,
        get_theme_script,
    )

if TYPE_CHECKING:
    from editorial_generator import EditorialArticle


def render_article_html(
    article: "EditorialArticle",
    tokens: Dict,
    related_articles: Optional[List[Dict]] = None,
) -> str:
    """Generate full HTML page for an editorial article."""
    date_formatted = datetime.strptime(article.date, "%Y-%m-%d").strftime("%B %d, %Y")

    # Properly escape for two distinct contexts:
    # - HTML attributes (meta og:title, twitter:title, <title>): full html.escape
    # - JSON-LD inside <script>: json.dumps PLUS <,>,& replacement, otherwise
    #   a payload like </script> in the value will break out of the script tag
    #   (the HTML parser scans for </script> regardless of JSON-string context).
    title_html = html.escape(article.title, quote=True)
    summary_html = html.escape(article.summary, quote=True)

    def _json_ld_safe(value: str) -> str:
        # json.dumps wraps in quotes; strip outer quotes for inline use,
        # then escape the three HTML chars that can break out of a script tag.
        encoded = json.dumps(value)[1:-1]
        return encoded.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")

    title_json = _json_ld_safe(article.title)
    summary_json = _json_ld_safe(article.summary)
    # Pre-render keywords array so the f-string below stays backslash-free.
    keywords_json = json.dumps(article.keywords).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    # Backwards-compatible aliases used in attribute contexts below
    title_escaped = title_html
    summary_escaped = summary_html
    article_content = sanitize_article_html(article.content)
    tokens = {
        **tokens,
        "primary_color": sanitize_hex_color(tokens.get("primary_color"), "#1a365d"),
        "accent_color": sanitize_hex_color(tokens.get("accent_color"), "#c53030"),
        "bg_color": sanitize_hex_color(tokens.get("bg_color"), "#0a0a0a"),
        "text_color": sanitize_hex_color(tokens.get("text_color"), "#f7fafc"),
        "muted_color": sanitize_hex_color(tokens.get("muted_color"), "#a0aec0"),
        "border_color": sanitize_hex_color(tokens.get("border_color"), "#2d3748"),
        "card_bg": sanitize_hex_color(tokens.get("card_bg"), "#1a202c"),
    }

    # Build related articles HTML
    related_html = ""
    if related_articles:
        related_cards = []
        for rel in related_articles:
            rel_date = datetime.strptime(rel["date"], "%Y-%m-%d").strftime("%B %d, %Y")
            rel_title = html.escape(rel.get("title", ""), quote=True)
            rel_summary = html.escape((rel.get("summary", "") or "")[:100], quote=True)
            if len(rel.get("summary", "") or "") > 100:
                rel_summary += "..."
            rel_url = rel.get("url", "") or ""
            if not rel_url.startswith("/articles/"):
                rel_url = "#"
            related_cards.append(f"""
                <a href="{html.escape(rel_url, quote=True)}" class="related-card">
                    <time datetime="{html.escape(rel["date"], quote=True)}">{rel_date}</time>
                    <h4>{rel_title}</h4>
                    <p>{rel_summary}</p>
                </a>""")
        related_html = f"""
            <div class="related-articles">
                <h3>More Analysis</h3>
                <div class="related-grid">
                    {"".join(related_cards)}
                </div>
            </div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title_html} | CMMC Watch</title>
    <meta name="description" content="{summary_escaped}">
    <meta name="keywords" content="{html.escape(", ".join(article.keywords), quote=True)}">
    <link rel="canonical" href="https://cmmcwatch.com{article.url}">

    <!-- Open Graph -->
    <meta property="og:title" content="{title_escaped}">
    <meta property="og:description" content="{summary_escaped}">
    <meta property="og:type" content="article">
    <meta property="og:url" content="https://cmmcwatch.com{article.url}">
    <meta property="og:site_name" content="CMMC Watch">
    <meta property="og:image" content="https://cmmcwatch.com/og-image.png">
    <meta property="og:image:width" content="1200">
    <meta property="og:image:height" content="630">
    <meta property="article:published_time" content="{article.date}T06:00:00Z">
    <meta property="article:author" content="https://twitter.com/bradshannon">
    <meta property="article:section" content="Analysis">

    <!-- Twitter Card -->
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:site" content="@bradshannon">
    <meta name="twitter:creator" content="@bradshannon">
    <meta name="twitter:title" content="{title_escaped}">
    <meta name="twitter:description" content="{summary_escaped}">
    <meta name="twitter:image" content="https://cmmcwatch.com/og-image.png">

    <!-- Google News -->
    <meta name="news_keywords" content="{html.escape(", ".join(article.keywords[:5]), quote=True) if article.keywords else "CMMC, NIST 800-171, cybersecurity, compliance"}">

    <!-- JSON-LD Structured Data -->
    <script type="application/ld+json">
    {{
        "@context": "https://schema.org",
        "@graph": [
            {{
                "@type": "NewsArticle",
                "@id": "https://cmmcwatch.com{article.url}#article",
                "headline": "{title_json}",
                "description": "{summary_json}",
                "datePublished": "{article.date}T06:00:00Z",
                "dateModified": "{article.date}T06:00:00Z",
                "author": {{
                    "@type": "Person",
                    "name": "Brad Shannon",
                    "url": "https://twitter.com/bradshannon",
                    "sameAs": ["https://twitter.com/bradshannon"]
                }},
                "publisher": {{
                    "@type": "Organization",
                    "name": "CMMC Watch",
                    "url": "https://cmmcwatch.com",
                    "logo": {{
                        "@type": "ImageObject",
                        "url": "https://cmmcwatch.com/icons/icon-512.png"
                    }}
                }},
                "mainEntityOfPage": {{
                    "@type": "WebPage",
                    "@id": "https://cmmcwatch.com{article.url}"
                }},
                "wordCount": {article.word_count},
                "keywords": {keywords_json},
                "articleSection": "Analysis",
                "inLanguage": "en-US"
            }},
            {{
                "@type": "BreadcrumbList",
                "itemListElement": [
                    {{"@type": "ListItem", "position": 1, "name": "Home", "item": "https://cmmcwatch.com/"}},
                    {{"@type": "ListItem", "position": 2, "name": "Articles", "item": "https://cmmcwatch.com/articles/"}},
                    {{"@type": "ListItem", "position": 3, "name": "{title_json}"}}
                ]
            }}
        ]
    }}
    </script>

    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family={tokens["font_secondary"].replace(" ", "+")}:wght@400;500;600;700&family={tokens["font_primary"].replace(" ", "+")}:wght@600;700&display=swap" rel="stylesheet">

    <style>
        :root {{
            --primary: {tokens["primary_color"]};
            --accent: {tokens["accent_color"]};
            --bg: {tokens["bg_color"]};
            --text: {tokens["text_color"]};
            --text-muted: {tokens["muted_color"]};
            --border: {tokens["border_color"]};
            --card-bg: {tokens["card_bg"]};
            --font-primary: '{tokens["font_primary"]}', system-ui, sans-serif;
            --font-secondary: '{tokens["font_secondary"]}', system-ui, sans-serif;
            /* Shared component color mappings */
            --color-text: var(--text);
            --color-muted: var(--text-muted);
            --color-bg: var(--bg);
            --color-accent: var(--accent);
            --color-border: var(--border);
            --color-card-bg: var(--card-bg);
        }}

        * {{ margin: 0; padding: 0; box-sizing: border-box; }}

        body {{
            font-family: var(--font-secondary);
            background: var(--bg);
            color: var(--text);
            line-height: 1.7;
            min-height: 100vh;
        }}

        body.light-mode {{
            --bg: #ffffff;
            --text: #1a1a2e;
            --text-muted: #64748b;
            --border: #e2e8f0;
            --card-bg: #f8fafc;
            --color-text: var(--text);
            --color-muted: var(--text-muted);
            --color-bg: var(--bg);
            --color-border: var(--border);
            --color-card-bg: var(--card-bg);
        }}

        body.dark-mode {{
            --bg: #0a0a0a;
            --text: #ffffff;
            --text-muted: #a1a1aa;
            --border: #27272a;
            --card-bg: #18181b;
            --color-text: var(--text);
            --color-muted: var(--text-muted);
            --color-bg: var(--bg);
            --color-border: var(--border);
            --color-card-bg: var(--card-bg);
        }}

        /* Density settings */
        body.density-compact {{
            --section-gap: 1.5rem;
            --card-gap: 0.75rem;
            --card-padding: 0.75rem;
        }}
        body.density-comfortable {{
            --section-gap: 2.5rem;
            --card-gap: 1.25rem;
            --card-padding: 1.25rem;
        }}
        body.density-spacious {{
            --section-gap: 4rem;
            --card-gap: 2rem;
            --card-padding: 1.75rem;
        }}

        .container {{
            max-width: 720px;
            margin: 0 auto;
            padding: 2rem 1.5rem;
        }}

        .breadcrumb {{
            font-size: 0.875rem;
            color: var(--text-muted);
            margin-bottom: 2rem;
        }}

        .breadcrumb a {{
            color: var(--accent);
            text-decoration: none;
        }}

        .breadcrumb a:hover {{
            text-decoration: underline;
        }}

        .article-header {{
            margin-bottom: 2.5rem;
            padding-bottom: 2rem;
            border-bottom: 1px solid var(--border);
        }}

        .article-meta {{
            display: flex;
            align-items: center;
            gap: 1rem;
            margin-bottom: 1rem;
            font-size: 0.875rem;
            color: var(--text-muted);
        }}

        .mood-badge {{
            background: var(--primary);
            color: white;
            padding: 0.25rem 0.75rem;
            border-radius: 999px;
            font-size: 0.75rem;
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}

        h1 {{
            font-family: var(--font-primary);
            font-size: clamp(2rem, 5vw, 3rem);
            font-weight: 700;
            line-height: 1.2;
            margin-bottom: 1rem;
            background: linear-gradient(135deg, var(--text), var(--accent));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }}

        .article-summary {{
            font-size: 1.25rem;
            color: var(--text-muted);
            font-weight: 400;
        }}

        .article-content {{
            font-size: 1.125rem;
        }}

        .article-content p {{
            margin-bottom: 1.5rem;
        }}

        .article-content h2 {{
            font-family: var(--font-primary);
            font-size: 1.5rem;
            margin: 2.5rem 0 1rem;
            color: var(--accent);
        }}

        .article-content blockquote {{
            border-left: 4px solid var(--primary);
            padding-left: 1.5rem;
            margin: 2rem 0;
            font-style: italic;
            color: var(--text-muted);
        }}

        .article-content strong {{
            color: var(--accent);
            font-weight: 600;
        }}

        .article-footer {{
            margin-top: 3rem;
            padding-top: 2rem;
            border-top: 1px solid var(--border);
        }}

        .sources-section {{
            background: rgba(255,255,255,0.03);
            border-radius: 12px;
            padding: 1.5rem;
            margin-bottom: 2rem;
        }}

        .sources-section h3 {{
            font-size: 0.875rem;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            color: var(--text-muted);
            margin-bottom: 1rem;
        }}

        .sources-section ul {{
            list-style: none;
        }}

        .sources-section li {{
            padding: 0.5rem 0;
            font-size: 0.9rem;
            color: var(--text-muted);
            border-bottom: 1px solid var(--border);
        }}

        .sources-section li:last-child {{
            border-bottom: none;
        }}

        .back-link {{
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            color: var(--accent);
            text-decoration: none;
            font-weight: 500;
            transition: opacity 0.2s;
        }}

        .back-link:hover {{
            opacity: 0.8;
        }}

        .keywords {{
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
            margin-top: 1rem;
        }}

        .keyword {{
            background: rgba(255,255,255,0.05);
            padding: 0.25rem 0.75rem;
            border-radius: 999px;
            font-size: 0.8rem;
            color: var(--text-muted);
        }}

        /* Related Articles */
        .related-articles {{
            margin-top: 2.5rem;
            padding-top: 2rem;
            border-top: 1px solid var(--border);
        }}

        .related-articles h3 {{
            font-size: 0.875rem;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            color: var(--text-muted);
            margin-bottom: 1.5rem;
        }}

        .related-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
        }}

        .related-card {{
            display: block;
            padding: 1rem;
            background: rgba(255,255,255,0.03);
            border: 1px solid var(--border);
            border-radius: 8px;
            text-decoration: none;
            transition: all 0.2s ease;
        }}

        .related-card:hover {{
            border-color: var(--primary);
            transform: translateY(-2px);
        }}

        .related-card time {{
            font-size: 0.75rem;
            color: var(--text-muted);
        }}

        .related-card h4 {{
            font-size: 0.95rem;
            margin: 0.5rem 0;
            color: var(--text);
            line-height: 1.4;
        }}

        .related-card p {{
            font-size: 0.8rem;
            color: var(--text-muted);
            margin: 0;
            line-height: 1.5;
        }}

        @media (max-width: 768px) {{
            .container {{
                padding: 1rem;
            }}

            h1 {{
                font-size: clamp(1.75rem, 5vw, 2.5rem);
            }}

            .article-summary {{
                font-size: 1rem;
            }}

            .article-content {{
                font-size: 1rem;
            }}

            .article-content h2 {{
                font-size: 1.25rem;
            }}

            .article-content blockquote {{
                padding-left: 1rem;
                margin: 1.5rem 0;
            }}

            .sources-section {{
                padding: 1rem;
            }}

            .related-articles {{
                grid-template-columns: 1fr;
            }}

            .breadcrumb {{
                font-size: 0.8rem;
            }}

            .article-meta {{
                flex-wrap: wrap;
            }}
        }}

        @media (max-width: 480px) {{
            .container {{
                padding: 0.75rem;
            }}

            h1 {{
                font-size: 1.5rem;
            }}

            .article-meta {{
                font-size: 0.75rem;
                gap: 0.5rem;
            }}

            .keywords {{
                gap: 0.375rem;
            }}

            .keyword {{
                font-size: 0.7rem;
                padding: 0.2rem 0.5rem;
            }}
        }}

        body.light-mode h1 {{
            background: linear-gradient(135deg, var(--text), var(--primary));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }}

        {get_header_styles()}
        {get_footer_styles()}
    </style>
</head>
<body class="{tokens["base_mode"]} editorial-mode">
    {build_header("articles", date_formatted)}

    <article class="container">
        <nav class="breadcrumb">
            <a href="/">Home</a> / <a href="/articles/">Articles</a> / {date_formatted}
        </nav>

        <header class="article-header">
            <div class="article-meta">
                <time datetime="{html.escape(article.date, quote=True)}">{date_formatted}</time>
                <span class="mood-badge">{html.escape(article.mood)}</span>
                <span>{article.word_count} words</span>
            </div>
            <h1>{html.escape(article.title)}</h1>
            <p class="article-summary">{html.escape(article.summary)}</p>
        </header>

        <div class="article-content">
            {article_content}
        </div>

        <footer class="article-footer">
            <div class="sources-section">
                <h3>Stories Referenced</h3>
                <ul>
                    {"".join(f"<li>{html.escape(story)}</li>" for story in article.top_stories)}
                </ul>
            </div>

            <div class="keywords">
                {"".join(f'<span class="keyword">{html.escape(kw)}</span>' for kw in article.keywords)}
            </div>

            {related_html}

            <p style="margin-top: 2rem;">
                <a href="/" class="back-link">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M19 12H5M12 19l-7-7 7-7"/>
                    </svg>
                    Back to Today's Trends
                </a>
            </p>
        </footer>
    </article>

    {build_footer(date_formatted)}

    {get_theme_script()}
</body>
</html>"""
