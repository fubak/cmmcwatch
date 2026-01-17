"""
Shared HTML components for consistent header/footer across all pages.
"""

from datetime import datetime


def get_nav_links(active_page: str = "") -> str:
    """
    Generate navigation links HTML.

    Args:
        active_page: One of 'home', 'tech', 'world', 'science', 'politics',
                     'finance', 'media', 'articles' to mark as active
    """
    links = [
        ("/", "Home", "home"),
        ("/articles/", "Articles", "articles"),
        ("/archive/", "Archive", "archive"),
        ("/feed.xml", "RSS Feed", "rss"),
    ]

    items = []
    for href, label, page_id in links:
        active_class = ' class="active"' if page_id == active_page else ""
        items.append(f'<li><a href="{href}"{active_class}>{label}</a></li>')

    return "\n            ".join(items)


def build_header(active_page: str = "", date_str: str = None) -> str:
    """
    Build consistent header/navigation HTML.

    Args:
        active_page: Which page to mark as active in navigation
        date_str: Date string to display (defaults to today)
    """
    if date_str is None:
        date_str = datetime.now().strftime("%B %d, %Y")

    nav_links = get_nav_links(active_page)

    return f"""
    <nav class="nav" id="nav" role="navigation" aria-label="Main navigation">
        <a href="/" class="nav-logo" aria-label="CMMC Watch Home">
            <span>CMMC Watch</span>
        </a>
        <button class="mobile-menu-toggle" id="mobile-menu-toggle" aria-label="Toggle navigation menu" aria-expanded="false">
            <span class="hamburger-line"></span>
            <span class="hamburger-line"></span>
            <span class="hamburger-line"></span>
        </button>
        <ul class="nav-links" id="nav-links">
            {nav_links}
        </ul>
        <div class="nav-actions">
            <button class="theme-toggle" id="theme-toggle" aria-label="Toggle dark/light mode" title="Toggle dark/light mode">
                <svg class="sun-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <circle cx="12" cy="12" r="5"></circle>
                    <line x1="12" y1="1" x2="12" y2="3"></line>
                    <line x1="12" y1="21" x2="12" y2="23"></line>
                    <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line>
                    <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line>
                    <line x1="1" y1="12" x2="3" y2="12"></line>
                    <line x1="21" y1="12" x2="23" y2="12"></line>
                    <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line>
                    <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line>
                </svg>
                <svg class="moon-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>
                </svg>
            </button>
        </div>
    </nav>"""


def build_footer(date_str: str = None, style_info: str = "") -> str:
    """
    Build consistent footer HTML.

    Args:
        date_str: Date string to display (defaults to today)
        style_info: Optional style/theme info line
    """
    if date_str is None:
        date_str = datetime.now().strftime("%B %d, %Y")

    style_line = f'<p class="footer-description">{style_info}</p>' if style_info else ""

    return f"""
    <footer class="footer" role="contentinfo">
        <div class="footer-content">
            <div class="footer-main">
                <div class="footer-brand">CMMC Watch</div>
                <p class="footer-description">
                    Daily aggregation of CMMC, NIST 800-171, and Defense Industrial Base
                    compliance news from federal sources, industry publications, and community discussions.
                </p>
                {style_line}
            </div>
            <div class="footer-links-section">
                <h4 class="footer-section-title">Explore</h4>
                <ul class="footer-links">
                    <li><a href="/">Home</a></li>
                    <li><a href="/articles/">Articles</a></li>
                    <li><a href="/archive/">Archive</a></li>
                    <li><a href="/feed.xml">RSS Feed</a></li>
                </ul>
            </div>
            <div class="footer-author-section">
                <h4 class="footer-section-title">About the Author</h4>
                <p class="footer-author-bio">
                    Brad Shannon is a technology entrepreneur and cybersecurity professional
                    focused on helping organizations navigate CMMC compliance.
                </p>
                <a href="https://www.linkedin.com/in/bradmshannon/" class="footer-linkedin" target="_blank" rel="noopener noreferrer">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                        <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/>
                    </svg>
                    Connect on LinkedIn
                </a>
            </div>
        </div>
        <div class="footer-bottom">
            <span>Generated on {date_str}</span>
            <span class="footer-separator">|</span>
            <span>Built on <a href="https://dailytrending.info" target="_blank" rel="noopener noreferrer">Daily Trending</a></span>
            <div class="footer-actions">
                <a href="/archive/" class="archive-btn">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M3 3h18v18H3z"></path>
                        <path d="M21 9H3"></path>
                        <path d="M9 21V9"></path>
                    </svg>
                    View Archive
                </a>
            </div>
        </div>
    </footer>"""


