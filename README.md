# Autonomous News Curation Agent

An intelligent web browsing agent that automatically extracts, fact-checks, and summarizes content from diverse sources including news articles, Twitter/X posts, and SEC filings.

## Features

- **Multi-Source Extraction**: Handles news articles, blog posts, Twitter/X threads, and SEC 13F filings
- **Universal Fact-Checking**: All content is verified against multiple fact-checking databases before summarization
- **Structured Summaries**: Outputs consistent, schema-validated summaries with executive summary, key points, sentiment, entities, and implications
- **Paywall Handling**: Falls back to Wayback Machine for soft-paywalled content
- **Cloud Browser Support**: Optional Browserless.io integration for better anti-detection
- **Multiple Export Formats**: PDF reports, executive prep documents, and Markdown slides
- **Streamlit Dashboard**: Interactive web UI for processing and viewing results
- **Cost-Efficient**: Designed for internal use at ~$0-50/month for 200 links

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      URL Input (API/CLI)                         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        URL Router                                │
│  Detects: Twitter/X | News Article | Blog | SEC Filing          │
└─────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│ Twitter Extractor│ │ Article Extractor│ │   SEC Extractor  │
│ (Syndication API)│ │  (Trafilatura)   │ │  (HTML Parser)   │
└──────────────────┘ └──────────────────┘ └──────────────────┘
              │               │               │
              │        ┌──────┴──────┐        │
              │        ▼             │        │
              │  ┌──────────────┐    │        │
              │  │Wayback Machine│   │        │
              │  │  (Paywalls)   │   │        │
              │  └──────────────┘    │        │
              │        │             │        │
              └────────┼─────────────┼────────┘
                       ▼             ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Fact-Checking Layer                          │
│  Google Fact Check API | ClaimBuster (optional) | NewsGuard     │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   LLM Summarizer (Gemini/Grok)                   │
│  Structured Output: Summary, Key Points, Entities, Sentiment    │
└─────────────────────────────────────────────────────────────────┘
                              │
       ┌──────────────────────┼──────────────────────┐
       ▼                      ▼                      ▼
┌────────────────┐   ┌─────────────────┐   ┌─────────────────┐
│   Database     │   │  Export Module  │   │  Slides Deck    │
│  (Firestore/   │   │   PDF Report    │   │   (Markdown)    │
│   Supabase)    │   │  Prep Document  │   │  Marp/reveal.js │
└────────────────┘   └─────────────────┘   └─────────────────┘
```

## Supported Sources

| Source Type | Examples | Extraction Method |
|-------------|----------|-------------------|
| News Articles | Bloomberg, WSJ, Economist, Wccftech | Trafilatura (F1: 0.937) |
| Tech Blogs | blog.google, openai.com/index | Trafilatura |
| Twitter/X | x.com/username/status/... | Syndication API (free) |
| SEC Filings | 13f.info, sec.gov | Custom HTML parser |
| Paywalled Content | Soft paywalls only | Wayback Machine fallback |

## Output Schema

Every processed URL returns a structured summary:

```json
{
  "url": "https://example.com/article",
  "source_type": "news_article",
  "extracted_at": "2025-12-19T12:00:00Z",
  "content": {
    "title": "Article Title",
    "author": "Author Name",
    "published_date": "2025-12-18",
    "word_count": 1500
  },
  "summary": {
    "executive_summary": "One paragraph overview...",
    "key_points": [
      "First major point",
      "Second major point",
      "Third major point"
    ],
    "sentiment": "neutral",
    "entities": [
      {"text": "OpenAI", "type": "ORG"},
      {"text": "Sam Altman", "type": "PERSON"}
    ],
    "implications": [
      "Market impact assessment",
      "Industry trend indication"
    ],
    "footnotes": [
      {"id": 1, "source_text": "Quote from article", "context": "Supporting detail"}
    ]
  },
  "fact_check": {
    "claims_analyzed": 3,
    "verified_claims": [
      {
        "claim": "Company X raised $100M",
        "rating": "verified",
        "source": "PolitiFact",
        "url": "https://..."
      }
    ],
    "unverified_claims": [],
    "publisher_credibility": {
      "score": 85,
      "source": "NewsGuard"
    }
  }
}
```

## Quick Start

### Prerequisites

- Python 3.11+
- Google Cloud account (for Gemini API)
- Firebase or Supabase account (for storage)

### Installation

```bash
# Clone the repository
git clone https://github.com/your-org/operatorNewsCuration.git
cd operatorNewsCuration

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env
```

### Configuration

Edit `.env` with your API keys:

```bash
# Required
GEMINI_API_KEY=your_gemini_api_key          # From https://makersuite.google.com/app/apikey
GOOGLE_FACT_CHECK_API_KEY=your_api_key      # From Google Cloud Console

