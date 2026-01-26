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

### Key CMMC Influencers (4 profiles)
1. **Katie Arrington** - DoD CIO (former CISO, original CMMC architect)
   - https://www.linkedin.com/in/katie-arrington-a6949425/

2. **Stacy Bostjanick** - DoD CIO Chief DIB Cybersecurity (CMMC implementation lead)
   - https://www.linkedin.com/in/stacy-bostjanick-a3b67173/

3. **Matthew Travis** - Cyber-AB CEO (former CISA Deputy Director)
   - https://www.linkedin.com/in/matthewtravisdc/

4. **Amira Armond** - Kieri Solutions (C3PAO), cmmcaudit.org editor
   - https://www.linkedin.com/in/amira-armond/

**Fetch limits (optimized for free tier):**
- 4 profiles max
- 3 posts per profile max
- 1 fetch per day
- ~12 posts/day total

**Expected usage:** ~$3/month  
**Free tier limit:** $5/month  
**Cost:** $0/month (within free tier) ✅

### LinkedIn API Credentials (Optional)

LinkedIn API integration is available but **not recommended** because:
- Only works for company pages (not personal profiles)
- Our key profiles are personal accounts
- Apify free tier works better for our use case

See `scripts/linkedin_api_setup.md` and `scripts/linkedin_oauth.py` if you want to experiment.

---

## Summary

**Total sources:** 20 RSS feeds + 4 LinkedIn profiles = 24 sources  
**Total cost:** $0/month (Apify free tier)  
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
3. If approaching $5 limit:
   - Reduce to 3 profiles
   - Fetch every other day
   - Or upgrade to paid tier ($49/month for more credits)

**Current config stays well within free tier.** No action needed. ✅