def get_header_styles() -> str:
    """Get CSS styles for the header/navigation."""
    return """
        /* Navigation */
        .nav {
            position: sticky;
            top: 0;
            z-index: 100;
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 1rem 2rem;
            background: var(--color-bg);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border-bottom: 1px solid var(--color-border);
        }

        .nav-logo {
            font-family: var(--font-primary);
            font-weight: 700;
            font-size: 1.25rem;
            color: var(--color-text);
            text-decoration: none;
            display: flex;
            align-items: center;
        }

        .nav-links {
            display: flex;
            gap: 0.25rem;
            list-style: none;
            margin: 0;
            padding: 0;
        }

        .nav-links a {
            padding: 0.5rem 1rem;
            color: var(--color-muted);
            text-decoration: none;
            font-size: 0.9rem;
            font-weight: 500;
            border-radius: 0.5rem;
            transition: color 0.2s ease, background 0.2s ease;
        }

        .nav-links a:hover {
            color: var(--color-text);
            background: rgba(255, 255, 255, 0.05);
        }

        .nav-links a.active {
            color: var(--color-accent);
            background: rgba(255, 255, 255, 0.08);
        }

        .nav-actions {
            display: flex;
            align-items: center;
            gap: 1rem;
        }

        .nav-date {
            font-size: 0.85rem;
            color: var(--color-muted);
            display: none;
        }

        @media (min-width: 768px) {
            .nav-date {
                display: block;
            }
        }

        .theme-toggle, .nav-github {
            background: none;
            border: none;
            cursor: pointer;
            padding: 0.5rem;
            border-radius: 0.5rem;
            color: var(--color-muted);
            display: flex;
            align-items: center;
            justify-content: center;
            transition: color 0.2s ease, background 0.2s ease;
        }

        .theme-toggle:hover, .nav-github:hover {
            color: var(--color-text);
            background: rgba(255, 255, 255, 0.05);
        }

        .theme-toggle .sun-icon { display: none; }
        .theme-toggle .moon-icon { display: block; }
        body.light-mode .theme-toggle .sun-icon { display: block; }
        body.light-mode .theme-toggle .moon-icon { display: none; }

        /* Mobile menu */
        .mobile-menu-toggle {
            display: none;
            background: none;
            border: none;
            cursor: pointer;
            padding: 0.5rem;
            z-index: 101;
        }

        .hamburger-line {
            display: block;
            width: 24px;
            height: 2px;
            background: var(--color-text);
            margin: 5px 0;
            transition: transform 0.3s ease;
        }

        @media (max-width: 900px) {
            .mobile-menu-toggle {
                display: block;
            }

            .nav-links {
                display: none;
                position: absolute;
                top: 100%;
                left: 0;
                right: 0;
                flex-direction: column;
                background: var(--color-bg);
                border-bottom: 1px solid var(--color-border);
                padding: 1rem;
            }

            .nav-links.active {
                display: flex;
            }

            .nav-links li {
                opacity: 0;
                transform: translateY(-10px);
                transition: opacity 0.3s ease, transform 0.3s ease;
            }

            .nav-links.active li {
                opacity: 1;
                transform: translateY(0);
            }

            .nav-links.active li:nth-child(1) { transition-delay: 0.1s; }
            .nav-links.active li:nth-child(2) { transition-delay: 0.15s; }
            .nav-links.active li:nth-child(3) { transition-delay: 0.2s; }
            .nav-links.active li:nth-child(4) { transition-delay: 0.25s; }
            .nav-links.active li:nth-child(5) { transition-delay: 0.3s; }
            .nav-links.active li:nth-child(6) { transition-delay: 0.35s; }
            .nav-links.active li:nth-child(7) { transition-delay: 0.4s; }
            .nav-links.active li:nth-child(8) { transition-delay: 0.45s; }
            .nav-links.active li:nth-child(9) { transition-delay: 0.5s; }

            .nav-links a {
                display: block;
                padding: 0.75rem 1rem;
            }
        }
    """


