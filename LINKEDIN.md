# LinkedIn Profile Monitoring Strategy

**Decision: Use Apify free tier ($5/month credits)**

## Why Apify?

After testing RSSHub and LinkedIn API:
- ❌ **RSSHub:** LinkedIn route disabled/broken due to LinkedIn anti-scraping
- ❌ **LinkedIn API:** Only works for company pages, not personal profiles
- ✅ **Apify:** Works reliably, $5/month free tier is sufficient

## Apify Free Tier Usage

**Free credits:** $5/month  
**Current config:** all 9 profiles × up to 3 posts, scraped **every other day**

> ✅ **Budget:** All 9 influencers are monitored, but the full list is scraped every
> other day (`LINKEDIN_FETCH_EVERY_N_DAYS = 2`) at 3 posts each — about the same
> per-run volume as the old 4-profile / 3-post setup, run ~15×/month instead of 30×.
> That keeps usage within the $5 free tier. The cadence is **stateless** (day-of-year
> parity) because CI wipes `data/*.json` each run, so a persisted "last fetched"
> timestamp would not survive between runs.

### Current Config

`scripts/config.py` (9 profiles — see [SOURCES.md](SOURCES.md) for the annotated list):
```python
CMMC_LINKEDIN_PROFILES = [ ... 9 URLs ... ]  # Katie Arrington, Stacy Bostjanick,
# Matthew Travis, Amira Armond, Scott Edwards, Jacob Horne, Daniel Akridge,
# Jacob Hill, Joy Beland

LINKEDIN_MAX_PROFILES = 10          # Max profiles per run (all 9 scraped)
LINKEDIN_MAX_POSTS_PER_PROFILE = 3  # Max posts per profile
LINKEDIN_FETCH_EVERY_N_DAYS = 2     # Scrape every other day (free-tier cost control)
```

**Per fetch (every other day):**
- up to 10 profiles per run (9 configured)
- up to 3 posts per profile
- ~27 posts per fetch, ~15 fetches/month

### Cost Breakdown (estimated)

| Activity | Cost per Run | Runs/Month | Total/Month |
|----------|--------------|------------|-------------|
| 9 profiles × 3 posts | ~$0.20 (est.) | ~15 (every other day) | **~$3–3.5 (est.)** |

**Result:** ✅ Within the $5 free tier — the every-other-day cadence offsets the larger
profile list. Confirm against actual Apify billing.

## Profiles Monitored (9)

1. **Katie Arrington** - DoD CIO (former CISO, original CMMC architect)
2. **Stacy Bostjanick** - DoD CIO Chief DIB Cybersecurity (CMMC implementation lead)
3. **Matthew Travis** - Cyber-AB CEO (former CISA Deputy Director)
4. **Amira Armond** - Kieri Solutions (C3PAO), cmmcaudit.org editor
5. **Scott Edwards** - Summit 7
6. **Jacob Horne** - Summit 7
7. **Daniel Akridge** - Summit 7
8. **Jacob Hill** - Summit 7 / GRC community
9. **Joy Beland** - CMMC educator

## Supplementary Free Sources

We also added these **FREE** RSS feeds for broader CMMC coverage:

**Official sources:**
- NIST CSRC - https://csrc.nist.gov/csrc/media/feeds/metafeeds/all.rss
- Cyber-AB News - https://cyberab.org/feed/
- CMMC Audit Blog - https://cmmcaudit.org/feed/

**Result:** 20+ free RSS feeds + 9 LinkedIn profiles = comprehensive coverage

## Monitoring Usage

Check Apify usage:
1. Go to https://console.apify.com/account/usage
2. Monitor "Platform usage" for current month
3. If still approaching the $5 limit, lower `LINKEDIN_MAX_POSTS_PER_PROFILE` or raise
   `LINKEDIN_FETCH_EVERY_N_DAYS` (e.g. 3 = every third day)

## Future Optimization

The every-other-day cadence (`LINKEDIN_FETCH_EVERY_N_DAYS = 2`) is already in place. If
the free tier still becomes insufficient:
- Raise `LINKEDIN_FETCH_EVERY_N_DAYS` to 3+ (scrape less often)
- Lower `LINKEDIN_MAX_POSTS_PER_PROFILE`
- Trim `CMMC_LINKEDIN_PROFILES` to the highest-signal accounts
- Switch to Google Alerts for supplementary monitoring

---

**Bottom line:** $5 free tier works perfectly for our needs. No paid upgrade required. 🎉