# Optional - Cloud browser (better anti-detection)
BROWSERLESS_API_KEY=your_key                # Free trial at https://browserless.io
BROWSERLESS_USE_UNBLOCK=true                # Enable /unblock API fallback (default: true)
BROWSERLESS_USE_RESIDENTIAL_PROXY=false     # Paid feature for better bypass

# Storage (choose one)
FIREBASE_CREDENTIALS_PATH=./firebase-creds.json
# OR
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_supabase_anon_key

# Optional - Paid fact-checking services
CLAIMBUSTER_API_KEY=your_key                # $50/month - Enhanced claim detection
NEWSGUARD_API_KEY=your_key                  # $200+/month - Publisher credibility
```

#### Browserless.io (Optional)

For better success with sites that block scrapers, you can use [Browserless.io](https://browserless.io) as a cloud browser backend:

1. Sign up for a free trial at https://browserless.io
2. Copy your API key from the dashboard
3. Add `BROWSERLESS_API_KEY=your_key` to your `.env` file

When the API key is set, the agent will automatically use Browserless instead of local Playwright. This provides:
- Better anti-detection with rotating proxies
- No need to install Chromium locally
- More reliable extraction from protected sites

**Additional Browserless Options:**

```bash
# Enable /unblock API fallback for aggressive bot detection bypass (default: true)
BROWSERLESS_USE_UNBLOCK=true

# Use residential proxy with /unblock API (paid feature, default: false)
BROWSERLESS_USE_RESIDENTIAL_PROXY=false
```

The `/unblock` API is automatically used as a fallback when standard browser extraction fails. It provides enhanced bot detection bypass capabilities including:
- Built-in stealth and anti-detection
- Automatic retry with exponential backoff on transient failures
- Support for `waitForTimeout` and `waitForSelector` options

### Usage

#### Streamlit Dashboard (Recommended)

The easiest way to use the agent is through the Streamlit web interface:

```bash
# Start the Streamlit dashboard
streamlit run src/streamlit_app.py
```

This opens a browser at `http://localhost:8501` with:
- Single URL processing with live progress
- Batch processing via text input or file upload
- Interactive results display with sentiment, entities, and fact-check data
- JSON export for all results
- Processing history in the sidebar

#### CLI Mode

```bash
# Process a single URL
python -m src.cli process "https://blog.google/products/gemini/gemini-3-flash/"

# Process multiple URLs from file
python -m src.cli batch urls.txt --output results.json

# Process with PDF export
python -m src.cli process "https://example.com/article" --pdf output.pdf
```

#### API Mode

```bash
# Start the API server
uvicorn src.api.main:app --reload

# Submit URLs via API
curl -X POST http://localhost:8000/api/submit \
  -H "Content-Type: application/json" \
  -d '{"urls": ["https://example.com/article1", "https://x.com/user/status/123"]}'

# Get results
curl http://localhost:8000/api/results/{job_id}
```

#### Python SDK

```python
from src.agent import NewsAgent

agent = NewsAgent()

# Process single URL
result = await agent.process("https://blog.google/products/gemini/gemini-3-flash/")
print(result.summary.executive_summary)

# Process batch
results = await agent.process_batch([
    "https://x.com/arcprize/status/2001330153902023157",
    "https://openai.com/index/frontierscience/",
    "https://www.bloomberg.com/news/..."
])
```

### Export Formats

The agent supports multiple export formats for different use cases:

#### PDF Report (Technical)
Detailed per-article reports with full extraction data, entities, fact-check results, and footnotes.

```python
from src.export import PDFReportGenerator

generator = PDFReportGenerator()
pdf_bytes = generator.generate(result)           # Single result
pdf_bytes = generator.generate_batch(results)   # Multiple results
```

#### Prep Document (Executive Briefing)
Theme-grouped PDF briefings with "Why It Matters" analysis for executive consumption.

```python
from src.export import PrepDocumentGenerator

generator = PrepDocumentGenerator()
pdf_bytes = generator.generate(results)  # Batch results with theme grouping
```

Features:
- Cover page with statistics
- Executive summary with sentiment breakdown
- Theme-based article grouping (AI Models, Infrastructure, M&A, Research, Industry)
- "Why It Matters" strategic implications section
- Failed sources appendix

#### Slides Deck (Presentations)
Marp-compatible Markdown slides for presentations (works with reveal.js, Slidev).

```python
from src.export import SlidesDeckGenerator

generator = SlidesDeckGenerator()
markdown = generator.generate(results)  # Returns Markdown string
```

Features:
- Title and agenda slides
- Theme divider slides
- Article slides with bullet points
- Speaker notes in HTML comments
- Summary slide with key takeaways

## Cost Analysis

### Estimated Monthly Cost (200 links/month)

| Component | Free Tier | With Paid Options |
|-----------|-----------|-------------------|
| **LLM (Gemini 1.5 Flash)** | $1-2 | $1-2 |
| **Google Fact Check API** | $0 | $0 |
| **ClaimBuster API** | - | +$50 |
| **NewsGuard API** | - | +$200 |
| **Firebase/Supabase** | $0 | $0 |
| **GCP Cloud Run** | $0 | $0 |
| **Total** | **$1-2/month** | **$50-250/month** |

