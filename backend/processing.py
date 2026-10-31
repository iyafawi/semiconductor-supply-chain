"""Explainable article matching and event risk. Functions have no network/DB side effects."""

import hashlib, html, json, math, re
from datetime import datetime, timezone
from pathlib import Path
from settings import (
    MAX_EVENT_DAYS,
    HALF_LIFE_HOURS,
    REGIONAL_WEIGHT,
    LOW_CONFIDENCE_WEIGHT,
    HIGH_RISK_THRESHOLD,
    MODERATE_RISK_THRESHOLD,
    JACCARD_THRESHOLD,
    CLUSTER_HOURS,
)

UTC = timezone.utc
RULES = [
    ("cyber_incident", ["ransomware", "cyberattack", "cyber attack", "cyber incident"]),
    ("natural_disaster", ["earthquake", "typhoon", "tsunami", "flood", "hurricane"]),
    (
        "trade_export_restriction",
        [
            "export control",
            "export restriction",
            "export ban",
            "sanctions",
            "entity list",
        ],
    ),
    (
        "labour",
        ["strike", "industrial action", "labour disruption", "labor disruption"],
    ),
    (
        "factory_disruption",
        [
            "factory fire",
            "plant fire",
            "shutdown",
            "shut down",
            "factory closure",
            "production halt",
            "production stopped",
            "outage",
        ],
    ),
    ("geopolitical", ["blockade", "military conflict", "invasion", "geopolitical"]),
    (
        "logistics",
        [
            "port congestion",
            "shipping delay",
            "logistics disruption",
            "supply disruption",
            "shipping disruption",
        ],
    ),
    (
        "capacity_constraint",
        ["capacity constraint", "capacity shortage", "shortage", "capacity bottleneck"],
    ),
    ("other", ["disruption", "production interruption"]),
]
SEMICONDUCTOR_TERMS = [
    "semiconductor",
    "chip",
    "wafer",
    "foundry",
    " fab ",
    "hbm",
    "dram",
    "memory",
    "packaging",
    "interposer",
    "substrate",
    "lithography",
    "photoresist",
]
STOPWORDS = set(
    "a an the and or at in on of to for from with after by is are was were has have its as this that amid over says said company companies".split()
)
COUNTRY_ALIASES = {
    "Taiwan": ["Taiwan", "Hsinchu", "Taichung", "Tainan"],
    "South Korea": ["South Korea", "Korea", "Icheon", "Cheongju"],
    "United States": ["United States", "U.S.", "USA"],
    "China": ["China", "Shanghai", "Beijing"],
    "Japan": ["Japan", "Kumamoto"],
    "Germany": ["Germany"],
    "Netherlands": ["Netherlands"],
    "Switzerland": ["Switzerland"],
    "France": ["France"],
}
NEGATED = r"\b(no (?:impact|disruption|damage)|unaffected|not affected|resumed|recovered|restored|normal operations|no production impact)\b"
UNCERTAIN = r"\b(could|may|might|potential|risk of|if |planned|plans|planning|proposed|expected|last year|years ago)\b"
ACTIVE = r"\b(halted|suspended|stopped|shut down|shutdown|closed|disrupted|outage|evacuated|hit by|operations interrupted)\b"


def utcnow():
    return datetime.now(UTC)


def iso(value):
    return value.astimezone(UTC).isoformat()


def parse_time(value):
    if isinstance(value, datetime):
        return (
            value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
        )
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def clean(value):
    return re.sub(
        r"\s+", " ", re.sub("<[^>]+>", " ", html.unescape(str(value or "")))
    ).strip()


def tokens(value):
    return set(
        t
        for t in re.findall(r"[a-z0-9]+", clean(value).lower())
        if len(t) > 1 and t not in STOPWORDS
    )


def jaccard(a, b):
    union = a | b
    return len(a & b) / len(union) if union else 0


def mention(text, name):
    return bool(re.search(r"(?<!\w)" + re.escape(name) + r"(?!\w)", text, re.I))


def aliases_for(s):
    mapping = json.loads((Path(__file__).parent / "aliases.json").read_text())
    return list(set([s["name"]] + mapping.get(str(s["id"]), [])))


def distance_km(lat1, lon1, lat2, lon2):
    a, b = math.radians(lat1), math.radians(lat2)
    dlat, dlon = b - a, math.radians(lon2 - lon1)
    h = math.sin(dlat / 2) ** 2 + math.cos(a) * math.cos(b) * math.sin(dlon / 2) ** 2
    return 6371 * 2 * math.asin(min(1, math.sqrt(h)))


