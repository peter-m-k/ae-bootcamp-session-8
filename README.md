# ae-bootcamp-session-8
capstone

## Setup

This project uses [uv](https://docs.astral.sh/uv/) for dependency management.

Install uv (if not already installed):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Install dependencies:

```bash
uv sync
```

## Run

```bash
uv run python app.py
```

## Test

```bash
uv run pytest
```

## About

A small Flask app that lets users define their own data tables (like a mini Airtable) and manage rows through a web UI. Table and column definitions are stored in SQLite, and each user-defined table becomes its own real SQLite table created on the fly.

## Architecture

- **[app.py](app.py)** — Flask routes / HTTP layer. Parses requests, calls `logic`, and maps errors to JSON responses and status codes.
- **[logic.py](logic.py)** — Business logic: name/type validation, slug generation, and workflow orchestration between the display layer and the database.
- **[db.py](db.py)** — Pure data-access layer: SQLite connection lifecycle and raw queries. No validation lives here.
- **[templates/index.html](templates/index.html)** and **[static/](static/)** — Front-end UI (vanilla JS/CSS) that talks to the JSON API below.

Every user-defined table automatically gets three system columns: `PK` (primary key), `CREATE_TS`, and `UPDATE_TS`. These are read-only and managed by the server.

## API

| Method | Path | Description |
| --- | --- | --- |
| GET | `/` | Serves the web UI. |
| GET | `/api/tables` | List all tables (`name`, `slug`). |
| POST | `/api/tables` | Create a table. Body: `{"name": str, "columns": [{"name": str, "type": "text"\|"integer"\|"number"}]}`. |
| GET | `/api/tables/<slug>` | Get a table's columns and rows. |
| POST | `/api/tables/<slug>/rows` | Create a row. Body: `{<column_slug>: value, ...}`. |
| PUT | `/api/tables/<slug>/rows/<row_id>` | Update a row by id. |
| DELETE | `/api/tables/<slug>/rows/<row_id>` | Delete a row by id. |

Errors are returned as `{"error": "message"}` with a `400` (validation) or `404` (table/row not found) status code.

## Configuration

- `DATABASE` — path to the SQLite database file. Defaults to `data.db` next to [app.py](app.py).
