# Changelog
 
All notable changes to MuckScraper are documented here.
 
---

## [0.5.0] - 2026-06-03

Status: beta candidate. MuckScraper is moving from early alpha into beta: the
core fetch, grouping, admin, and edition workflows are now usable end-to-end on a
fresh install, while source balance, scrape quality, and headline-selection
tuning remain active areas of work.

### Added

- **Fresh-install bootstrap**:
  - `bootstrap_admin.py` initializes the database, stamps Alembic current for a fresh schema, and creates or updates the admin user from `.env`
  - `.env.sample` now includes `ADMIN_USERNAME`, `ADMIN_EMAIL`, and `ADMIN_PASSWORD`
  - README install flow now starts core services, runs bootstrap, then starts the scheduler
- **Admin and operations tooling**:
  - new Admin Tools page centralizes maintenance actions
  - Meilisearch-backed admin search support with rebuild/status endpoints
  - expanded troubleshooting guide for scheduler, database, scrape, and run-metric checks
- **Scrape telemetry expansion**:
  - persisted scrape status, method, failure reason, and HTTP status now flow through ingestion, retries, and admin tooling
  - scrape outcome history is stored over time for operational review
  - low-value article detection flags roundups, live updates, video pages, and weak/duplicative scrape output
- **Edition and headline hardening**:
  - same-event headline candidates are filtered before publish
  - edition backfill continues down the ranked list to preserve edition size after duplicate removals
  - editions are capped at 20 stories even after mixed-coverage reservation and balance fills
  - previous-edition repeats are suppressed unless the story has new articles
  - stories with leftish and rightish coverage are favored during edition selection
- **Source-balance and RSS enrichment**:
  - added targeted right/center-right and international sources including Reason, National Post, The Telegraph, Toronto Sun, Washington Examiner, Newsmax, and Daily Wire
  - added bias lookup/normalization support for new outlets
  - added left and right targeted enrichment passes around headline ranking
- **Summary quality guardrails**:
  - story summaries and deep reports now skip generation when no article has enough readable scraped content
  - prompt filtering reduces misgrouped/outlier articles before story summaries and deep reports
- **Archived edition images**:
  - edition-story image metadata is stored on `EditionStory`
  - archived local copies can be generated from story article images for stable published output
  - low-resolution headline images are filtered out instead of shown as blurry thumbnails
- **Grouping review fields** on articles to support higher-scrutiny grouping workflows
- **Updated README screenshots** for story reader, bias tags, and article reader

### Changed

- Docker Compose no longer includes personal Langfuse or n8n environment hooks by default
- README now treats n8n, Matrix notifications, and similar workflow hooks as optional personal integrations
- Flask app now runs through `boot.sh` and Gunicorn in the container
- Scheduler startup catch-up logic waits for the next scheduled run unless a scheduled slot was actually missed
- Static headline export now defaults to the latest edition instead of rebuilding every historical edition on every run
- `process_current_edition()` skips unchanged stable stories earlier instead of repeatedly reconsidering them for summary work
- Story grouping now eager-loads recent story articles for the hot matching path and logs the configured lookback window
- Scraper retry behavior keeps degraded domains cooled down even when a URL-level fallback succeeds
- High-cost scrape variant fan-out is skipped after strong terminal failures like `401`, `403`, `404`, and `410`
- Edition dedupe matching was tightened to reduce false positives driven by generic political/process words
- README and project map were cleaned up so public repo docs no longer depend on deployment-specific/private headline-site files

### Fixed

- Fresh installs failing when `create_admin.py` ran before the `users` table existed
- Compose warnings for removed personal Langfuse/n8n variables in default installs
- Real same-event duplicate clusters making it into the same published edition
- Editions occasionally exceeding the 20-story target during balance fill
- Repeated stories carrying forward unchanged from the immediately previous edition
- Summaries and deep reports hallucinating from title-only article sets with no readable content
- Excessive retry churn on chronically blocked scrape domains
- Misleading public docs and repo-map references to deployment-specific paths
- Confusing Alembic migration filename mismatch for the archived-edition-image revision

### Upgrade Notes

- For a fresh install:

  ```bash
  cp .env.sample .env
  # Edit .env with API keys, model host, database settings, and admin login
  docker compose up -d --build postgres meilisearch app
  docker compose exec app python bootstrap_admin.py
  docker compose up -d scheduler
  ```

- For an existing install, pull the update and run migrations:

  ```bash
  docker compose up -d --build
  docker compose exec app flask db upgrade
  ```

- `create_admin.py` still exists, but `bootstrap_admin.py` is now the recommended first-run setup path.
- Langfuse and n8n are no longer part of the default Compose environment. Add them with your own override/env wiring if you use those personal workflows.

---
 
## [0.4.0] - 2026-05-04
 
### Added
 
- **Edition deduplication hardening**:
  - `seen_story_ids` set added to `publish_edition()` candidate loop — prevents a story appearing twice if it exists multiple times in the candidate pool
  - Final `top_20` slice now runs through a dedup pass before slicing
  - `UniqueConstraint('edition_id', 'story_id')` added to `EditionStory` model as a database-level safety net
