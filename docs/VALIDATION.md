# Tests and development

Install the development dependencies:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
npm ci --ignore-scripts
```

## Run checks

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s backend -v
npm test
npm run build
npm run format:check
.\.venv\Scripts\python.exe -m black --check backend
```

Python tests cover supplier aliases, relevance filtering, negation, geographic exposure, event clustering and score decay. OpenAI adapter tests cover citation requirements, dates, duplicate results, incomplete responses and low-confidence treatment of summaries. They use controlled responses and do not make paid API requests.

JavaScript checks cover network integrity, criticality normalization, supplier removal and all 54 preset scenarios.

## SQL integration

Configure the connection in `.env`, then run:

```powershell
$env:SILICONWATCH_SQL_TESTS='1'
.\.venv\Scripts\python.exe -m unittest discover -s backend -p test_sql_integration.py -v
```

The test creates a uniquely named database, exercises persistence through the API, checks feed failure and duplicate handling, then removes that test database. It requires database-creation permissions. GitHub Actions skips this test because the hosted runner has no configured SQL Server.

## Formatting

```powershell
npm run format
.\.venv\Scripts\python.exe -m black backend
```

Prettier formats JavaScript, JSX, CSS and documentation. Black formats Python. CI checks both without modifying files.

## Sample data

`npm run seed` recreates `backend/seed/network.json`. Review changes before committing. Regenerating the file does not update a database that has already been initialized.

## Evaluation gaps

Live OpenAI retrieval quality has not yet been measured. Test it with a configured key and compare the retrieved reports against labeled examples before making accuracy claims. Unit tests establish behavior for the covered cases; they do not calibrate the risk scores against real outages.
