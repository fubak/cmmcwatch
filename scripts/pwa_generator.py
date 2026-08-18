#!/usr/bin/env python3
"""
PWA Generator Module - Generates Progressive Web App assets.

Includes:
- Web App Manifest (manifest.json)
- Service Worker (sw.js)
- Offline fallback support
"""

import json
import struct
import zlib
from datetime import datetime
from pathlib import Path

from config import setup_logging

logger = setup_logging("pipeline")


def generate_manifest() -> str:
    """
    Generate PWA manifest.json content.

    Returns:
        JSON string for manifest.json
    """
    manifest = {
        "name": "CMMC Watch",
        "short_name": "CMMCWatch",
        "description": "Daily CMMC, NIST 800-171, and federal cybersecurity compliance news aggregator",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#ffffff",
        "theme_color": "#6366f1",
        "orientation": "portrait-primary",
        "categories": ["news", "social"],
        "lang": "en-US",
        "icons": [
            {
                "src": "/icons/icon-192.png",
                "sizes": "192x192",
                "type": "image/png",
                "purpose": "any maskable",
            },
            {
                "src": "/icons/icon-512.png",
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "any maskable",
            },
        ],
        "related_applications": [],
        "prefer_related_applications": False,
        "shortcuts": [
            {
                "name": "Today's Trends",
                "short_name": "Trends",
                "description": "View today's trending topics",
                "url": "/",
                "icons": [{"src": "/icons/icon-192.png", "sizes": "192x192"}],
            },
            {
                "name": "Archive",
                "short_name": "Archive",
                "description": "Browse past daily designs",
                "url": "/archive/",
                "icons": [{"src": "/icons/icon-192.png", "sizes": "192x192"}],
            },
        ],
    }

    return json.dumps(manifest, indent=2)


def generate_service_worker() -> str:
    """
    Generate service worker for offline support and caching.

    Returns:
        JavaScript string for sw.js
    """
    cache_version = datetime.now().strftime("%Y%m%d")

    return f"""// CMMC Watch Service Worker
// Cache version: {cache_version}

const CACHE_NAME = 'cmmcwatch-v{cache_version}';
const OFFLINE_URL = '/offline.html';

// Assets to cache immediately
const PRECACHE_ASSETS = [
    '/',
    '/offline.html',
    '/manifest.json',
    '/feed.xml'
];

// Install event - cache core assets
self.addEventListener('install', (event) => {{
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then((cache) => {{
                console.log('[SW] Caching core assets');
                return cache.addAll(PRECACHE_ASSETS);
            }})
            .then(() => self.skipWaiting())
    );
}});

// Activate event - clean old caches
self.addEventListener('activate', (event) => {{
    event.waitUntil(
        caches.keys()
            .then((cacheNames) => {{
                return Promise.all(
                    cacheNames
                        .filter((name) => name !== CACHE_NAME)
                        .map((name) => {{
                            console.log('[SW] Deleting old cache:', name);
                            return caches.delete(name);
                        }})
                );
            }})
            .then(() => self.clients.claim())
    );
}});

// Fetch event - network first, fallback to cache
self.addEventListener('fetch', (event) => {{
    // Skip non-GET requests
    if (event.request.method !== 'GET') return;

    // Skip cross-origin requests
    if (!event.request.url.startsWith(self.location.origin)) return;

    event.respondWith(
        fetch(event.request)
            .then((response) => {{
                // Clone and cache successful responses
                if (response.status === 200) {{
                    const responseClone = response.clone();
                    caches.open(CACHE_NAME)
                        .then((cache) => {{
                            cache.put(event.request, responseClone);
                        }});
                }}
                return response;
            }})
            .catch(() => {{
                // Try cache on network failure
                return caches.match(event.request)
                    .then((cachedResponse) => {{
                        if (cachedResponse) {{
                            return cachedResponse;
                        }}
                        // Return offline page for navigation requests
                        if (event.request.mode === 'navigate') {{
                            return caches.match(OFFLINE_URL);
                        }}
                        return new Response('Offline', {{
                            status: 503,
                            statusText: 'Service Unavailable'
                        }});
                    }});
            }})
    );
}});
"""


