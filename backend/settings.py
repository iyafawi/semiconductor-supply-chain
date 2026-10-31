"""Visible, configurable risk weights. No credentials live in source control."""
import json, os
from pathlib import Path
from dotenv import load_dotenv
ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env')
POLL_SECONDS = max(300, min(600, int(os.getenv('INGESTION_POLL_SECONDS', '600'))))
MAX_EVENT_DAYS = int(os.getenv('MAX_EVENT_DAYS', '7'))
HALF_LIFE_HOURS = float(os.getenv('RISK_HALF_LIFE_HOURS', '48'))
JACCARD_THRESHOLD = float(os.getenv('EVENT_JACCARD_THRESHOLD', '.65'))
CLUSTER_HOURS = float(os.getenv('EVENT_CLUSTER_HOURS', '48'))
REGIONAL_WEIGHT = float(os.getenv('REGIONAL_EXPOSURE_WEIGHT', '.65'))
LOW_CONFIDENCE_WEIGHT = float(os.getenv('LOW_CONFIDENCE_WEIGHT', '.5'))
HIGH_RISK_THRESHOLD = float(os.getenv('HIGH_RISK_THRESHOLD', '.45'))
MODERATE_RISK_THRESHOLD = float(os.getenv('MODERATE_RISK_THRESHOLD', '.15'))
ALERT_CRITICALITY_THRESHOLD = float(os.getenv('ALERT_CRITICALITY_THRESHOLD', '50'))
SOURCE_PATH = Path(os.getenv('SOURCE_CONFIG', str(ROOT / 'backend' / 'sources.json')))

def sources():
    data = json.loads(SOURCE_PATH.read_text(encoding='utf-8'))
    if os.getenv('OPENAI_NEWS_ENABLED', 'false').lower() in ('true', '1', 'yes'):
        data.append({'id': 'openai-web-search', 'name': 'OpenAI web search (AI summary)',
                     'kind': 'openai_search', 'url': 'https://api.openai.com/v1/responses',
                     'credibility': .6})
    return [s for s in data if s.get('enabled', True)]

def public_weights():
    return dict(half_life_hours=HALF_LIFE_HOURS, regional_weight=REGIONAL_WEIGHT,
                low_confidence_weight=LOW_CONFIDENCE_WEIGHT, high_threshold=HIGH_RISK_THRESHOLD,
                moderate_threshold=MODERATE_RISK_THRESHOLD, criticality_threshold=ALERT_CRITICALITY_THRESHOLD,
                jaccard_threshold=JACCARD_THRESHOLD, cluster_hours=CLUSTER_HOURS, max_event_days=MAX_EVENT_DAYS)
