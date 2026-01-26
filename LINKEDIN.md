# LinkedIn Profile Monitoring Strategy

**Decision: Use Apify free tier ($5/month credits)**

## Why Apify?

After testing RSSHub and LinkedIn API:
- ❌ **RSSHub:** LinkedIn route disabled/broken due to LinkedIn anti-scraping
- ❌ **LinkedIn API:** Only works for company pages, not personal profiles
- ✅ **Apify:** Works reliably, $5/month free tier is sufficient

## Apify Free Tier Optimization

**Free credits:** $5/month  
**Current usage:** 4 profiles × 1 fetch/day = ~$2-3/month  
**Headroom:** ~$2-3/month for occasional extra fetches

### Staying Within Free Limits

**Current config (optimized):**
```python
CMMC_LINKEDIN_PROFILES = [
    "https://www.linkedin.com/in/katie-arrington-a6949425/",      # DoD CIO
    "https://www.linkedin.com/in/stacy-bostjanick-a3b67173/",     # DoD Chief DIB Cyber
    "https://www.linkedin.com/in/matthewtravisdc/",               # Cyber-AB CEO
    "https://www.linkedin.com/in/amira-armond/",                  # C3PAO, CMMC Audit
]

LINKEDIN_MAX_PROFILES = 4           # Max profiles per run (reduced from 10)
LINKEDIN_MAX_POSTS_PER_PROFILE = 3  # Max posts per profile (reduced from 5)
```

**Daily limits:**
- 4 profiles max
- 3 posts per profile max
- 1 fetch per day
- **Total:** ~12 posts/day, well within free tier

### Cost Breakdown

| Activity | Cost per Run | Runs/Month | Total/Month |
|----------|--------------|------------|-------------|
| 4 profiles × 3 posts | ~$0.10 | 30 | ~$3.00 |
| **Total** | | | **~$3/month** |

**Result:** $2/month under free tier ✅

## Profiles Monitored

1. **Katie Arrington** - DoD CIO (former CISO, original CMMC architect)
2. **Stacy Bostjanick** - DoD CIO Chief DIB Cybersecurity (CMMC implementation lead)
3. **Matthew Travis** - Cyber-AB CEO (former CISA Deputy Director)
4. **Amira Armond** - Kieri Solutions (C3PAO), cmmcaudit.org editor

## Supplementary Free Sources

We also added these **FREE** RSS feeds for broader CMMC coverage:

**Official sources:**
- NIST CSRC - https://csrc.nist.gov/csrc/media/feeds/metafeeds/all.rss
- Cyber-AB News - https://cyberab.org/feed/
- CMMC Audit Blog - https://cmmcaudit.org/feed/

**Result:** 20+ free RSS feeds + 4 LinkedIn profiles = comprehensive coverage

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
