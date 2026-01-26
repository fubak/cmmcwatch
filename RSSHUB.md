# RSSHub LinkedIn Integration

**Free, self-hosted LinkedIn profile monitoring for CMMC Watch.**

## Why RSSHub?

| Feature | RSSHub | Apify | LinkedIn API |
|---------|--------|-------|--------------|
| **Cost** | FREE | $5-50/month | FREE |
| **Personal Profiles** | ✅ Yes | ✅ Yes | ❌ No |
| **Company Pages** | ✅ Yes | ✅ Yes | ✅ Yes |
| **Rate Limits** | None (self-hosted) | 200 req/month | 500 req/day |
| **Reliability** | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **Setup Time** | 2 minutes | Instant | 15 minutes |

**RSSHub wins:** Works for personal profiles, completely free, no rate limits when self-hosted.

---

## Quick Start (2 minutes)

### 1. Start RSSHub
```bash
./scripts/rsshub.sh start
```

Wait ~30 seconds for startup.

### 2. Test It
```bash
./scripts/rsshub.sh test
```

Should show: `✅ RSSHub is working!`

### 3. Fetch LinkedIn Posts
```bash
python3 scripts/rsshub_fetch.py --test
```

Should fetch ~12-20 posts from all 4 CMMC profiles.

**Done!** RSSHub is now monitoring Katie Arrington, Stacy Bostjanick, Matthew Travis, and Amira Armond for free. 🎉

---

## Daily Usage

RSSHub runs in the background. When the daily trend collector runs, it automatically:
1. Fetches posts from all 4 CMMC profiles via RSSHub
2. Filters by CMMC/NIST keywords
3. Includes relevant posts in the daily digest

**No manual intervention needed.**

---

## Management Commands

```bash
# Start RSSHub
./scripts/rsshub.sh start

# Check status
./scripts/rsshub.sh status

# View logs
./scripts/rsshub.sh logs

# Test connection
./scripts/rsshub.sh test

# Update to latest version
./scripts/rsshub.sh update

# Stop RSSHub
./scripts/rsshub.sh stop
```

---

## Profiles Monitored

1. **Katie Arrington** - DoD CIO (former CISO, original CMMC architect)
2. **Stacy Bostjanick** - DoD CIO Chief DIB Cybersecurity (CMMC implementation lead)
3. **Matthew Travis** - Cyber-AB CEO (former CISA Deputy Director)
4. **Amira Armond** - Kieri Solutions (C3PAO), cmmcaudit.org editor

---

## Troubleshooting

### RSSHub not starting?
```bash
# Check Docker is running
docker ps

# View RSSHub logs
./scripts/rsshub.sh logs

# Restart
./scripts/rsshub.sh restart
```

### Empty feeds or errors?

**Possible causes:**
- LinkedIn may be blocking the RSSHub IP
- Profile privacy settings changed
- RSSHub needs updating

**Solutions:**
1. Use a VPN or proxy
2. Switch to a public RSSHub instance (less reliable)
3. Update RSSHub: `./scripts/rsshub.sh update`

### Want to use a public instance instead?

Edit `.env`:
```bash
RSSHUB_URL=https://rsshub.app
```

**⚠️ Warning:** Public instances can be slow/unreliable. Self-hosting recommended.

---

## Cost Savings

**Before (Apify):**
- $5-50/month for scraping
- 12 posts/day from 4 profiles
- Unreliable (rate limited, blocks)

**After (RSSHub):**
- $0/month (self-hosted)
- 12-20 posts/day from 4 profiles
- More reliable

**Annual savings:** $60-600 💰

---

## Alternative: Keep Apify as Fallback

If RSSHub gets blocked by LinkedIn, you can still use Apify as a backup:

```python
# In your trend collector:
try:
    posts = fetch_via_rsshub()
except Exception:
    posts = fetch_via_apify()  # Fallback
```

Best of both worlds: Free RSSHub primary, paid Apify backup.

---

## Next Steps

1. ✅ RSSHub is running
2. ✅ LinkedIn feeds are working
3. ⏭️ Integrate into daily trend collector
4. ⏭️ Remove Apify dependency (or keep as fallback)

See `scripts/rsshub_setup.md` for detailed documentation.
