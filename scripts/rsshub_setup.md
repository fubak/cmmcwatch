# RSSHub Setup Guide - LinkedIn Profile Monitoring

RSSHub converts LinkedIn profiles to RSS feeds. Free, self-hosted, no API limits.

## Quick Start (Docker)

### 1. Install RSSHub
```bash
docker run -d \
  --name rsshub \
  -p 1200:1200 \
  --restart unless-stopped \
  diygod/rsshub:latest
```

Wait ~30 seconds for startup, then test:
```bash
curl http://localhost:1200
```

Should see: RSSHub homepage HTML.

### 2. Test LinkedIn Feed
```bash
# Example: Get posts from Katie Arrington's profile
# Profile URL: https://www.linkedin.com/in/katie-arrington-a6949425/
# Username: katie-arrington-a6949425

curl "http://localhost:1200/linkedin/in/katie-arrington-a6949425"
```

Should return RSS XML with recent posts.

### 3. Update .env
```bash
# RSSHub endpoint (default: local Docker instance)
RSSHUB_URL=http://localhost:1200
```

### 4. Test the Fetcher Script
```bash
cd ~/clawd/cmmcwatch
python3 scripts/rsshub_fetch.py --test
```

Should fetch posts from all 4 CMMC profiles.

---

## LinkedIn Profile URL → RSSHub Format

**Profile URL format:**
- `https://www.linkedin.com/in/katie-arrington-a6949425/`

**RSSHub feed format:**
- `http://localhost:1200/linkedin/in/katie-arrington-a6949425`

The script handles this conversion automatically.

---

## Docker Management

**Start RSSHub:**
```bash
docker start rsshub
```

**Stop RSSHub:**
```bash
docker stop rsshub
```

**View logs:**
```bash
docker logs -f rsshub
```

**Update RSSHub:**
```bash
docker pull diygod/rsshub:latest
docker stop rsshub
docker rm rsshub
# Then re-run the docker run command above
```

---

## Public RSSHub Instances (Alternative)

If you don't want to self-host, use a public instance:

```bash
# .env
RSSHUB_URL=https://rsshub.app
```

**⚠️ Warning:**
- Public instances can be slow/unreliable
- May have rate limits
- Self-hosting recommended for production

---

## Comparison: RSSHub vs Apify vs LinkedIn API

| Feature | RSSHub | Apify | LinkedIn API |
|---------|--------|-------|--------------|
| **Cost** | FREE | $5-50/month | FREE |
| **Personal Profiles** | ✅ Yes | ✅ Yes | ❌ No |
| **Company Pages** | ✅ Yes | ✅ Yes | ✅ Yes |
| **Rate Limits** | None (self-hosted) | 200 req/month ($5) | 500 req/day |
| **Reliability** | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **Setup** | 5 min (Docker) | Instant | 15 min (OAuth) |

**Winner:** RSSHub for personal profiles (free + reliable)

---

## Integration with CMMC Watch

Once RSSHub is running, the daily trend collector will:
1. Fetch posts from 4 CMMC profiles via RSSHub
2. Extract titles, URLs, timestamps
3. Filter by CMMC/NIST keywords
4. Include in daily digest

**Expected output:**
- 4 profiles × 3-5 posts/day = ~12-20 posts
- Zero cost
- More reliable than Apify
- No scraping blocks

---

## Troubleshooting

### "Connection refused" Error
RSSHub isn't running. Start it:
```bash
docker start rsshub
```

### "Empty feed" or "No posts"
- LinkedIn may be blocking the RSSHub IP
- Try using a VPN or proxy
- Or switch to a public RSSHub instance

### "Rate limited"
- Only happens with public instances
- Self-host to avoid this

### Docker not installed?
```bash
# Install Docker (Ubuntu/Debian)
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# Log out and back in
```

---

## Next Steps

1. Run Docker command above
2. Test with `curl http://localhost:1200`
3. Run `python3 scripts/rsshub_fetch.py --test`
4. Done! No Apify needed.
