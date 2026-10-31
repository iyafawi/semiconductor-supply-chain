"""Controlled articles only in a freshly created SQL Server test database.
Run with SILICONWATCH_SQL_TESTS=1. Real SQL persistence, no mock database.
"""

import os, re, unittest, uuid
from unittest.mock import patch
from fastapi.testclient import TestClient
from repository import connect, initialize, SqlRepository
from feeds import make_article
from processing import utcnow
from worker import run_once
from main import app


@unittest.skipUnless(
    os.getenv("SILICONWATCH_SQL_TESTS") == "1",
    "Set SILICONWATCH_SQL_TESTS=1 for isolated real SQL Server integration",
)
class SqlIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = os.environ["SQLSERVER_CONNECTION_STRING"]
        cls.original_name = os.environ.get("SQLSERVER_DATABASE")
        cls.name = "SiliconWatchTest_" + uuid.uuid4().hex[:12]
        cls.master = re.sub(
            r"(?i)Database\s*=\s*[^;]+", "Database=master", cls.original
        )
        os.environ["SQLSERVER_CONNECTION_STRING"] = re.sub(
            r"(?i)Database\s*=\s*[^;]+", "Database=" + cls.name, cls.original
        )
        os.environ["SQLSERVER_DATABASE"] = cls.name
        initialize()
        cls.repo = SqlRepository()
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        os.environ["SQLSERVER_CONNECTION_STRING"] = cls.original
        if cls.original_name:
            os.environ["SQLSERVER_DATABASE"] = cls.original_name
        else:
            os.environ.pop("SQLSERVER_DATABASE", None)
        # Name is generated exclusively here and never references the user's application database.
        assert re.fullmatch(r"SiliconWatchTest_[0-9a-f]{12}", cls.name)
        with connect(cls.master, autocommit=True) as db:
            db.cursor().execute(
                f"ALTER DATABASE [{cls.name}] SET SINGLE_USER WITH ROLLBACK IMMEDIATE; DROP DATABASE [{cls.name}]"
            )

    def test_complete_pipeline_sql_to_api(self):
        def controlled_fetch(source, state):
            if source["id"] == "usgs":
                raise RuntimeError("Controlled unavailable feed")
            now = utcnow()
            suffix = " today" if source["id"] == "federal-register-bis" else ""
            article = make_article(
                source,
                "TSMC semiconductor factory shutdown disrupts wafer production"
                + suffix,
                "TSMC has halted wafer production.",
                "https://example.invalid/controlled/" + source["id"],
                now,
                now=now,
            )
            regional = make_article(
                source,
                "Earthquake disrupts semiconductor manufacturing in Taiwan",
                "",
                "https://example.invalid/region/" + source["id"],
                now,
                now=now,
            )
            unrelated = make_article(
                source,
                "Sports championship results",
                "",
                "https://example.invalid/sports/" + source["id"],
                now,
                now=now,
            )
            return [article, regional, unrelated], {}

        first = run_once(self.repo, controlled_fetch)
        second = run_once(self.repo, controlled_fetch)
        self.assertEqual(first["sources_ok"], 2)
        self.assertEqual(first["sources_failed"], 1)
        self.assertEqual(first["articles_new"], 6)
        self.assertEqual(second["articles_new"], 0)
        with connect() as db:
            c = db.cursor()
            self.assertEqual(
                c.execute("SELECT COUNT(*) FROM dbo.Article").fetchone()[0], 6
            )
            self.assertEqual(
                c.execute("SELECT COUNT(*) FROM dbo.LiveEvent").fetchone()[0], 2
            )
            self.assertEqual(
                c.execute("SELECT COUNT(*) FROM dbo.EventArticle").fetchone()[0], 4
            )
            self.assertGreater(
                c.execute("SELECT COUNT(*) FROM dbo.SupplierRiskHistory").fetchone()[0],
                48,
            )
            self.assertGreater(
                c.execute("SELECT COUNT(*) FROM dbo.RegionalRiskHistory").fetchone()[0],
                0,
            )
        events = self.client.get("/api/events/active").json()["events"]
        self.assertEqual(len(events), 2)
        direct = next(e for e in events if e["event_type"] == "factory_disruption")
        self.assertEqual(direct["severity"], 0.9)
        self.assertEqual(len(direct["sources"]), 2)
        risk = self.client.get("/api/suppliers/0/risk").json()
        self.assertEqual(risk["risk"], "High")
        self.assertEqual(risk["priority"], "Critical alert")
        self.assertEqual(risk["criticality"], 82)
        self.assertGreater(
            self.client.get("/api/regions/Taiwan/risk").json()["current_live_risk"], 0
        )
        self.assertEqual(
            self.client.get("/api/ingestion/status").json()["status"], "degraded"
        )
        self.assertEqual(self.client.get("/api/suppliers/999/risk").status_code, 404)
        self.assertEqual(
            self.client.post("/api/simulate", json={"supplier_ids": [0]}).json()[
                "zero_coverage"
            ],
            1,
        )
        self.assertEqual(
            self.client.post("/api/simulate", json={"supplier_ids": [999]}).status_code,
            400,
        )
        self.assertEqual(
            self.client.post("/api/simulate", json={"supplier_ids": []}).status_code,
            422,
        )
        self.assertEqual(self.client.get("/api/health").json()["database"], "sqlserver")
        self.assertEqual(len(self.client.get("/api/news/latest").json()["articles"]), 6)


if __name__ == "__main__":
    unittest.main()