def get_footer_styles() -> str:
    """Get CSS styles for the footer."""
    return """
        /* Footer */
        .footer {
            margin-top: 4rem;
            padding: 3rem 2rem;
            background: var(--color-card-bg);
            border-top: 1px solid var(--color-border);
        }

        .footer-content {
            max-width: 1200px;
            margin: 0 auto;
            display: grid;
            grid-template-columns: 2fr 1fr 1fr;
            gap: 3rem;
        }

        @media (max-width: 768px) {
            .footer-content {
                grid-template-columns: 1fr;
                gap: 2rem;
            }
        }

        .footer-brand {
            font-family: var(--font-primary);
            font-weight: 700;
            font-size: 1.5rem;
            color: var(--color-text);
            margin-bottom: 1rem;
        }

        .footer-description {
            color: var(--color-muted);
            font-size: 0.9rem;
            line-height: 1.6;
            margin-bottom: 1rem;
        }

        .footer-author-section {
            /* Author section styling */
        }

        .footer-author-bio {
            color: var(--color-muted);
            font-size: 0.9rem;
            line-height: 1.6;
            margin-bottom: 1rem;
        }

        .footer-linkedin {
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            color: var(--color-muted);
            text-decoration: none;
            font-size: 0.9rem;
            transition: color 0.2s ease;
            padding: 0.5rem 1rem;
            border-radius: 0.5rem;
            background: rgba(255, 255, 255, 0.05);
        }

        .footer-linkedin:hover {
            color: #0077b5;
            background: rgba(0, 119, 181, 0.1);
        }

        .footer-linkedin svg {
            flex-shrink: 0;
        }

        .footer-section-title {
            font-size: 0.85rem;
            font-weight: 600;
            color: var(--color-text);
            margin-bottom: 1rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        .footer-links {
            list-style: none;
            padding: 0;
            margin: 0;
        }

        .footer-links li {
            margin-bottom: 0.5rem;
        }

        .footer-links a {
            color: var(--color-muted);
            text-decoration: none;
            font-size: 0.9rem;
            transition: color 0.2s ease;
        }

        .footer-links a:hover {
            color: var(--color-accent);
        }

        .footer-bottom {
            max-width: 1200px;
            margin: 2rem auto 0;
            padding-top: 2rem;
            border-top: 1px solid var(--color-border);
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 1rem;
            font-size: 0.85rem;
            color: var(--color-muted);
        }

        .footer-separator {
            color: var(--color-border);
            margin: 0 0.25rem;
        }

        .footer-bottom a {
            color: var(--color-accent);
            text-decoration: none;
            transition: color 0.2s ease;
        }

        .footer-bottom a:hover {
            color: var(--color-text);
            text-decoration: underline;
        }

        .footer-actions {
            display: flex;
            gap: 1rem;
        }

        .footer-actions a {
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            color: var(--color-muted);
            text-decoration: none;
            padding: 0.5rem 1rem;
            border-radius: 0.5rem;
            background: rgba(255, 255, 255, 0.05);
            transition: color 0.2s ease, background 0.2s ease;
        }

        .footer-actions a:hover {
            color: var(--color-text);
            background: rgba(255, 255, 255, 0.1);
        }
    """


def get_theme_script() -> str:
    """Get JavaScript for theme toggle and mobile menu."""
    return """
    <script>
        // Theme toggle functionality
        (function() {
            const themeToggle = document.getElementById('theme-toggle');
            const body = document.body;

            // Apply saved theme or default to dark mode for new users
            const savedTheme = localStorage.getItem('theme');
            if (savedTheme === 'light') {
                body.classList.remove('dark-mode');
                body.classList.add('light-mode');
            } else {
                // Default to dark mode
                body.classList.remove('light-mode');
                body.classList.add('dark-mode');
                if (!savedTheme) localStorage.setItem('theme', 'dark');
            }

            if (themeToggle) {
                themeToggle.addEventListener('click', function() {
                    if (body.classList.contains('light-mode')) {
                        body.classList.remove('light-mode');
                        body.classList.add('dark-mode');
                        localStorage.setItem('theme', 'dark');
                    } else {
                        body.classList.remove('dark-mode');
                        body.classList.add('light-mode');
                        localStorage.setItem('theme', 'light');
                    }
                });
            }
        })();

        // Mobile menu toggle
        (function() {
            const menuToggle = document.getElementById('mobile-menu-toggle');
            const navLinks = document.getElementById('nav-links');

            if (menuToggle && navLinks) {
                menuToggle.addEventListener('click', function() {
                    navLinks.classList.toggle('active');
                    const isExpanded = navLinks.classList.contains('active');
                    menuToggle.setAttribute('aria-expanded', isExpanded);
                });
            }
        })();

        // Apply saved density/view preferences
        (function() {
            const body = document.body;
            const densityClasses = ['density-compact', 'density-comfortable', 'density-spacious'];

            // Apply saved density or default to compact
            const savedDensity = localStorage.getItem('reading_density');
            const density = savedDensity || 'compact';
            densityClasses.forEach(cls => body.classList.remove(cls));
            body.classList.add('density-' + density);
            if (!savedDensity) localStorage.setItem('reading_density', 'compact');

            // Apply saved view or default to grid
            const savedView = localStorage.getItem('reading_view');
            const view = savedView || 'grid';
            body.classList.toggle('view-list', view === 'list');
            if (!savedView) localStorage.setItem('reading_view', 'grid');
        })();
    </script>"""
