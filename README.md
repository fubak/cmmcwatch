# CMMC Watch 🛡️

**Automated daily news aggregator for CMMC/NIST compliance professionals.**

[![Daily Build](https://github.com/fubak/cmmcwatch/actions/workflows/daily-regenerate.yml/badge.svg)](https://github.com/fubak/cmmcwatch/actions/workflows/daily-regenerate.yml)
[![Live Site](https://img.shields.io/badge/live-cmmcwatch.com-blue)](https://cmmcwatch.com)

![CMMC Watch](https://img.shields.io/badge/CMMC-Compliance%20News-orange)
![Python](https://img.shields.io/badge/python-3.10+-blue)
![License](https://img.shields.io/badge/license-MIT-green)

---

## 🎯 What is CMMC Watch?

CMMC Watch is a free, open-source news aggregator that automatically collects, categorizes, and publishes daily news about:

- **CMMC Certification** (Cybersecurity Maturity Model Certification)
- **NIST Frameworks** (800-171, 800-172, DFARS compliance)
- **Defense Industrial Base** (DoD contractors, DIB cybersecurity)
- **Federal Cybersecurity** (Government cyber threats, policy updates)
- **Intelligence Threats** (Espionage, nation-state actors, APTs)
- **Insider Threats** (Employee risks, data exfiltration)

**Live Site:** [cmmcwatch.com](https://cmmcwatch.com)

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10 or higher
- Git
- API keys (see [Configuration](#-configuration))

### Installation

```bash
# Clone the repository
git clone https://github.com/fubak/cmmcwatch.git
cd cmmcwatch

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# Edit .env and add your API keys (see Configuration section)

# Run the pipeline
cd scripts
python main.py
```

The generated website will be in `public/index.html`.

---

## 🔑 Configuration

### Required API Keys

Create a `.env` file in the project root with the following keys:

```bash
# AI Generation (at least one required)
GROQ_API_KEY=gsk_your_key_here           # Recommended - fastest, free tier
OPENROUTER_API_KEY=sk-or-your_key_here   # Backup
GOOGLE_AI_API_KEY=your_key_here          # Alternative

# Image Fetching (recommended)
PEXELS_API_KEY=your_key_here             # 200 req/hour free
UNSPLASH_ACCESS_KEY=your_key_here        # 50 req/hour free

# LinkedIn Scraping (optional)
APIFY_API_KEY=apify_api_your_key_here    # $5/month free tier
APIFY_ACTOR_ID=scraper-engine/linkedin-post-scraper
```

### Get API Keys

| Service | Free Tier | Sign Up |
|---------|-----------|---------|
| **Groq** | Yes (30 req/min) | [console.groq.com](https://console.groq.com) |
| **OpenRouter** | Yes ($1 credit) | [openrouter.ai](https://openrouter.ai) |
| **Google AI** | Yes (60 req/min) | [makersuite.google.com](https://makersuite.google.com/app/apikey) |
| **Pexels** | Yes (200/hour) | [pexels.com/api](https://www.pexels.com/api/) |
| **Unsplash** | Yes (50/hour) | [unsplash.com/developers](https://unsplash.com/developers) |
| **Apify** | Yes ($5/month) | [console.apify.com](https://console.apify.com/account/integrations) |

**Total Monthly Cost:** $0 (all free tiers) 💰

---

## 📚 Data Sources

### RSS Feeds (20 sources)
- **Federal IT:** FedScoop, DefenseScoop, Federal News Network, Nextgov
- **Defense News:** Breaking Defense, Defense One, Defense News
- **Cybersecurity:** SecurityWeek, Cyberscoop, Industrial Cyber
- **Intelligence:** IntelNews, CSIS, Cyberpress
- **Official:** NIST CSRC, DOJ National Security, Cyber-AB News

### Reddit Communities (4 subreddits)
- r/CMMC, r/NISTControls, r/FederalEmployees, r/cybersecurity

### LinkedIn Influencers (4 profiles)
- Katie Arrington (DoD CIO, CMMC architect)
- Stacy Bostjanick (DoD Chief DIB Cybersecurity)
- Matthew Travis (Cyber-AB CEO)
- Amira Armond (C3PAO, CMMC Audit)

**See [SOURCES.md](SOURCES.md) for complete list.**

---

## 🏗️ Architecture

### 10-Step Pipeline

The pipeline runs automatically daily at 6 AM EST via GitHub Actions:

1. **Archive** - Save previous website
2. **Collect Trends** - Fetch from RSS, Reddit, LinkedIn
3. **Fetch Images** - Download relevant images
4. **Generate Design** - AI-powered design system
5. **Generate Editorial** - Write daily summary article
6. **Build Website** - Render HTML/CSS/JS
7. **Generate RSS** - Create RSS feed
8. **PWA Assets** - Service worker, manifest
9. **Generate Sitemap** - SEO optimization
10. **Cleanup** - Remove old archives (30-day retention)

### Project Structure

```
cmmcwatch/
├── scripts/              # Pipeline modules
│   ├── main.py          # Pipeline orchestrator
│   ├── collect_trends.py    # Data collection
│   ├── fetch_images.py      # Image fetching
│   ├── generate_design.py   # AI design generation
│   ├── editorial_generator.py  # Article writing
│   ├── build_website.py     # HTML generation
│   └── config.py        # All settings
├── templates/           # Jinja2 HTML templates
├── public/             # Generated website
├── data/               # Pipeline data (JSON)
└── .github/workflows/  # GitHub Actions
```

---

## 🧪 Testing

Run tests:

```bash
pytest tests/
```

Run with coverage:

```bash
pytest --cov=scripts tests/
```

---

## 🛠️ Development

### Local Development

```bash
# Run pipeline without archiving
cd scripts
python main.py --no-archive

# Dry run (collect data only, don't build)
python main.py --dry-run

# Run specific modules
python collect_trends.py     # Test data collection
python fetch_images.py       # Test image fetching
python editorial_generator.py --test  # Test article generation
```

### Environment Variables

Check your `.env` configuration:

```bash
cd scripts
python -c "from config import *; import os; print('✓ Config loaded')"
```

### Code Style

We use `ruff` for linting:

```bash
ruff check scripts/
ruff format scripts/
```

---

## 🚢 Deployment

### GitHub Pages (Automatic)

The site automatically deploys to GitHub Pages on every push to `main`:

1. GitHub Actions runs the pipeline
2. Generates fresh content daily at 6 AM EST
3. Deploys to `https://cmmcwatch.com`

### Manual Deployment

```bash
# Run the pipeline
cd scripts
python main.py

# The output is in public/
# Deploy public/ to any static hosting service
```

---

## 📊 Monitoring

### Build Status

Check [GitHub Actions](https://github.com/fubak/cmmcwatch/actions) for build status.

If a build fails, an issue is automatically created with the error details.

### API Usage

Monitor your API usage:
- **Groq:** [console.groq.com](https://console.groq.com)
- **Apify:** [console.apify.com/account/usage](https://console.apify.com/account/usage)
- **Pexels:** Dashboard at pexels.com

---

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Contribution Ideas

- Add new data sources (RSS feeds, APIs)
- Improve AI prompt engineering
- Add analytics/metrics
- Improve mobile UI
- Add email newsletter feature
- Translate to other languages

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **Data Sources:** FedScoop, DefenseScoop, NIST CSRC, Cyber-AB, and all RSS feed providers
- **AI Services:** Groq, OpenRouter, Google AI
- **Image Providers:** Pexels, Unsplash
- **Hosting:** GitHub Pages

---

## 📞 Support

- **Issues:** [GitHub Issues](https://github.com/fubak/cmmcwatch/issues)
- **Website:** [cmmcwatch.com](https://cmmcwatch.com)
- **Documentation:** See `ANALYSIS.md`, `SOURCES.md`, `LINKEDIN.md`

---

## 🔒 Security

If you discover a security vulnerability, please email [security contact here] instead of using the issue tracker.

---

## 📈 Roadmap

### Current (v1.0)
- ✅ Daily news aggregation from 24 sources
- ✅ AI-powered design generation
- ✅ Editorial article generation
- ✅ PWA support
- ✅ RSS feed

### Planned (v1.1)
- 📧 Email newsletter
- 📊 Analytics dashboard
- 🔍 Search functionality
- 📱 Mobile app (native)

### Future (v2.0)
- 👤 User accounts + personalization
- 🌍 Multi-language support
- 💾 Historical trend analysis
- 🤖 Custom AI models

---

**Built with ❤️ for the CMMC compliance community**
