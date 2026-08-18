"""SQLite adapter: owns the connection lifecycle, schema, and all raw SQL
queries backing the dynamic "tables" feature. Flask routes in app.py call
into this module instead of touching sqlite3 directly.
"""

import re
import sqlite3

from flask import current_app, g

# Maps the field types offered in the "New Table" form to SQLite column types.
ALLOWED_TYPES = {
    "text": "TEXT",
    "number": "REAL",
}

_SLUG_INVALID_RE = re.compile(r"[^a-z0-9]+")


class TableNotFoundError(LookupError):
    """Raised when a table slug does not match any known table."""


class RowNotFoundError(LookupError):
    """Raised when a row id does not exist in a table."""


def init_app(app):
    app.teardown_appcontext(close_db)


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
        _init_schema(g.db)
    return g.db


def close_db(exception=None):
    db_conn = g.pop("db", None)
    if db_conn is not None:
        db_conn.close()


def slugify(value):
    """Turn a user-supplied name into a safe SQL identifier (a-z, 0-9, _)."""
    slug = _SLUG_INVALID_RE.sub("_", value.strip().lower()).strip("_")
    if not slug:
        raise ValueError("Name must contain at least one letter or number.")
    if slug[0].isdigit():
        slug = f"f_{slug}"
    return slug