- **Repeat story window expanded** — edition eligibility check now looks back across all editions published in the last 24 hours, not just the immediately previous edition. Prevents stories from recycling by skipping a single cycle
- **Story age filter** — `publish_edition()` candidate query now filters to stories created within the last 3 days. Previously, high-scoring old stories could remain in the candidate pool indefinitely
- **Carried-over story age cap** — fallback carried stories capped at 48 hours old. Previously, arbitrarily old stories could pad an edition if fewer than 20 fresh stories were available
- **Unscraped single-article story exclusion** — stories with exactly one article and no scraped content are excluded from edition eligibility
- **Video prefix stripping in story grouper** — `strip_video_prefix()` strips "WATCH:", "VIDEO:", "LIVE:", "LISTEN:", "BREAKING:", "PHOTOS:", "GALLERY:" and `[WATCH]` variants before embedding and before LLM title comparison. Prevents media-type prefixes from distorting semantic similarity scores
- **Outlet name normalization** — `normalize_source_name()` expanded with partial-match patterns for all major outlets, eliminating feed-title variants like "NPR Topics: News", "Al Jazeera – Breaking News, World News and Video from Al Jazeera", "NYT > World News", "World news | The Guardian"
- **`merge_duplicate_outlets()` admin function** — normalizes all outlet names and merges duplicates. Accessible from admin hamburger menu as "Merge Duplicate Outlets". Returns renamed/deleted/reassigned counts
### Changed
 
- `LOWER_THRESHOLD` in `story_grouper.py` lowered from `0.80` to `0.68` — gives Ollama more opportunity to confirm semantically equivalent but differently worded headlines
- Embeddings now generated from `title + content[:200]` snippet rather than title alone — anchors similarity to event substance, not surface wording
- `merge_duplicate_outlets()` now uses raw SQL `UPDATE articles SET outlet_id = :canonical WHERE outlet_id = :dup` with a post-update verification count before executing `DELETE` — eliminates article orphaning on merge
### Fixed
 
- Duplicate story IDs appearing in the same edition (same story_id at multiple ranks)
- `merge_duplicate_outlets()` orphaning articles — articles were being left with `outlet_id = NULL` when duplicate outlet records were deleted before article reassignment completed
---
 
## [0.3.0] - 2026-04-14
 
### Added
 
- **Image capture and display** — `image_url` added to Article model, populated from NewsAPI (`urlToImage`) and GNews (`image`). Images shown in articles feed
- **`backfill_images.py`** — utility to backfill image URLs from stored raw API payloads
- **Langfuse observability** — all LLM calls instrumented with tracing across summarizer, story grouper, headline generator, outlet bias, topic classifier
- **Authentication** — Flask-Login based auth with login page, admin user creation script (`create_admin.py`), and protected admin routes
- **Blueprint architecture** — routes split into blueprints:
  - `admin.py` — all write and trigger routes requiring authentication
  - `auth.py` — login/logout
- **`filters.py`** — Jinja2 template filters extracted from app factory and registered via `register_filters(app)`
- **`constants.py`** — shared `TOPICS` and `AGGREGATORS` constants extracted from app factory
- **Scrape blocklist** — automatic detection and blocking of bad scrapes:
  - Strong indicators: login walls, captchas, bot detection, subscriber gates
  - Weak indicators: short content with sign-in/subscribe text
  - Duplicate detection: content near-identical to 2+ other articles from same outlet flagged as login/error page
  - Pre-populated permanent blocklist of hard-paywalled domains (NYT, WSJ, FT, Bloomberg, etc.)
  - `audit_existing_scrapes()` — retroactive scan of all stored content
  - `/scrape-blocklist` admin page — view blocked domains, unblock auto-blocked entries, trigger audit
- **New Alembic migrations**: `image_url` on articles and `scrape_blocklist` table
- **Gunicorn** — replaces Flask development server in production
### Changed
 
- Scheduler fetch times changed to 4 daily runs at 12am, 7am, 12pm, 6pm Eastern
- Scheduler categories restructured: Top News, World News, US Politics, Business & Economy, Science & Health, Technology, National Security & Foreign Policy
- `regroup_ungrouped_stories()` replaced O(n²) Python cosine loop with pgvector `<=>` nearest-neighbour SQL query
- Force Re-group button now requires confirmation before executing
- `create_app()` reduced to wiring only
### Fixed
 
- Duplicate `summarize_article` definition in `summarizer.py`
- `cleanup_duplicates.py` double app instantiation
- Alembic migration branch conflict
- Duplicate CSS block in `article.html`
---
 
## [0.2.2] - 2026-03-21
 
