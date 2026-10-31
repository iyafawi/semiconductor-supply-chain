import json
import os
import unittest
from datetime import timedelta
from unittest.mock import patch, MagicMock
from pathlib import Path

from openai_news import parse_results, fetch_openai_news
from processing import utcnow, classify
from settings import sources

SOURCE = {
    "id": "openai-web-search",
    "name": "OpenAI web search (AI summary)",
    "credibility": 0.6,
}


class OpenAINewsTests(unittest.TestCase):
    def setUp(self):
        self.now = utcnow()
        self.item = {
            "title": "TSMC halted wafer production after factory fire",
            "summary": "TSMC halted semiconductor production.",
            "url": "https://example.com/news",
            "published_at": (self.now - timedelta(hours=1)).isoformat(),
        }

    def payload(self, items=None, cited=True):
        return {
            "status": "completed",
            "output": [
                {"type": "web_search_call", "status": "completed"},
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "output_text",
                            "text": json.dumps(
                                {
                                    "articles": (
                                        items if items is not None else [self.item]
                                    )
                                }
                            ),
                            "annotations": (
                                [{"type": "url_citation", "url": self.item["url"]}]
                                if cited
                                else []
                            ),
                        }
                    ],
                },
            ],
        }

    def test_cited_result_is_deduplicated(self):
        result = parse_results(self.payload([self.item, self.item]), SOURCE, self.now)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["url"], self.item["url"])
        self.assertEqual(
            result[0]["id"], parse_results(self.payload(), SOURCE, self.now)[0]["id"]
        )

    def test_uncited_result_rejected(self):
        with self.assertRaises(ValueError):
            parse_results(self.payload(cited=False), SOURCE, self.now)

    def test_old_future_missing_dates_rejected(self):
        for date in [
            (self.now - timedelta(days=8)).isoformat(),
            (self.now + timedelta(days=1)).isoformat(),
            "unknown",
            "2026-10-31",
        ]:
            with self.subTest(date=date), self.assertRaises(ValueError):
                parse_results(
                    self.payload([{**self.item, "published_at": date}]),
                    SOURCE,
                    self.now,
                )

    def test_incomplete_or_no_search_rejected(self):
        payload = self.payload()
        payload["status"] = "incomplete"
        with self.assertRaises(ValueError):
            parse_results(payload, SOURCE, self.now)
        payload = self.payload()
        payload["output"] = payload["output"][1:]
        with self.assertRaises(ValueError):
            parse_results(payload, SOURCE, self.now)

    def test_empty_search_is_valid(self):
        self.assertEqual(parse_results(self.payload([]), SOURCE, self.now), [])

    def test_ai_text_never_confirms_supplier_interruption(self):
        article = parse_results(self.payload(), SOURCE, self.now)[0]
        network = json.loads((Path(__file__).parent / "seed/network.json").read_text())
        event, _ = classify(article, network, self.now)
        self.assertEqual(event["status"], "low_confidence")
        self.assertTrue(
            all(m["exposure_status"] == "low_confidence" for m in event["matches"])
        )
        self.assertIn(0, [m["supplier_id"] for m in event["matches"]])

    def test_disabled_by_default_and_opt_in(self):
        with patch.dict(os.environ, {"OPENAI_NEWS_ENABLED": "false"}):
            self.assertFalse(any(s["kind"] == "openai_search" for s in sources()))
        with patch.dict(os.environ, {"OPENAI_NEWS_ENABLED": "true"}):
            self.assertTrue(any(s["kind"] == "openai_search" for s in sources()))

    def test_missing_key_fails_without_network(self):
        with (
            patch.dict(os.environ, {"OPENAI_API_KEY": ""}),
            patch("openai_news.httpx.Client") as client,
        ):
            with self.assertRaises(RuntimeError):
                fetch_openai_news(SOURCE)
            client.assert_not_called()

    def test_request_forces_live_search(self):
        response = MagicMock()
        response.json.return_value = self.payload([])
        with (
            patch.dict(os.environ, {"OPENAI_API_KEY": "test-only-not-a-real-key"}),
            patch("openai_news.httpx.Client") as client,
        ):
            client.return_value.__enter__.return_value.post.return_value = response
            self.assertEqual(fetch_openai_news(SOURCE)[0], [])
            request = client.return_value.__enter__.return_value.post.call_args.kwargs[
                "json"
            ]
            self.assertEqual(request["tool_choice"], "required")
            self.assertTrue(request["tools"][0]["external_web_access"])


if __name__ == "__main__":
    unittest.main()