def _init_schema(db):
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS _tables (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            slug TEXT NOT NULL UNIQUE
        );
        CREATE TABLE IF NOT EXISTS _columns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            table_id INTEGER NOT NULL REFERENCES _tables(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            slug TEXT NOT NULL,
            type TEXT NOT NULL,
            position INTEGER NOT NULL
        );
        """
    )
    db.commit()


def get_table_meta(slug):
    """Return {"id", "name", "slug", "columns"} for a table, or None."""
    db = get_db()
    table = db.execute(
        "SELECT id, name, slug FROM _tables WHERE slug = ?", (slug,)
    ).fetchone()
    if table is None:
        return None
    columns = db.execute(
        "SELECT name, slug, type FROM _columns WHERE table_id = ? ORDER BY position",
        (table["id"],),
    ).fetchall()
    return {
        "id": table["id"],
        "name": table["name"],
        "slug": table["slug"],
        "columns": [dict(column) for column in columns],
    }


def list_tables():
    db = get_db()
    rows = db.execute("SELECT name, slug FROM _tables ORDER BY name").fetchall()
    return [dict(row) for row in rows]


def create_table(name, columns):
    """Create a new user-defined table and return its metadata.

    Raises ValueError on invalid input (missing/duplicate names, bad types).
    """
    name = (name or "").strip()
    if not name:
        raise ValueError("Table name is required.")
    if not columns:
        raise ValueError("At least one field is required.")

    table_slug = slugify(name)

    db = get_db()
    if db.execute("SELECT 1 FROM _tables WHERE slug = ?", (table_slug,)).fetchone():
        raise ValueError(f'A table named "{name}" already exists.')

    prepared_columns = []
    seen_slugs = set()
    for column in columns:
        col_name = (column.get("name") or "").strip()
        col_type = column.get("type")
        if not col_name:
            raise ValueError("Every field needs a name.")
        if col_type not in ALLOWED_TYPES:
            raise ValueError(f'Unsupported field type "{col_type}".')
        col_slug = slugify(col_name)
        if col_slug in seen_slugs:
            raise ValueError(f'Duplicate field name "{col_name}".')
        seen_slugs.add(col_slug)
        prepared_columns.append((col_name, col_slug, col_type))

    cursor = db.execute(
        "INSERT INTO _tables (name, slug) VALUES (?, ?)", (name, table_slug)
    )
    table_id = cursor.lastrowid

    column_defs = ", ".join(
        f'"{col_slug}" {ALLOWED_TYPES[col_type]}'
        for _, col_slug, col_type in prepared_columns
    )
    db.execute(
        f'CREATE TABLE "{table_slug}" '
        f"(id INTEGER PRIMARY KEY AUTOINCREMENT, {column_defs})"
    )

    for position, (col_name, col_slug, col_type) in enumerate(prepared_columns):
        db.execute(
            "INSERT INTO _columns (table_id, name, slug, type, position) "
            "VALUES (?, ?, ?, ?, ?)",
            (table_id, col_name, col_slug, col_type, position),
        )

    db.commit()
    return get_table_meta(table_slug)


def get_table_data(slug):
    """Return {"name", "slug", "columns", "rows"} for a table.

    Raises TableNotFoundError if the slug is unknown.
    """
    meta = get_table_meta(slug)
    if meta is None:
        raise TableNotFoundError(f'Table "{slug}" not found.')

    db = get_db()
    column_slugs = [column["slug"] for column in meta["columns"]]
    select_cols = ", ".join(["id"] + [f'"{s}"' for s in column_slugs])
    rows = db.execute(
        f'SELECT {select_cols} FROM "{meta["slug"]}" ORDER BY id'
    ).fetchall()
    return {
        "name": meta["name"],
        "slug": meta["slug"],
        "columns": meta["columns"],
        "rows": [dict(row) for row in rows],
    }


def _coerce_row_values(columns, payload):
    values = {}
    for column in columns:
        raw = payload.get(column["slug"])
        if column["type"] == "number":
            if raw in (None, ""):
                values[column["slug"]] = None
            else:
                try:
                    values[column["slug"]] = float(raw)
                except (TypeError, ValueError):
                    raise ValueError(f'"{column["name"]}" must be a number.') from None
        else:
            values[column["slug"]] = None if raw is None else str(raw)
    return values


def create_row(slug, payload):
    """Insert a row into a table and return it.

    Raises TableNotFoundError or ValueError (invalid field values).
    """
    meta = get_table_meta(slug)
    if meta is None:
        raise TableNotFoundError(f'Table "{slug}" not found.')

    values = _coerce_row_values(meta["columns"], payload)

    db = get_db()
    col_slugs = list(values.keys())
    col_list = ", ".join(f'"{c}"' for c in col_slugs)
    placeholders = ", ".join("?" for _ in col_slugs)
    cursor = db.execute(
        f'INSERT INTO "{meta["slug"]}" ({col_list}) VALUES ({placeholders})',
        [values[c] for c in col_slugs],
    )
    db.commit()

    select_cols = ", ".join(["id"] + [f'"{c}"' for c in col_slugs])
    row = db.execute(
        f'SELECT {select_cols} FROM "{meta["slug"]}" WHERE id = ?',
        (cursor.lastrowid,),
    ).fetchone()
    return dict(row)


def update_row(slug, row_id, payload):
    """Update a row in place and return the new values.

    Raises TableNotFoundError, RowNotFoundError, or ValueError.
    """
    meta = get_table_meta(slug)
    if meta is None:
        raise TableNotFoundError(f'Table "{slug}" not found.')

    db = get_db()
    existing = db.execute(
        f'SELECT id FROM "{meta["slug"]}" WHERE id = ?', (row_id,)
    ).fetchone()
    if existing is None:
        raise RowNotFoundError(f"Record {row_id} not found.")

    values = _coerce_row_values(meta["columns"], payload)

    col_slugs = list(values.keys())
    assignments = ", ".join(f'"{c}" = ?' for c in col_slugs)
    db.execute(
        f'UPDATE "{meta["slug"]}" SET {assignments} WHERE id = ?',
        [*(values[c] for c in col_slugs), row_id],
    )
    db.commit()

    select_cols = ", ".join(["id"] + [f'"{c}"' for c in col_slugs])
    row = db.execute(
        f'SELECT {select_cols} FROM "{meta["slug"]}" WHERE id = ?', (row_id,)
    ).fetchone()
    return dict(row)


def delete_row(slug, row_id):
    """Delete a row. Raises TableNotFoundError or RowNotFoundError."""
    meta = get_table_meta(slug)
    if meta is None:
        raise TableNotFoundError(f'Table "{slug}" not found.')

    db = get_db()
    cursor = db.execute(f'DELETE FROM "{meta["slug"]}" WHERE id = ?', (row_id,))
    db.commit()
    if cursor.rowcount == 0:
        raise RowNotFoundError(f"Record {row_id} not found.")