### Added
- **Collapsible sidebar** — toggle to icon-only mode, state saved in localStorage
- **Grouped Stories view** — dedicated `/multi-stories` page showing only stories with 2+ articles, paginated at 50
- **All Stories view** — explicit link in sidebar to view unfiltered stories
- **Sticky header** with hamburger menu (☰) — maintenance buttons moved from sidebar into a cleaner dropdown
- **Aggregator deduplication** — Yahoo News, Google News, MSN, AOL articles hidden per story when original source content exists
- **Local timezone conversion** — article dates displayed in user's local timezone via JavaScript
- **Published and fetched timestamps** — both the original publish date and MuckScraper fetch date shown per article
- **`fetched_at` column** added to Article model
- **Single linkage story matching** — new articles now compared against every article in a story for best similarity match, not just the first
- **Story ordering** by most recent article date instead of story creation date
- **`cleanup_duplicates.py`** — maintenance script for deduplicating articles (work in progress)
### Changed
- Maintenance buttons moved from sidebar footer to hamburger menu in header
- Sidebar now shows "All Stories" and "Grouped Stories" navigation links
### Fixed
- Story ordering now reflects latest news rather than when the story was first created
---
 
## [0.2.1] - 2026-03-20
 
### Added
- AI-generated wire service style headlines for multi-article stories
- Single-article story filter toggle — hide/show stories with only one article
- `headline_generator.py` — new module for story headline generation
- Headlines generated automatically when second article added to a story
- Headlines generated during Ollama catchup for existing multi-article stories
### Changed
- Replaced all `print()` statements with proper Python `logging` module across all news_fetcher files
- Story display now shows AI headline when available, falls back to auto-generated title
---
 
## [0.2.0] - 2026-03-19
 
### Added
- **pgvector story clustering** — replaced Ollama prompt-based grouping with vector embeddings using `nomic-embed-text`
- **LLM topic classifier** — articles classified into topics by Ollama based on content
- **Pagination** — 25 stories per page with prev/next navigation
- **Force Re-group button** — rebuilds all story groupings from scratch using vector similarity
- **Reclassify Topics button** — reclassifies all existing articles into the new topic system
- **Wake Ollama button** — sends Wake on LAN magic packet to Ollama machine
- **Per-article [scrape] button** — appears on articles missing full text
- **Global ↻ Scrape Missing button** — bulk re-scrapes up to 20 articles missing full text
- `python-readability` for smarter article content extraction
- Googlebot user agent fallback for soft-paywalled sites
- archive.ph fallback when all other scraping strategies fail
- DB indexes on articles and stories tables for faster queries
- Raw API payload storage with 30-day auto-cleanup
- `restart.sh` script for soft rebuilds that preserve the database
- Screenshots added to README
### Changed
- Topics redesigned — now 7 categories classified by LLM content analysis
- Scheduler fetch configurations updated
- TOPICS list simplified
### Fixed
- Ollama catchup button breaking article links and summarization
- Re-grouping creating new stories instead of only matching existing ones
- Auto-summarization capped to 10 stories per batch to prevent timeouts
- HTML tags being sent to Ollama in summaries
- Content snippet size increased from 500 to 1500 chars per article
- Force regroup foreign key violation on story_topics table
- numpy array boolean evaluation error in story grouper
---
 
## [0.1.3] - 2026-03-17
 
### Added
- `python-readability` for smarter article content extraction
- Googlebot user agent fallback for soft-paywalled sites
- archive.ph fallback when all other scraping strategies fail
- Per-article `[scrape]` button for articles missing full text
- Global ↻ Scrape Missing sidebar button
- DB indexes on key columns
- Raw API payload storage with 30-day auto-cleanup
- `restart.sh` script for soft rebuilds that preserve the database
### Fixed
- Ollama catchup button breaking article links and summarization
- Re-grouping creating new stories instead of only matching existing ones
- Auto-summarization capped to 10 stories per batch
- HTML tags being sent to Ollama in summaries
---
 
## [0.1.2] - 2026-03-13
 
### Added
- Full article scraping with BeautifulSoup and Playwright fallback
- Sanitized HTML storage for scraped articles
- Article reader page at `/article/<id>`
- LLM story grouping using keyword pre-filter and Ollama match decision
- Smart Brevity summary format
- Dark/light mode toggle with localStorage persistence
- Sticky sidebar with purple accent and drop shadow
- Ollama Catchup button
- Automatic Ollama catchup when scheduler detects Ollama came back online
- Smart restart timer
- `AppSetting` model for persisting state across container restarts
- Many-to-many topic tagging for articles and stories
- GNews as a second news source alongside NewsAPI
- `destroy.sh` and `restart.sh` maintenance scripts
- `.env` support for all credentials and configuration
### Fixed
- Race condition causing duplicate topic creation
- Scheduler running stale cached code after restarts
- `POSTGRES_USER` typo in `docker-compose.yml`
- Removed standalone `news_fetcher` container
---
 
## [0.1.0] - 2026-03-10
 
### Added
- Initial release
- Flask + PostgreSQL + Docker Compose setup
- NewsAPI integration with scheduled fetching every 3 hours
- Outlet-level political bias scoring via Ollama (1=Left to 5=Right)
- On-demand AI story summarization via Ollama
- Source blocklist for filtering unwanted domains and title patterns
- Ollama online/offline status indicator
- Per-article and per-outlet bias rating buttons
- MIT License
- README documentation