def classify(article, network, now=None):
    now = now or utcnow()
    published = parse_time(article["published_at"])
    if (
        published > now.replace(microsecond=0)
        and (published - now).total_seconds() > 3600
    ):
        return None, "future timestamp"
    if (now - published).total_seconds() > MAX_EVENT_DAYS * 86400:
        return None, "outside active window"
    text = clean(article["title"] + " " + article.get("description", ""))
    direct = [
        s for s in network["suppliers"] if any(mention(text, a) for a in aliases_for(s))
    ]
    event_type = next(
        (kind for kind, terms in RULES if any(mention(text, t.strip()) for t in terms)),
        None,
    )
    matched = []
    countries = []
    confidence = 0.75
    if article.get("geo"):
        geo = article["geo"]
        magnitude = geo["magnitude"]
        if magnitude < float(geo.get("minimum_magnitude", 4.5)):
            return None, "below earthquake threshold"
        nearby = [
            s
            for s in network["suppliers"]
            if distance_km(s["lat"], s["lon"], geo["lat"], geo["lon"])
            <= geo.get("radius_km", 300)
        ]
        if not nearby:
            return None, "earthquake outside tracked supplier radius"
        matched = [
            {
                "supplier_id": s["id"],
                "match_type": "regional",
                "exposure_status": "potential_exposure",
            }
            for s in nearby
        ]
        countries = list(set(s["country"] for s in nearby))
        event_type = "natural_disaster"
        confidence = 0.9
        severity = min(1, max(0.25, (magnitude - 3) / 4))
        explanation = f"USGS M{magnitude:g} earthquake within {geo.get('radius_km',300)} km of illustrative supplier locations. Geographic exposure only; facility damage is not established."
    else:
        if not event_type:
            return None, "no disruption terms"
        if not direct and not any(
            mention(text, t.strip()) for t in SEMICONDUCTOR_TERMS
        ):
            return None, "not semiconductor relevant"
        countries = [
            c
            for c in set(s["country"] for s in network["suppliers"])
            if any(mention(text, a) for a in COUNTRY_ALIASES.get(c, [c]))
        ]
        if not direct and not countries:
            return None, "no tracked supplier or region match"
        # Only explicit present disruption in the supplier's own sentence can be confirmed.
        for s in direct:
            sentences = [
                line
                for line in re.split(r"(?<=[.!?])\s+", text)
                if any(mention(line, a) for a in aliases_for(s))
            ]
            confirmed = any(
                re.search(ACTIVE, line, re.I)
                and not re.search(NEGATED, line, re.I)
                and not re.search(UNCERTAIN, line, re.I)
                for line in sentences
            )
            negated = sentences and all(
                re.search(NEGATED, line, re.I) for line in sentences
            )
            if negated:
                continue
            matched.append(
                {
                    "supplier_id": s["id"],
                    "match_type": "direct",
                    "exposure_status": (
                        "confirmed_report" if confirmed else "potential_exposure"
                    ),
                }
            )
        # A country mentioned alongside direct suppliers is context, not evidence against every supplier.
        if not direct:
            if re.search(NEGATED, text, re.I):
                return None, "explicitly negated disruption"
            matched += [
                {
                    "supplier_id": s["id"],
                    "match_type": "regional",
                    "exposure_status": "potential_exposure",
                }
                for s in network["suppliers"]
                if s["country"] in countries
            ]
        if not matched:
            return None, "no supported exposure after negation checks"
        uncertain = bool(re.search(UNCERTAIN, text, re.I))
        confidence = (
            0.45
            if uncertain
            else (
                0.8
                if any(m["exposure_status"] == "confirmed_report" for m in matched)
                else 0.65
            )
        )
        severity = (
            0.9
            if re.search(
                r"\b(shutdown|shut down|halted|outage|ransomware|blockade|production stopped)\b",
                text,
                re.I,
            )
            else (
                0.65
                if event_type
                in [
                    "trade_export_restriction",
                    "natural_disaster",
                    "factory_disruption",
                ]
                else 0.4
            )
        )
        explanation = f"Keyword taxonomy matched {event_type}; {'named supplier with reported operational interruption' if any(m['exposure_status']=='confirmed_report' for m in matched) else 'potential exposure; no confirmed supplier interruption'}. {'Uncertain or historical wording lowers confidence.' if uncertain else 'Rule-based classification; source claim has not been independently verified.'}"
    published_confidence = article.get("published_time_confidence", 1)
    confidence *= published_confidence
    if confidence < 0.55:
        matched = [{**m, "exposure_status": "low_confidence"} for m in matched]
    status = (
        "confirmed_report"
        if any(m["exposure_status"] == "confirmed_report" for m in matched)
        else "low_confidence" if confidence < 0.55 else "potential_exposure"
    )
    return {
        "id": hashlib.sha256((article["id"] + event_type).encode()).hexdigest(),
        "title": article["title"],
        "description": article["description"],
        "event_type": event_type,
        "category": event_type.replace("_", " ").title(),
        "severity": severity,
        "confidence": round(confidence, 3),
        "classification_confidence": round(confidence, 3),
        "credibility": article["credibility"],
        "region": ", ".join(
            countries
            or sorted(
                set(
                    s["country"]
                    for s in network["suppliers"]
                    if s["id"] in [m["supplier_id"] for m in matched]
                )
            )
        ),
        "first_seen": article["retrieved_at"],
        "last_seen": article["retrieved_at"],
        "published_at": article["published_at"],
        "status": status,
        "explanation": explanation,
        "matches": matched,
        "sources": [
            {
                "name": article["source"],
                "id": article["source_id"],
                "url": article["url"],
                "article_id": article["id"],
                "credibility": article["credibility"],
            }
        ],
        "articles": [article["id"]],
        "tokens": sorted(tokens(article["title"])),
        **({"geo": article["geo"]} if article.get("geo") else {}),
    }, "relevant"


