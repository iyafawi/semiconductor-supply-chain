# Silicon Watch — private local live monitoring

The application runs entirely on your computer. Python retrieves real external feeds; SQL Server persists articles, events, sourcing records, current risk and risk history; FastAPI serves the processed records; React automatically refreshes. Runtime persistence has no SQLite, JSON, in-memory or mock fallback.

The 48 suppliers, 32 components, 303 relationships and supplier coordinates are an illustrative sourcing model. Live articles and earthquake reports are real. A nearby earthquake indicates potential exposure, not proven damage or production interruption.

## Start and stop

SQL Server 2025 Express (localhost\SQLEXPRESS), Microsoft ODBC Driver 18, the SiliconWatch database and dependencies are installed on this computer. In PowerShell, change to this folder and run:

~~~powershell
powershell -ExecutionPolicy Bypass -File .\start-local.ps1
~~~

Dashboard: http://127.0.0.1:5173. API documentation: http://127.0.0.1:8000/docs. The worker fetches immediately on startup, then every 10 minutes; React refreshes every 45 seconds. Services bind to localhost. Closing the browser does not stop monitoring.

~~~powershell
powershell -ExecutionPolicy Bypass -File .\stop-local.ps1
~~~

Stopping leaves SQL Server and all stored records intact. Logs are in .local-runtime/. Start refuses duplicate managed services; stop checks process IDs and startup times. Run as the Windows user with SQL Server access.

## Setup on another Windows computer

Install Python 3.11+ and Node.js 22+ (or use the detected Codex bundled runtimes). With permission to install SQL Server and ODBC:

~~~powershell
powershell -ExecutionPolicy Bypass -File .\setup-local.ps1 -InstallSqlServer
powershell -ExecutionPolicy Bypass -File .\start-local.ps1
~~~

If SQL Server exists, omit -InstallSqlServer and configure .env from .env.example. The default uses Windows integrated authentication, ODBC Driver 18, encryption and trust for the local SQL Server certificate. The Windows user needs initial database creation/migration permissions. Never place SQL credentials in frontend variables. Downloads and feeds require outbound internet access; inbound internet access is unnecessary.

## Pipeline and stack

1. backend/feeds.py fetches HTTPS RSS/JSON with timeouts, retries and conditional requests, normalizing source IDs, URLs, titles, summaries and publication/retrieval timestamps.
2. backend/worker.py stores raw articles in SQL Server before processing. Stable article IDs prevent repeat ingestion; a SQL application lock prevents duplicate workers. Feed failures are recorded independently.
3. backend/processing.py applies age/relevance/disruption filters, explicit supplier aliases and geographic exposure matching. It assigns taxonomy, severity, confidence and exposure status. Token Jaccard similarity, matched targets and a 48-hour window cluster duplicate reports. Distinct USGS event IDs remain separate.
4. backend/repository.py transactionally writes processing status, events and article/supplier mappings. It updates supplier and regional risk and appends both histories. Initialization seeds sourcing once; normal requests read SQL Server.
5. backend/main.py exposes FastAPI endpoints. src/live.js polls without overlapping requests and updates React. Database or stale-worker failure is visible; fabricated news is never substituted.

Frontend: React 19, Vite 7, Lucide, d3-geo. Backend: Python, FastAPI, uvicorn, httpx, feedparser, pyodbc. Persistence: Microsoft SQL Server Express and ODBC Driver 18. Natural Earth supplies static public-domain map geography. Optional OpenAI Responses web search discovers cited recent reports. Relevance matching and scoring remain rule based. See the root README for OpenAI configuration.

## Sources and settings

backend/sources.json configures Semiconductor Digest RSS, USGS magnitude 4.5+ weekly earthquake reports, and Federal Register Bureau of Industry and Security semiconductor documents. These three feeds require no keys. Optional OpenAI search requires OPENAI_API_KEY and OPENAI_NEWS_ENABLED=true. backend/aliases.json contains supplier aliases. Ordinary or old articles remain stored but do not become active risk events. Quiet periods may have zero signals.

.env.example documents polling, event age, decay, clustering, weights and CORS. Worker polling is constrained to 300–600 seconds; frontend to 30–60 seconds. Changes to VITE variables require npm run build with Node on PATH. Restart after backend changes.

## Risk model and limitations

Event risk = severity × source credibility × matching confidence × recency. Recency halves every 48 hours; events expire after seven days. Supplier risk is the maximum matched active contribution, so repeated coverage does not add severity. Regional matches receive a 0.65 weight; low-confidence matches an additional 0.5 weight. API responses expose configurable weights. High risk starts at 0.45; moderate at 0.15.

Structural criticality is separate: sum(component importance / supplier count), normalized to the highest supplier. A Critical alert requires high live risk, at most one alternative and criticality ≥50. Other elevated constrained suppliers are Investigate. Simulation removes selected suppliers from the illustrative graph without changing stored sourcing.

“Reported interruption” means a source explicitly reports interruption, not independent verification. Confidence is rule-based matching confidence, not a calibrated probability. Rules may miss indirect references or misclassify complex language. Geographic matching uses illustrative coordinates, not verified facilities. Selective feed coverage means no active signal never proves safety. Replace sourcing and coordinates with validated procurement data before operational decisions.

## SQL and API

backend/schema.sql and backend/migrations/002_live.sql define Supplier, Component, SupplyRelationship, Article, LiveEvent, EventArticle, EventSupplier, SupplierRisk, RegionalRisk, both history tables, SourceState, IngestionRun and SchemaMigration. Legacy RiskEvent remains for compatibility; live ingestion uses LiveEvent. Initialization is idempotent.

Endpoints include /api/health, /api/network, /api/analysis, /api/news/latest, /api/events/active, /api/alerts, /api/ingestion/status, /api/suppliers/{id}/risk, /api/suppliers/{id}/risk/history, /api/regions/{region}/risk, /api/scenarios and POST /api/simulate. See /docs. SQL failure gives explicit unavailability; individual source failure gives partial coverage; stale monitoring shows offline.

## Verification

~~~powershell
$env:SILICONWATCH_SQL_TESTS='1'
.\.venv\Scripts\python.exe -m unittest discover -s backend -v
node tests.mjs
npm run build
~~~

Unit tests cover aliases, relevance, negation, uncertainty, geography, decay, expiry, clustering and aggregation. Integration tests create/remove a separate real SQL Server database and check persistence, mappings, histories, feed failure, API, simulation and deduplication. Mock articles are restricted to automated tests. backend/test_browser_fixture.py enforces an isolated test-database name for verifying React automatic refresh through SQL and FastAPI.

The source package excludes .env, dependencies, runtime logs, database files and Git history. Use SQL Server backup tools to back up persistent data.
