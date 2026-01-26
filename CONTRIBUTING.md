# Contributing to CMMC Watch

Thank you for considering contributing to CMMC Watch! This document provides guidelines and instructions for contributing.

## 🎯 Ways to Contribute

- **Report Bugs:** Found a bug? [Create a bug report](https://github.com/fubak/cmmcwatch/issues/new?template=bug_report.md)
- **Suggest Features:** Have an idea? [Submit a feature request](https://github.com/fubak/cmmcwatch/issues/new?template=feature_request.md)
- **Add Data Sources:** Know a good RSS feed? [Suggest a data source](https://github.com/fubak/cmmcwatch/issues/new?template=data_source.md)
- **Improve Documentation:** Fix typos, clarify instructions, add examples
- **Write Code:** Fix bugs, add features, improve performance
- **Write Tests:** Increase test coverage

## 🚀 Getting Started

### 1. Fork and Clone

```bash
# Fork the repo on GitHub, then clone your fork
git clone https://github.com/YOUR_USERNAME/cmmcwatch.git
cd cmmcwatch

# Add upstream remote
git remote add upstream https://github.com/fubak/cmmcwatch.git
```

### 2. Set Up Environment

```bash
# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env

# Add your API keys to .env
# See README.md for instructions on getting free API keys
```

### 3. Create a Branch

```bash
# Create a branch for your changes
git checkout -b feature/your-feature-name

# Or for bug fixes:
git checkout -b fix/bug-description
```

## 💻 Development Workflow

### Running the Pipeline

```bash
# Full pipeline run
cd scripts
python main.py

# Skip archiving (faster for testing)
python main.py --no-archive

# Dry run (collect data only, don't build)
python main.py --dry-run
```

### Testing Individual Components

```bash
# Test trend collection
python scripts/collect_trends.py

# Test image fetching
python scripts/fetch_images.py

# Test design generation
python scripts/generate_design.py --test
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=scripts --cov-report=html

# Run only fast tests (skip slow integration tests)
pytest -m "not slow"

# Run specific test file
pytest tests/test_config.py -v
```

### Code Quality

```bash
# Format code with ruff
ruff format scripts/

# Lint code
ruff check scripts/

# Fix auto-fixable issues
ruff check scripts/ --fix

# Type checking (optional, mypy is configured loosely)
mypy scripts/
```

## 📝 Code Style Guidelines

### Python Style
- Follow [PEP 8](https://pep8.org/)
- Use `ruff` for formatting (configured in `pyproject.toml`)
- Maximum line length: 120 characters
- Use type hints where practical
- Write docstrings for all public functions/classes

### Example Function

```python
def fetch_data(url: str, timeout: int = 15) -> dict:
    """
    Fetch data from a URL with retry logic.
    
    Args:
        url: The URL to fetch from
        timeout: Request timeout in seconds
        
    Returns:
        Parsed JSON response as a dictionary
        
    Raises:
        requests.RequestException: If request fails after retries
    """
    # Implementation here
    pass
```

### Naming Conventions
- Functions/variables: `snake_case`
- Classes: `PascalCase`
- Constants: `UPPER_SNAKE_CASE`
- Private methods: `_leading_underscore`

## 🧪 Testing Guidelines

### Writing Tests
- Place tests in `tests/` directory
- Name test files `test_*.py`
- Name test functions `test_*`
- Use descriptive test names that explain what's being tested

### Test Categories
- **Unit tests:** Fast, no external dependencies
- **Integration tests:** May require network/APIs, mark with `@pytest.mark.slow`

### Example Test

```python
def test_categorize_trend():
    """Test trend categorization logic."""
    collector = TrendCollector()
    
    category = collector._categorize_trend(
        "CMMC 2.0 certification requirements",
        "New CMMC certification process announced"
    )
    
    assert category == "cmmc_program"
```

## 📦 Adding Data Sources

### Adding an RSS Feed

1. Edit `scripts/config.py`
2. Add to `CMMC_RSS_FEEDS` dictionary:

```python
CMMC_RSS_FEEDS = {
    # ... existing feeds
    "New Source Name": "https://example.com/feed.xml",
}
```

3. Test the feed:

```bash
python scripts/collect_trends.py
```

4. Submit PR with description of the source and why it's relevant

### Adding Keywords

Edit the relevant keyword list in `scripts/config.py`:

```python
CMMC_CORE_KEYWORDS = [
    # ... existing keywords
    "new-keyword",
]
```

## 🔄 Pull Request Process

### Before Submitting

1. **Update from upstream:**
   ```bash
   git fetch upstream
   git rebase upstream/main
   ```

2. **Run tests:**
   ```bash
   pytest
   ```

3. **Format code:**
   ```bash
   ruff format scripts/
   ruff check scripts/ --fix
   ```

4. **Update documentation** if needed

### Submitting the PR

1. Push your branch:
   ```bash
   git push origin feature/your-feature-name
   ```

2. Go to GitHub and create a Pull Request

3. Fill out the PR template:
   - **Title:** Clear, descriptive title
   - **Description:** What does this PR do? Why?
   - **Testing:** How did you test this?
   - **Screenshots:** If UI changes

### PR Review Process

- Maintainers will review your PR
- Address any requested changes
- Once approved, your PR will be merged

## 🐛 Bug Fix Guidelines

### Before Fixing a Bug

1. **Check existing issues** - Has this been reported?
2. **Reproduce the bug** - Can you consistently trigger it?
3. **Create an issue** if one doesn't exist

### Writing a Bug Fix

1. Add a test that reproduces the bug
2. Fix the bug
3. Verify the test now passes
4. Submit PR referencing the issue number

## 🎨 UI/Design Changes

### Guidelines
- Keep the design clean and professional
- Maintain accessibility (WCAG 2.1 AA)
- Test on mobile, tablet, and desktop
- Ensure dark/light mode compatibility (if implemented)

### Testing UI Changes

```bash
# Build the website
python scripts/main.py

# Open public/index.html in a browser
# Test on different screen sizes
```

## 📖 Documentation Changes

### Types of Documentation
- **README.md** - Setup and overview
- **ANALYSIS.md** - Architecture and recommendations
- **SOURCES.md** - Data source inventory
- **LINKEDIN.md** - LinkedIn strategy
- **CONTRIBUTING.md** - This file
- **Docstrings** - In-code documentation

### Documentation Style
- Use clear, concise language
- Include code examples where helpful
- Keep documentation up-to-date with code changes

## ⚡ Performance Considerations

### Guidelines
- Minimize API calls (use caching where appropriate)
- Use batch processing for AI requests
- Stay within free tier limits
- Add retry logic for network requests
- Log performance metrics

### Cost Optimization
- CMMC Watch runs on free tiers only
- Be mindful of API quotas
- Batch operations when possible
- Cache results aggressively

## 🔒 Security Guidelines

### Do Not
- Commit API keys or secrets
- Hardcode credentials
- Expose sensitive data in logs
- Merge unreviewed code that fetches external data

### Do
- Use environment variables for secrets
- Validate external input
- Use HTTPS for all external requests
- Keep dependencies updated

## 📞 Getting Help

- **Questions?** [Open a discussion](https://github.com/fubak/cmmcwatch/discussions)
- **Stuck?** Comment on your PR or issue
- **Security issue?** Email privately (see README)

## 📜 License

By contributing, you agree that your contributions will be licensed under the MIT License.

## 🙏 Thank You!

Your contributions make CMMC Watch better for everyone in the compliance community!

---

**Happy Contributing!** 🎉