def find_cluster(event, existing):
    for other in existing:
        if other["event_type"] != event["event_type"]:
            continue
        if event.get("geo") or other.get("geo"):
            # Different earthquakes remain distinct even if headline tokens overlap.
            if event.get("geo", {}).get("external_id") != other.get("geo", {}).get(
                "external_id"
            ) or not event.get("geo", {}).get("external_id"):
                continue
        if (
            abs(
                (
                    parse_time(other["published_at"])
                    - parse_time(event["published_at"])
                ).total_seconds()
            )
            > CLUSTER_HOURS * 3600
        ):
            continue
        target_a = {(m["supplier_id"], m["match_type"]) for m in event["matches"]}
        target_b = {(m["supplier_id"], m["match_type"]) for m in other["matches"]}
        if target_a != target_b:
            continue
        if jaccard(set(event["tokens"]), set(other["tokens"])) >= JACCARD_THRESHOLD:
            return other
    return None


def merge_event(old, new):
    sources = {s["article_id"]: s for s in old["sources"] + new["sources"]}
    independent = len(set(s["id"] for s in sources.values()))
    base = max(
        old.get("classification_confidence", old["confidence"]),
        new.get("classification_confidence", new["confidence"]),
    )
    confidence = min(0.95, base + min(0.1, 0.05 * (independent - 1)))
    # No recency reset from syndicated re-reporting; decay uses earliest publication.
    return {
        **old,
        "last_seen": new["last_seen"],
        "published_at": min(old["published_at"], new["published_at"]),
        "severity": max(old["severity"], new["severity"]),
        "credibility": max(old["credibility"], new["credibility"]),
        "classification_confidence": base,
        "confidence": confidence,
        "sources": list(sources.values()),
        "articles": sorted(set(old["articles"] + new["articles"])),
    }


def event_risk(event, now=None):
    now = now or utcnow()
    age = max(0, (now - parse_time(event["published_at"])).total_seconds() / 3600)
    if age > MAX_EVENT_DAYS * 24:
        return 0
    return round(
        event["severity"]
        * event["credibility"]
        * event["confidence"]
        * 2 ** (-age / HALF_LIFE_HOURS),
        4,
    )


def risk_band(value):
    return (
        "High"
        if value >= HIGH_RISK_THRESHOLD
        else "Moderate" if value >= MODERATE_RISK_THRESHOLD else "Low"
    )


def supplier_risks(network, events, now=None):
    now = now or utcnow()
    result = []
    for s in network["suppliers"]:
        exposed = []
        for e in events:
            match = next((m for m in e["matches"] if m["supplier_id"] == s["id"]), None)
            if not match:
                continue
            score = event_risk(e, now)
            if not score:
                continue
            weight = REGIONAL_WEIGHT if match["match_type"] == "regional" else 1
            if match["exposure_status"] == "low_confidence":
                weight *= LOW_CONFIDENCE_WEIGHT
            exposed.append(
                {
                    **e,
                    "supplier": s["id"],
                    "country": (
                        s["country"] if match["match_type"] == "regional" else None
                    ),
                    "match_type": match["match_type"],
                    "exposure_status": match["exposure_status"],
                    "event_risk": score,
                    "supplier_risk": round(score * weight, 4),
                    "time": e["published_at"],
                }
            )
        top = max(exposed, key=lambda e: e["supplier_risk"], default=None)
        value = top["supplier_risk"] if top else 0
        result.append(
            {
                "supplier_id": s["id"],
                "current_live_risk": value,
                "risk": risk_band(value),
                "active_event_id": top["id"] if top else None,
                "updated_at": iso(now),
                "events": exposed,
                "exposure_status": (
                    top["exposure_status"] if top else "no_active_signal"
                ),
            }
        )
    return result
