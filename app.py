import os
import re
import sqlite3
from pathlib import Path

from flask import Flask, current_app, g, jsonify, render_template, request

app = Flask(__name__)
app.config["DATABASE"] = os.environ.get(
    "DATABASE", str(Path(__file__).parent / "data.db")
)

# Maps the field types offered in the "New Table" form to SQLite column types.
ALLOWED_TYPES = {
    "text": "TEXT",
    "number": "REAL",
}

_SLUG_INVALID_RE = re.compile(r"[^a-z0-9]+")


def slugify(value):
    """Turn a user-supplied name into a safe SQL identifier (a-z, 0-9, _)."""
    slug = _SLUG_INVALID_RE.sub("_", value.strip().lower()).strip("_")
    if not slug:
        raise ValueError("Name must contain at least one letter or number.")
    if slug[0].isdigit():
        slug = f"f_{slug}"
    return slug


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
        _init_schema(g.db)
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


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


def _get_table_meta(db, slug):
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
                    return None, f'"{column["name"]}" must be a number.'
        else:
            values[column["slug"]] = None if raw is None else str(raw)
    return values, None


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/tables", methods=["GET"])
def list_tables():
    db = get_db()
    rows = db.execute("SELECT name, slug FROM _tables ORDER BY name").fetchall()
    return jsonify([dict(row) for row in rows])


@app.route("/api/tables", methods=["POST"])
def create_table():
    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    columns = payload.get("columns") or []

    if not name:
        return jsonify(error="Table name is required."), 400
    if not columns:
        return jsonify(error="At least one field is required."), 400

    try:
        table_slug = slugify(name)
    except ValueError as exc:
        return jsonify(error=str(exc)), 400

    db = get_db()
    if db.execute("SELECT 1 FROM _tables WHERE slug = ?", (table_slug,)).fetchone():
        return jsonify(error=f'A table named "{name}" already exists.'), 400

    prepared_columns = []
    seen_slugs = set()
    for column in columns:
        col_name = (column.get("name") or "").strip()
        col_type = column.get("type")
        if not col_name:
            return jsonify(error="Every field needs a name."), 400
        if col_type not in ALLOWED_TYPES:
            return jsonify(error=f'Unsupported field type "{col_type}".'), 400
        try:
            col_slug = slugify(col_name)
        except ValueError as exc:
            return jsonify(error=str(exc)), 400
        if col_slug in seen_slugs:
            return jsonify(error=f'Duplicate field name "{col_name}".'), 400
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
    return jsonify(_get_table_meta(db, table_slug)), 201


@app.route("/api/tables/<slug>", methods=["GET"])
def get_table(slug):
    db = get_db()
    meta = _get_table_meta(db, slug)
    if meta is None:
        return jsonify(error="Table not found."), 404

    column_slugs = [column["slug"] for column in meta["columns"]]
    select_cols = ", ".join(["id"] + [f'"{s}"' for s in column_slugs])
    rows = db.execute(
        f'SELECT {select_cols} FROM "{meta["slug"]}" ORDER BY id'
    ).fetchall()
    return jsonify(
        {
            "name": meta["name"],
            "slug": meta["slug"],
            "columns": meta["columns"],
            "rows": [dict(row) for row in rows],
        }
    )


@app.route("/api/tables/<slug>/rows", methods=["POST"])
def create_row(slug):
    db = get_db()
    meta = _get_table_meta(db, slug)
    if meta is None:
        return jsonify(error="Table not found."), 404

    payload = request.get_json(silent=True) or {}
    values, error = _coerce_row_values(meta["columns"], payload)
    if error:
        return jsonify(error=error), 400

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
    return jsonify(dict(row)), 201


@app.route("/api/tables/<slug>/rows/<int:row_id>", methods=["PUT"])
def update_row(slug, row_id):
    db = get_db()
    meta = _get_table_meta(db, slug)
    if meta is None:
        return jsonify(error="Table not found."), 404

    existing = db.execute(
        f'SELECT id FROM "{meta["slug"]}" WHERE id = ?', (row_id,)
    ).fetchone()
    if existing is None:
        return jsonify(error="Record not found."), 404

    payload = request.get_json(silent=True) or {}
    values, error = _coerce_row_values(meta["columns"], payload)
    if error:
        return jsonify(error=error), 400

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
    return jsonify(dict(row))


@app.route("/api/tables/<slug>/rows/<int:row_id>", methods=["DELETE"])
def delete_row(slug, row_id):
    db = get_db()
    meta = _get_table_meta(db, slug)
    if meta is None:
        return jsonify(error="Table not found."), 404

    cursor = db.execute(f'DELETE FROM "{meta["slug"]}" WHERE id = ?', (row_id,))
    db.commit()
    if cursor.rowcount == 0:
        return jsonify(error="Record not found."), 404
    return "", 204


if __name__ == "__main__":
    app.run()
