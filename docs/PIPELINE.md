# Pipeline and data quality

## Collection and provenance

`settings.sources()` loads the configured feeds and adds OpenAI when `OPENAI_NEWS_ENABLED=true`. `worker.run_once()` fetches each independently. The worker waits `INGESTION_POLL_SECONDS` after a completed cycle (clamped to 300–600 seconds). A SQL application lock prevents simultaneous workers.

OpenAI calls the Responses API with `web_search`, live access enabled and tool choice required. It requests at most 10 articles from the past seven days per cycle. It is a bounded discovery query, not an exhaustive search of every tracked supplier. The model is configurable. [Official web-search documentation](https://developers.openai.com/api/docs/guides/tools-web-search).

The parser requires a completed search and response, valid JSON, a cited HTTPS URL and a recent publication timestamp. Unsupported records are dropped; an entirely invalid nonempty response fails the source. An empty result is valid. The model's date and summary are still unverified interpretations. The application does not fetch each full article to independently verify them.

OpenAI articles are labeled “OpenAI web search (AI summary)”. The source URL is preserved and clickable. Their publication confidence is reduced so rule processing cannot label them as confirmed interruptions. A search citation establishes provenance, not truth.

## Cleaning and relevance

Text is stripped of markup and normalized for whitespace. URLs lose common tracking parameters. A source ID plus external ID or canonical URL produces a stable article identifier. Cross-source duplicates may still arrive as separate articles; event clustering handles similar reports.

Articles are stored before relevance processing. Classification rejects future dates, events outside the seven-day window, unrelated text and unsupported supplier or region matches. Categories cover disasters, factory disruption, trade restrictions, logistics, cyber incidents, labour events and capacity constraints.

Supplier aliases use word boundaries. Direct matching considers the sentence containing the supplier and checks for negation or uncertainty. Geographic matches indicate possible exposure only. Source failures, processing reasons and retrieval timestamps remain inspectable.

## Supplier impact

The network connects suppliers to components, not every tier of a verified industrial supply chain. After matching an event to suppliers, the dashboard exposes their component relationships. A simulation removes selected suppliers from a temporary calculation and counts remaining alternatives. It does not estimate lost production, revenue, inventory or recovery time.

## Scoring

Event score = severity × source credibility × matching confidence × recency.

Recency = 2 ^ (−age in hours / 48). Events expire after seven days. Regional matches receive a 0.65 multiplier; low-confidence matches receive a further 0.5 multiplier. A supplier takes its maximum active contribution, rather than adding repeated coverage.

Structural criticality = sum(component importance / supplier count), normalized to the highest supplier. This measures importance within the illustrative network, separately from current news exposure.

Thresholds and credibility values are heuristics, not calibrated probabilities. The maximum rule may understate multiple independent threats. Matching rules can miss complex language. New or unfamiliar supplier aliases require maintenance.

## Persistence and display

SQL Server stores articles, interpreted events, evidence links, supplier matches, source status and risk histories. FastAPI reads that evidence and serves the React application. The browser polls after each completed refresh, avoiding overlapping cycles. No database or feed failure is replaced by fabricated live news.