def generate_offline_page() -> str:
    """
    Generate a simple offline fallback page.

    Returns:
        HTML string for offline.html
    """
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Offline - CMMC Watch</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0a0a0a;
            color: #ffffff;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            text-align: center;
            padding: 2rem;
        }
        .offline-container { max-width: 400px; }
        .offline-icon {
            font-size: 4rem;
            margin-bottom: 1.5rem;
            opacity: 0.8;
        }
        h1 {
            font-size: 1.75rem;
            margin-bottom: 1rem;
        }
        p {
            color: #a1a1aa;
            margin-bottom: 2rem;
            line-height: 1.6;
        }
        .retry-btn {
            display: inline-block;
            padding: 0.75rem 2rem;
            background: #6366f1;
            color: white;
            border: none;
            border-radius: 0.5rem;
            font-size: 1rem;
            font-weight: 600;
            cursor: pointer;
            transition: background 0.2s;
        }
        .retry-btn:hover { background: #4f46e5; }
    </style>
</head>
<body>
    <div class="offline-container">
        <div class="offline-icon">📡</div>
        <h1>You're Offline</h1>
        <p>
            It looks like you've lost your internet connection.
            CMMC Watch needs a connection to show you the latest trends.
        </p>
        <button class="retry-btn" onclick="location.reload()">
            Try Again
        </button>
    </div>
</body>
</html>
"""


def generate_pwa_icon_placeholder() -> str:
    """
    Generate a simple SVG icon placeholder.
    In production, replace with actual PNG icons.

    Returns:
        SVG string for icon
    """
    return """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
  <rect width="512" height="512" fill="#6366f1" rx="64"/>
  <text x="256" y="320" font-family="Arial, sans-serif" font-size="280" font-weight="bold" fill="white" text-anchor="middle">D</text>
</svg>
"""


def save_pwa_assets(public_dir: Path):
    """
    Save all PWA assets to the public directory.

    Args:
        public_dir: Path to the public output directory
    """
    # Create directories
    (public_dir / "icons").mkdir(parents=True, exist_ok=True)

    # Save manifest
    manifest_path = public_dir / "manifest.json"
    manifest_path.write_text(generate_manifest())
    logger.info(f"  Created {manifest_path}")

    # Save service worker
    sw_path = public_dir / "sw.js"
    sw_path.write_text(generate_service_worker())
    logger.info(f"  Created {sw_path}")

    # Save offline page
    offline_path = public_dir / "offline.html"
    offline_path.write_text(generate_offline_page())
    logger.info(f"  Created {offline_path}")

    # Save placeholder icon SVG
    icon_svg_path = public_dir / "icons" / "icon.svg"
    icon_svg_path.write_text(generate_pwa_icon_placeholder())
    logger.info(f"  Created {icon_svg_path}")

    icons_dir = public_dir / "icons"
    (icons_dir / "icon-192.png").write_bytes(_solid_png(192, 192, (99, 102, 241)))
    (icons_dir / "icon-512.png").write_bytes(_solid_png(512, 512, (99, 102, 241)))
    (public_dir / "og-image.png").write_bytes(_solid_png(1200, 630, (26, 54, 93)))
    logger.info("  Created PNG icons and og-image.png")

    saved_path = public_dir / "saved" / "index.html"
    saved_path.parent.mkdir(parents=True, exist_ok=True)
    saved_path.write_text(generate_saved_page(), encoding="utf-8")
    logger.info(f"  Created {saved_path}")

    logger.info(f"PWA assets saved to {public_dir}")


def _solid_png(width: int, height: int, rgb: tuple) -> bytes:
    """Minimal RGB PNG (stdlib only) so PWA/OG icon URLs resolve."""

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    raw = b"".join(b"\x00" + (bytes(rgb) * width) for _ in range(height))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


def generate_saved_page() -> str:
    """Static page that reads localStorage['cmmcwatch_saved']."""
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Saved stories | CMMC Watch</title>
    <link rel="stylesheet" href="/">
    <style>
        body { font-family: system-ui, sans-serif; max-width: 42rem; margin: 2rem auto; padding: 0 1rem; }
        h1 { font-size: 1.5rem; }
        ul { list-style: none; padding: 0; }
        li { border-bottom: 1px solid #ddd; padding: 0.75rem 0; }
        .empty { color: #666; }
    </style>
</head>
<body>
    <p><a href="/">← Home</a></p>
    <h1>Saved stories</h1>
    <p id="empty" class="empty">No saved stories yet. Use Save on the homepage.</p>
    <ul id="list"></ul>
    <script>
    const KEY = 'cmmcwatch_saved';
    const items = JSON.parse(localStorage.getItem(KEY) || '[]');
    const list = document.getElementById('list');
    const empty = document.getElementById('empty');
    if (items.length) {
        empty.hidden = true;
        items.forEach(item => {
            const li = document.createElement('li');
            const a = document.createElement('a');
            a.href = item.url || '#';
            a.textContent = item.title || item.url || 'Untitled';
            a.rel = 'noopener';
            a.target = '_blank';
            li.appendChild(a);
            list.appendChild(li);
        });
    }
    </script>
</body>
</html>
"""
