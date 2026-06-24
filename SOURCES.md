# CMMC Watch - Data Sources

Complete list of sources for daily CMMC/compliance news aggregation.

## RSS Feeds (FREE - 20 feeds)

### Federal IT & Defense Cybersecurity
- FedScoop - https://fedscoop.com/feed/
- DefenseScoop - https://defensescoop.com/feed/
- Federal News Network - https://federalnewsnetwork.com/category/technology-main/cybersecurity/feed/
- Nextgov Cybersecurity - https://www.nextgov.com/rss/cybersecurity/
- GovCon Wire - https://www.govconwire.com/feed/
- SecurityWeek - https://www.securityweek.com/feed/
- Cyberscoop - https://cyberscoop.com/feed/

### Defense-focused
- Breaking Defense - https://breakingdefense.com/feed/
- Defense One - https://www.defenseone.com/rss/all/
- Defense News - https://www.defensenews.com/arc/outboundfeeds/rss/?outputType=xml
- ExecutiveGov - https://executivegov.com/feed/

### Intelligence & Espionage
- Industrial Cyber - https://industrialcyber.co/feed/
- IntelNews - https://intelnews.org/feed/
- CSIS - https://www.csis.org/rss/analysis/all
- Cyberpress - https://cyberpress.org/feed/
- Reuters Security - https://www.reuters.com/arc/outboundfeeds/v3/rss/section/world/cybersecurity/?outputType=xml

### Official Government Sources
- DOJ National Security - https://www.justice.gov/feeds/opa/justice-news.xml
- **NIST CSRC** - https://csrc.nist.gov/csrc/media/feeds/metafeeds/all.rss ⭐ NEW

### CMMC-Specific Resources
- **CMMC Audit Blog** - https://cmmcaudit.org/feed/ ⭐ NEW
- **Cyber-AB News** - https://cyberab.org/feed/ ⭐ NEW

**Total RSS feeds:** 20  
**Cost:** $0/month ✅

---

## LinkedIn Profiles (Apify - FREE TIER)

### Key CMMC Influencers (9 profiles)
1. **Katie Arrington** - DoD CIO (former CISO, original CMMC architect)
   - https://www.linkedin.com/in/katie-arrington-a6949425/

2. **Stacy Bostjanick** - DoD CIO Chief DIB Cybersecurity (CMMC implementation lead)
   - https://www.linkedin.com/in/stacy-bostjanick-a3b67173/

3. **Matthew Travis** - Cyber-AB CEO (former CISA Deputy Director)
   - https://www.linkedin.com/in/matthewtravisdc/

4. **Amira Armond** - Kieri Solutions (C3PAO), cmmcaudit.org editor
   - https://www.linkedin.com/in/amira-armond/

5. **Scott Edwards** - Summit 7
   - https://www.linkedin.com/in/mscottedwards/

6. **Jacob Horne** - Summit 7
   - https://www.linkedin.com/in/jacob-evan-horne/

7. **Daniel Akridge** - Summit 7
   - https://www.linkedin.com/in/danielakridge/

8. **Jacob Hill** - Summit 7 / GRC community
   - https://www.linkedin.com/in/jacobrhill/

9. **Joy Beland** - CMMC educator
   - https://www.linkedin.com/in/joybeland/

**Fetch limits (`config.py` / `fetch_linkedin_posts.py`):**
- 10 profiles max per run (`LINKEDIN_MAX_PROFILES`); 9 currently configured
- 3 posts per profile max (`LINKEDIN_MAX_POSTS_PER_PROFILE`)
- scraped every other day (`LINKEDIN_FETCH_EVERY_N_DAYS = 2`, stateless cadence)
- ~27 posts per fetch, ~15 fetches/month

**Free tier limit:** $5/month
**Cost:** ✅ ~$3–3.5/month (est.) — all 9 profiles are kept, but the every-other-day
cadence offsets the larger list to stay within the $5 free tier. Verify actual usage at
the Apify console (see [LINKEDIN.md](LINKEDIN.md)).

### LinkedIn API Credentials (Optional)

LinkedIn API integration is available but **not recommended** because:
- Only works for company pages (not personal profiles)
- Our key profiles are personal accounts
- Apify free tier works better for our use case

The pipeline uses Apify exclusively (`scripts/fetch_linkedin_posts.py`).

---

## Summary

**Total sources:** 20 RSS feeds + 9 LinkedIn profiles = 29 sources  
**Total cost:** $0/month for RSS; Apify LinkedIn ~$3–3.5/month (est.), within the $5 free tier via the every-other-day cadence  
**Expected daily content:** 50+ posts/day

**Recent additions (2026-01-25):**
- ✅ NIST CSRC RSS feed (official NIST 800-171 updates)
- ✅ CMMC Audit Blog RSS (Amira Armond)
- ✅ Cyber-AB News RSS (official certification body)

**Abandoned approaches:**
- ❌ RSSHub (LinkedIn route broken/disabled)
- ⚠️ LinkedIn API (available but limited to company pages)

---

## Monitoring Apify Usage

1. Go to https://console.apify.com/account/usage
2. Check "Platform usage" for current month
3. If still approaching the $5 limit:
   - Raise `LINKEDIN_FETCH_EVERY_N_DAYS` to 3+ (scrape less often)
   - Lower `LINKEDIN_MAX_POSTS_PER_PROFILE`
   - Or upgrade to paid tier ($49/month for more credits)

**The every-other-day cadence keeps all 9 profiles within the $5 free tier** (~$3–3.5/month est.) — monitor actual usage at the Apify console.
