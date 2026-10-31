"""SQL Server is the sole runtime persistence. No file or memory fallback."""

import json, os, re
from pathlib import Path
import pyodbc
from settings import ROOT, MAX_EVENT_DAYS, POLL_SECONDS
from processing import utcnow, iso, parse_time, event_risk, supplier_risks


class DatabaseUnavailable(RuntimeError):
    pass


def connect(connection_string=None, autocommit=False):
    value = connection_string or os.getenv("SQLSERVER_CONNECTION_STRING")
    if not value:
        raise DatabaseUnavailable("SQLSERVER_CONNECTION_STRING is not configured")
    try:
        return pyodbc.connect(value, autocommit=autocommit, timeout=5)
    except pyodbc.Error as exc:
        raise DatabaseUnavailable(
            "SQL Server connection unavailable; check local instance and ODBC driver"
        ) from exc


def sqltime(value):
    return parse_time(value).replace(tzinfo=None)


def timestamp(value):
    return (
        iso(value.replace(tzinfo=__import__("datetime").timezone.utc))
        if value
        else None
    )


class SqlRepository:
    def network(self):
        with connect() as db:
            c = db.cursor()
            suppliers = [
                json.loads(r[0])
                for r in c.execute("SELECT payload FROM dbo.Supplier ORDER BY id")
            ]
            components = [
                json.loads(r[0])
                for r in c.execute("SELECT payload FROM dbo.Component ORDER BY id")
            ]
            relationships = [
                {"supplier": r[0], "component": r[1]}
                for r in c.execute(
                    "SELECT supplier_id,component_id FROM dbo.SupplyRelationship"
                )
            ]
        if not suppliers:
            raise DatabaseUnavailable(
                "SQL Server sourcing tables are empty; run database initialization"
            )
        scenarios = [
            {
                "id": "s" + str(s["id"]),
                "name": s["name"] + " unavailable",
                "suppliers": [s["id"]],
            }
            for s in suppliers
        ]
        scenarios += [
            {
                "id": "r" + country,
                "name": country + " regional disruption",
                "suppliers": [s["id"] for s in suppliers if s["country"] == country],
            }
            for country in sorted(set(s["country"] for s in suppliers))
        ]
        return {
            "suppliers": [{**s, "risk": "Unknown"} for s in suppliers],
            "components": components,
            "relationships": relationships,
            "scenarios": scenarios,
            "events": [],
            "network_source": "sqlserver",
            "network_is_synthetic": True,
        }

    def health(self):
        with connect() as db:
            c = db.cursor()
            version = c.execute(
                "SELECT CAST(SERVERPROPERTY('ProductVersion') AS NVARCHAR(100))"
            ).fetchone()[0]
            c.execute(
                "SELECT TOP 1 version FROM dbo.SchemaMigration ORDER BY version DESC"
            ).fetchone()
            count = c.execute("SELECT COUNT(*) FROM dbo.Supplier").fetchone()[0]
        return {
            "database": "sqlserver",
            "database_connected": True,
            "database_version": version,
            "supplier_count": count,
        }

    def store_article(self, a):
        with connect() as db:
            c = db.cursor()
            row = c.execute(
                "SELECT processing_status FROM dbo.Article WITH (UPDLOCK,HOLDLOCK) WHERE id=?",
                a["id"],
            ).fetchone()
            if row:
                return False
            c.execute(
                "INSERT dbo.Article(id,source_id,source,title,description,url,published_at,retrieved_at,raw_metadata) VALUES(?,?,?,?,?,?,?,?,?)",
                a["id"],
                a["source_id"],
                a["source"],
                a["title"][:1000],
                a["description"],
                a["url"][:2048],
                sqltime(a["published_at"]),
                sqltime(a["retrieved_at"]),
                json.dumps(a, ensure_ascii=False),
            )
            db.commit()
            return True

    def pending_articles(self):
        with connect() as db:
            return [
                json.loads(r[0])
                for r in db.cursor().execute(
                    "SELECT TOP 500 raw_metadata FROM dbo.Article WHERE processing_status='pending' ORDER BY retrieved_at"
                )
            ]

    def finish_article(self, article_id, event, reason):
        with connect() as db:
            c = db.cursor()
            if event:
                e = event
                payload = json.dumps(e, ensure_ascii=False)
                exists = c.execute(
                    "SELECT id FROM dbo.LiveEvent WITH (UPDLOCK,HOLDLOCK) WHERE id=?",
                    e["id"],
                ).fetchone()
                values = (
                    e["event_type"],
                    e["title"][:1000],
                    e["severity"],
                    e["confidence"],
                    e["credibility"],
                    e["region"],
                    event_risk(e),
                    sqltime(e["first_seen"]),
                    sqltime(e["last_seen"]),
                    sqltime(e["published_at"]),
                    e["status"],
                    e["explanation"],
                    payload,
                    e["id"],
                )
                if exists:
                    c.execute(
                        "UPDATE dbo.LiveEvent SET event_type=?,title=?,severity=?,confidence=?,credibility=?,region=?,event_risk=?,first_seen=?,last_seen=?,published_at=?,status=?,explanation=?,payload=? WHERE id=?",
                        *values,
                    )
                else:
                    c.execute(
                        "INSERT dbo.LiveEvent(event_type,title,severity,confidence,credibility,region,event_risk,first_seen,last_seen,published_at,status,explanation,payload,id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        *values,
                    )
                for aid in e["articles"]:
                    c.execute(
                        "IF NOT EXISTS(SELECT 1 FROM dbo.EventArticle WHERE event_id=? AND article_id=?) INSERT dbo.EventArticle(event_id,article_id) VALUES(?,?)",
                        e["id"],
                        aid,
                        e["id"],
                        aid,
                    )
                for m in e["matches"]:
                    c.execute(
                        "IF NOT EXISTS(SELECT 1 FROM dbo.EventSupplier WHERE event_id=? AND supplier_id=?) INSERT dbo.EventSupplier(event_id,supplier_id,match_type,exposure_status) VALUES(?,?,?,?) ELSE UPDATE dbo.EventSupplier SET match_type=?,exposure_status=? WHERE event_id=? AND supplier_id=?",
                        e["id"],
                        m["supplier_id"],
                        e["id"],
                        m["supplier_id"],
                        m["match_type"],
                        m["exposure_status"],
                        m["match_type"],
                        m["exposure_status"],
                        e["id"],
                        m["supplier_id"],
                    )
            c.execute(
                "UPDATE dbo.Article SET processing_status=?,processing_reason=? WHERE id=?",
                "processed" if event else "filtered",
                reason[:500],
                article_id,
            )
            db.commit()

    def events(self):
        with connect() as db:
            rows = (
                db.cursor()
                .execute(
                    "SELECT payload FROM dbo.LiveEvent WHERE published_at>=DATEADD(day,?,SYSUTCDATETIME()) ORDER BY published_at DESC",
                    -MAX_EVENT_DAYS,
                )
                .fetchall()
            )
        return [json.loads(r[0]) for r in rows]

    def update_risks(self, network, events, now=None):
        now = now or utcnow()
        risks = supplier_risks(network, events, now)
        with connect() as db:
            c = db.cursor()
            for e in events:
                c.execute(
                    "UPDATE dbo.LiveEvent SET event_risk=? WHERE id=?",
                    event_risk(e, now),
                    e["id"],
                )
            c.execute(
                "UPDATE dbo.LiveEvent SET event_risk=0 WHERE published_at<DATEADD(day,?,SYSUTCDATETIME())",
                -MAX_EVENT_DAYS,
            )
            for r in risks:
                args = (
                    r["current_live_risk"],
                    r["risk"],
                    r["active_event_id"],
                    r["exposure_status"],
                    sqltime(iso(now)),
                    r["supplier_id"],
                )
                c.execute(
                    "IF EXISTS(SELECT 1 FROM dbo.SupplierRisk WHERE supplier_id=?) UPDATE dbo.SupplierRisk SET current_live_risk=?,risk_level=?,active_event_id=?,exposure_status=?,updated_at=? WHERE supplier_id=? ELSE INSERT dbo.SupplierRisk(current_live_risk,risk_level,active_event_id,exposure_status,updated_at,supplier_id) VALUES(?,?,?,?,?,?)",
                    r["supplier_id"],
                    *args,
                    *args,
                )
                c.execute(
                    "INSERT dbo.SupplierRiskHistory(supplier_id,current_live_risk,active_event_id,exposure_status,recorded_at) VALUES(?,?,?,?,?)",
                    r["supplier_id"],
                    r["current_live_risk"],
                    r["active_event_id"],
                    r["exposure_status"],
                    sqltime(iso(now)),
                )
            for country in sorted(set(s["country"] for s in network["suppliers"])):
                ids = {s["id"] for s in network["suppliers"] if s["country"] == country}
                regional = [
                    e
                    for e in events
                    if any(
                        m["match_type"] == "regional" and m["supplier_id"] in ids
                        for m in e["matches"]
                    )
                ]
                top = max(regional, key=lambda e: event_risk(e, now), default=None)
                value = event_risk(top, now) if top else 0
                affected = len(
                    set(
                        m["supplier_id"]
                        for e in regional
                        for m in e["matches"]
                        if m["supplier_id"] in ids and m["match_type"] == "regional"
                    )
                )
                args = (
                    value,
                    top["id"] if top else None,
                    affected,
                    sqltime(iso(now)),
                    country,
                )
                c.execute(
                    "IF EXISTS(SELECT 1 FROM dbo.RegionalRisk WHERE region=?) UPDATE dbo.RegionalRisk SET current_live_risk=?,active_event_id=?,exposed_suppliers=?,updated_at=? WHERE region=? ELSE INSERT dbo.RegionalRisk(current_live_risk,active_event_id,exposed_suppliers,updated_at,region) VALUES(?,?,?,?,?)",
                    country,
                    *args,
                    *args,
                )
                c.execute(
                    "INSERT dbo.RegionalRiskHistory(region,current_live_risk,active_event_id,recorded_at) VALUES(?,?,?,?)",
                    country,
                    value,
                    top["id"] if top else None,
                    sqltime(iso(now)),
                )
            db.commit()
        return risks

    def risk_rows(self):
        with connect() as db:
            return [
                {
                    "supplier_id": r[0],
                    "current_live_risk": r[1],
                    "risk": r[2],
                    "active_event_id": r[3],
                    "exposure_status": r[4],
                    "updated_at": timestamp(r[5]),
                }
                for r in db.cursor().execute(
                    "SELECT supplier_id,current_live_risk,risk_level,active_event_id,exposure_status,updated_at FROM dbo.SupplierRisk"
                )
            ]

    def regional_rows(self):
        with connect() as db:
            return [
                {
                    "region": r[0],
                    "current_live_risk": r[1],
                    "active_event_id": r[2],
                    "exposed_suppliers": r[3],
                    "updated_at": timestamp(r[4]),
                }
                for r in db.cursor().execute(
                    "SELECT region,current_live_risk,active_event_id,exposed_suppliers,updated_at FROM dbo.RegionalRisk"
                )
            ]

    def latest_news(self, limit=50):
        with connect() as db:
            rows = (
                db.cursor()
                .execute(
                    "SELECT TOP (?) raw_metadata,processing_status,processing_reason FROM dbo.Article ORDER BY published_at DESC",
                    limit,
                )
                .fetchall()
            )
        return [
            {**json.loads(r[0]), "processing_status": r[1], "processing_reason": r[2]}
            for r in rows
        ]

    def history(self, supplier_id):
        with connect() as db:
            return [
                {
                    "risk": r[0],
                    "active_event_id": r[1],
                    "exposure_status": r[2],
                    "recorded_at": timestamp(r[3]),
                }
                for r in db.cursor().execute(
                    "SELECT TOP 200 current_live_risk,active_event_id,exposure_status,recorded_at FROM dbo.SupplierRiskHistory WHERE supplier_id=? ORDER BY recorded_at DESC",
                    supplier_id,
                )
            ]

    def source_states(self):
        with connect() as db:
            rows = (
                db.cursor()
                .execute(
                    "SELECT source_id,name,url,etag,last_modified,last_attempt,last_success,status,last_error,retrieved_count,new_count FROM dbo.SourceState"
                )
                .fetchall()
            )
        keys = [
            "id",
            "name",
            "url",
            "etag",
            "last_modified",
            "last_attempt",
            "last_success",
            "status",
            "last_error",
            "retrieved_count",
            "new_count",
        ]
        return [
            {
                k: timestamp(v) if k in ["last_attempt", "last_success"] else v
                for k, v in zip(keys, r)
            }
            for r in rows
        ]

    def save_source_state(self, state):
        with connect() as db:
            c = db.cursor()
            values = (
                state["name"],
                state["url"],
                state.get("etag"),
                state.get("last_modified"),
                sqltime(state["last_attempt"]),
                sqltime(state["last_success"]) if state.get("last_success") else None,
                state["status"],
                state.get("last_error"),
                state.get("retrieved_count", 0),
                state.get("new_count", 0),
                state["id"],
            )
            c.execute(
                "IF EXISTS(SELECT 1 FROM dbo.SourceState WHERE source_id=?) UPDATE dbo.SourceState SET name=?,url=?,etag=?,last_modified=?,last_attempt=?,last_success=?,status=?,last_error=?,retrieved_count=?,new_count=? WHERE source_id=? ELSE INSERT dbo.SourceState(name,url,etag,last_modified,last_attempt,last_success,status,last_error,retrieved_count,new_count,source_id) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                state["id"],
                *values,
                *values,
            )
            db.commit()

    def save_run(self, start, end, ok, failed, new, processed):
        with connect() as db:
            db.cursor().execute(
                "INSERT dbo.IngestionRun(started_at,finished_at,sources_ok,sources_failed,articles_new,events_processed) VALUES(?,?,?,?,?,?)",
                sqltime(start),
                sqltime(end),
                ok,
                failed,
                new,
                processed,
            )
            db.commit()

    def ingestion_status(self):
        states = self.source_states()
        now = utcnow()
        from settings import sources

        enabled = {s["id"] for s in sources()}
        states = [s for s in states if s["id"] in enabled]
        fresh = [
            s
            for s in states
            if s["last_success"]
            and (now - parse_time(s["last_success"])).total_seconds()
            < max(1800, 3 * POLL_SECONDS)
        ]
        status = (
            "online"
            if len(fresh) == len(enabled)
            and enabled
            and all(s["status"] == "ok" for s in fresh)
            else "degraded" if fresh else "offline"
        )
        with connect() as db:
            c = db.cursor()
            run = c.execute(
                "SELECT TOP 1 started_at,finished_at,sources_ok,sources_failed,articles_new,events_processed FROM dbo.IngestionRun ORDER BY id DESC"
            ).fetchone()
            pending = c.execute(
                "SELECT COUNT(*) FROM dbo.Article WHERE processing_status='pending'"
            ).fetchone()[0]
            total = c.execute("SELECT COUNT(*) FROM dbo.Article").fetchone()[0]
        last_run = (
            dict(
                zip(
                    [
                        "started_at",
                        "finished_at",
                        "sources_ok",
                        "sources_failed",
                        "articles_new",
                        "events_processed",
                    ],
                    [timestamp(run[0]), timestamp(run[1]), *run[2:]],
                )
            )
            if run
            else None
        )
        return {
            "status": status,
            "poll_seconds": POLL_SECONDS,
            "sources": states,
            "pending_articles": pending,
            "total_articles": total,
            "last_run": last_run,
            "as_of": iso(now),
        }