### LLM Provider Options

| Provider | Model | Input Cost | Output Cost | Notes |
|----------|-------|------------|-------------|-------|
| **Gemini 1.5 Flash** | gemini-1.5-flash | $0.075/1M | $0.30/1M | Recommended |
| Gemini 2.0 Flash | gemini-2.0-flash-exp | FREE | FREE | Preview only |
| Grok | grok-beta | $5/1M | $15/1M | Higher cost |

### Fact-Checking Services

| Service | Cost | Coverage | Best For |
|---------|------|----------|----------|
| **Google Fact Check API** | FREE | Global aggregator | Default choice |
| ClaimBuster | $50/mo | AI claim detection | Claim-worthiness scoring |
| NewsGuard | $200+/mo | Publisher ratings | Source credibility |
| Full Fact | Custom | UK-focused | UK political content |
| Factmata | Enterprise | Real-time | High-volume needs |

## Project Structure

```
operatorNewsCuration/
├── src/
│   ├── extractors/
│   │   ├── __init__.py
│   │   ├── base.py           # Abstract extractor interface
│   │   ├── twitter.py        # Twitter/X extraction
│   │   ├── article.py        # News article extraction
│   │   └── sec_filings.py    # SEC 13F extraction
│   ├── enrichment/
│   │   ├── __init__.py
│   │   ├── fact_check.py     # Fact-checking orchestrator
│   │   ├── google_fc.py      # Google Fact Check API
│   │   ├── claimbuster.py    # ClaimBuster integration
│   │   ├── newsguard.py      # NewsGuard integration
│   │   └── wayback.py        # Wayback Machine fallback
│   ├── summarizer/
│   │   ├── __init__.py
│   │   ├── llm.py            # LLM abstraction layer
│   │   └── prompts.py        # Summarization prompts
│   ├── export/
│   │   ├── __init__.py
│   │   ├── pdf_report.py     # Detailed PDF report generator
│   │   ├── prep_document.py  # Executive briefing PDF generator
│   │   ├── slides_deck.py    # Markdown slides generator
│   │   └── utils.py          # Shared utilities (themes, colors)
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py        # Pydantic models
│   ├── api/
│   │   ├── __init__.py
│   │   └── main.py           # FastAPI application
│   ├── agent.py              # Main agent orchestrator
│   ├── cli.py                # CLI interface
│   ├── config.py             # Configuration management
│   └── streamlit_app.py      # Streamlit web dashboard
├── tests/
│   ├── test_extractors.py
│   ├── test_fact_check.py
│   ├── test_pdf_export.py
│   └── test_summarizer.py
├── .env.example
├── .gitignore
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

## Deployment

### Local Development

```bash
# Run Streamlit dashboard (recommended for single-user)
streamlit run src/streamlit_app.py

# Or run FastAPI server (for programmatic access)
uvicorn src.api.main:app --reload --port 8000
```

### Docker

```bash
# Build image
docker build -t news-agent .

# Run container
docker run -p 8000:8000 --env-file .env news-agent
```

### Google Cloud Run

```bash
# Deploy to Cloud Run
gcloud run deploy news-agent \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars "GEMINI_API_KEY=$GEMINI_API_KEY"
```

## Limitations

- **Hard Paywalls**: Cannot bypass paywalls requiring login (WSJ, Bloomberg premium)
- **Twitter Rate Limits**: Syndication API has undocumented rate limits
- **Fact-Check Coverage**: Limited for non-English content and recent claims
- **SEC Filings**: Only supports 13F format from 13f.info currently

## Roadmap

- [x] PDF report export (detailed per-article reports)
- [x] Executive prep document export (theme-grouped briefings)
- [x] Slides deck export (Marp/reveal.js Markdown)
- [x] Streamlit frontend dashboard
- [ ] React frontend dashboard (for multi-user deployment)
- [ ] Slack/Discord integration
- [ ] Scheduled URL monitoring
- [x] Cloud browser support (Browserless.io)
- [ ] Multi-language support
- [ ] PDF export with charts and data visualizations

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

- [Trafilatura](https://github.com/adbar/trafilatura) - Content extraction
- [Instructor](https://github.com/jxnl/instructor) - Structured LLM outputs
- [Google Fact Check Tools](https://toolbox.google.com/factcheck/explorer) - Fact verification
- [Wayback Machine](https://archive.org/web/) - Archived content access
- [Browserless.io](https://browserless.io) - Cloud browser infrastructure
- [Streamlit](https://streamlit.io) - Web dashboard framework
- [fpdf2](https://github.com/py-pdf/fpdf2) - PDF generation
- [Marp](https://marp.app/) - Markdown presentation ecosystem

