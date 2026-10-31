# Local setup

## Prerequisites

- Windows with PowerShell.
- Python 3.11+ and Node.js 22+ with npm on PATH.
- SQL Server Express and Microsoft ODBC Driver 18.
- An OpenAI API key if web search is enabled.

The default connection uses Windows authentication against `localhost\SQLEXPRESS`. The Windows account must be able to create the database and apply migrations during setup.

## Install

```powershell
Copy-Item .env.example .env
```

Edit `SQLSERVER_CONNECTION_STRING` and `SQLSERVER_DATABASE` for your SQL Server instance. Set `OPENAI_NEWS_ENABLED=true` and `OPENAI_API_KEY` to enable paid web searches. Leave it false to run the other feeds without OpenAI.

```powershell
.\setup-local.ps1
```

The script creates a virtual environment, installs dependencies, initializes the database and builds the frontend. It uses the committed npm lockfile. To select a particular Python executable, set `SILICONWATCH_PYTHON` to its path.

If SQL Server and ODBC are not installed, the optional command below installs them through Windows Package Manager and accepts the package agreements. Installation may require administrator access.

```powershell
.\setup-local.ps1 -InstallSqlServer
```

## Start and stop

```powershell
.\start-local.ps1
.\stop-local.ps1
```

Dashboard: http://127.0.0.1:5173. API documentation: http://127.0.0.1:8000/docs.

The start script launches the API, worker and frontend server as separate local processes. The worker fetches immediately, then waits 10 minutes between completed cycles. React refreshes about every 45 seconds. Closing the browser leaves the worker running. Stop shuts down the application processes but leaves SQL Server and stored records intact.

Logs and process IDs are stored in `.local-runtime/`. The stop script checks process start times before stopping a recorded process.

## Configuration

`.env.example` lists connection settings, polling intervals and risk thresholds. The worker interval is constrained to 300–600 seconds; the frontend refresh interval is constrained to 30–60 seconds. Restart services after changing backend settings. Rebuild the frontend after changing a `VITE_` setting.

`backend/sources.json` configures the RSS, earthquake and regulatory feeds. `backend/aliases.json` maps alternate supplier names. OpenAI is added as a source when enabled in the environment.

Keep credentials out of frontend variables. The default SQL connection trusts the local server certificate; configure certificate validation for other environments.

## Troubleshooting

| Symptom                                 | Check                                                                                                 |
| --------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| SQL Server unavailable                  | Instance name, running SQL service, ODBC installation and Windows account permissions                 |
| OpenAI source failed                    | API key, account access, model availability and API quota                                             |
| No active events                        | Source refresh times and article filtering reasons; a successful cycle may find no qualifying reports |
| Worker offline                          | `.local-runtime/worker.error.log` and database connectivity                                           |
| Frontend does not reflect configuration | Rebuild with `npm run build`, then restart                                                            |
| Services already running                | Stop the existing managed processes before starting again                                             |

A failed feed does not stop the other sources. Database failures are reported as unavailable; previously stored data is not replaced with sample news.

## Database and API

`backend/schema.sql` and `backend/migrations/` define suppliers, components, sourcing relationships, articles, events, evidence mappings, risk histories and ingestion status. Initialization seeds the sourcing network once. Normal requests read SQL Server.

FastAPI documents the endpoints at `/docs`, including network inspection, active events, source health, supplier risk history and simulation. Use SQL Server backup tools to back up persistent records.
