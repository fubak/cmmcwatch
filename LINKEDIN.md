# LinkedIn Profile Monitoring Strategy

**Decision: Use Apify free tier ($5/month credits)**

## Why Apify?

After testing RSSHub and LinkedIn API:
- ❌ **RSSHub:** LinkedIn route disabled/broken due to LinkedIn anti-scraping
- ❌ **LinkedIn API:** Only works for company pages, not personal profiles
- ✅ **Apify:** Works reliably, $5/month free tier is sufficient

## Apify Free Tier Usage

**Free credits:** $5/month  
**Current config:** 9 profiles × up to 5 posts × 1 fetch/day

> ⚠️ **Budget note:** This reverts the earlier 4-profile / 3-post optimization. At
> 9 profiles the run is ~2–4× the old basis (~$3/mo), so usage **likely exceeds the
> $5 free tier**. Verify at the Apify console; reduce `LINKEDIN_MAX_PROFILES`/posts or
> fetch frequency if over budget.

### Current Config

`scripts/config.py` (9 profiles — see [SOURCES.md](SOURCES.md) for the annotated list):
```python
CMMC_LINKEDIN_PROFILES = [ ... 9 URLs ... ]  # Katie Arrington, Stacy Bostjanick,
# Matthew Travis, Amira Armond, Scott Edwards, Jacob Horne, Daniel Akridge,
# Jacob Hill, Joy Beland

LINKEDIN_MAX_PROFILES = 10          # Max profiles per run
LINKEDIN_MAX_POSTS_PER_PROFILE = 5  # Max posts per profile
```

**Daily volume:**
- up to 10 profiles per run (9 configured)
- up to 5 posts per profile
- 1 fetch per day
- **Total:** ~45 posts/day

### Cost Breakdown (estimated)

| Activity | Cost per Run | Runs/Month | Total/Month |
|----------|--------------|------------|-------------|
| 9 profiles × 5 posts | ~$0.20–0.40 (est.) | 30 | **~$6–11 (est.)** |

**Result:** ⚠️ Likely **over** the $5 free tier. Estimates scale the prior
4-profile / $3 figure by profile and post count — confirm against actual Apify billing.

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
3. If approaching $5 limit, reduce to 3 profiles or fetch every other day

## Future Optimization

If free tier becomes insufficient:
- Reduce to 3 most important profiles (keep Katie, Stacy, Matthew)
- Fetch every other day instead of daily
- Switch to Google Alerts for supplementary monitoring

---

**Bottom line:** $5 free tier works perfectly for our needs. No paid upgrade required. 🎉