def initialize():
    database = os.getenv("SQLSERVER_DATABASE", "SiliconWatch")
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,100}", database):
        raise ValueError("Invalid database name")
    base = os.getenv("SQLSERVER_CONNECTION_STRING", "")
    if not base:
        raise DatabaseUnavailable("Configure SQLSERVER_CONNECTION_STRING first")
    master = re.sub(r"(?i)Database\s*=\s*[^;]+", "Database=master", base)
    if master == base and "database=" not in base.lower():
        master = base + ";Database=master"
    with connect(master, autocommit=True) as db:
        db.cursor().execute(
            f"IF DB_ID('{database}') IS NULL CREATE DATABASE [{database}]"
        )
    with connect() as db:
        c = db.cursor()
        c.execute((Path(__file__).parent / "schema.sql").read_text())
        db.commit()
        c.execute((Path(__file__).parent / "migrations/002_live.sql").read_text())
        db.commit()
        if c.execute("SELECT COUNT(*) FROM dbo.Supplier").fetchone()[0] == 0:
            data = json.loads(
                (ROOT / "backend/seed/network.json").read_text(encoding="utf-8")
            )
            for s in data["suppliers"]:
                s = {**s, "risk": "Unknown"}
                c.execute(
                    "INSERT dbo.Supplier VALUES(?,?,?,?,?,?,?)",
                    s["id"],
                    s["name"],
                    s["country"],
                    s["category"],
                    s["lat"],
                    s["lon"],
                    json.dumps(s),
                )
            for comp in data["components"]:
                c.execute(
                    "INSERT dbo.Component VALUES(?,?,?,?)",
                    comp["id"],
                    comp["name"],
                    comp["importance"],
                    json.dumps(comp),
                )
            for r in data["relationships"]:
                c.execute(
                    "INSERT dbo.SupplyRelationship VALUES(?,?)",
                    r["supplier"],
                    r["component"],
                )
            db.commit()
        # Repair the original Windows seed import's middle-dot encoding, preserving records.
        for row in c.execute("SELECT id,payload FROM dbo.Component").fetchall():
            item = json.loads(row[1])
            name = item["name"].replace("\u00c2\u00b7", "\u00b7")
            if name != item["name"]:
                item["name"] = name
                c.execute(
                    "UPDATE dbo.Component SET name=?,payload=? WHERE id=?",
                    name,
                    json.dumps(item),
                    row[0],
                )
        db.commit()
    repo = SqlRepository()
    repo.update_risks(repo.network(), repo.events())
    print(
        "SQL Server initialized. Sourcing records persisted; no synthetic news inserted."
    )


if __name__ == "__main__":
    initialize()
