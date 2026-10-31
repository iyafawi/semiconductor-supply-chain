# Validation

Checked October 31, 2026:

- 20 Python unit tests passed, including nine OpenAI adapter checks.
- Real SQL Server integration test passed against an isolated temporary database: article persistence, API results, histories, deduplication and independent feed failure.
- Frontend production build passed (Vite).
- JavaScript dataset and analysis checks passed for all 54 preset scenarios.

The OpenAI tests use controlled API responses. No paid OpenAI request was made; real search response formatting and retrieval quality still need validation with a configured key. This is not a claim of measured classification accuracy.

The continuous-integration workflow runs unit tests, JavaScript checks and the frontend build. It skips the SQL integration test because it needs a separately configured SQL Server. To run locally:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s backend -v
node tests.mjs
npm run build
```

For the isolated SQL integration test, configure your connection and then set `SILICONWATCH_SQL_TESTS=1` before running unittest. The test creates and removes only its own uniquely named test database.
