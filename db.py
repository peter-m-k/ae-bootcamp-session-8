"""Pure SQLite data-access wrapper: connection lifecycle, schema, and raw
queries. No validation or business rules live here — see logic.py for that.
"""

import sqlite3

from flask import current_app, g


def init_app(app):
    app.teardown_appcontext(close_db)


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
        init_schema(g.db)
    return g.db


def close_db(exception=None):
    db_conn = g.pop("db", None)
    if db_conn is not None:
        db_conn.close()


def init_schema(db):
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


def fetch_table_by_slug(slug):
    db = get_db()
    return db.execute(
        "SELECT id, name, slug FROM _tables WHERE slug = ?", (slug,)
    ).fetchone()


def fetch_columns(table_id):
    db = get_db()
    return db.execute(
        "SELECT name, slug, type FROM _columns WHERE table_id = ? ORDER BY position",
        (table_id,),
    ).fetchall()


def fetch_all_tables():
    db = get_db()
    return db.execute("SELECT name, slug FROM _tables ORDER BY name").fetchall()


def insert_table_record(name, slug):
    db = get_db()
    cursor = db.execute(
        "INSERT INTO _tables (name, slug) VALUES (?, ?)", (name, slug)
    )
    db.commit()
    return cursor.lastrowid


def insert_column_record(table_id, name, slug, col_type, position):
    db = get_db()
    db.execute(
        "INSERT INTO _columns (table_id, name, slug, type, position) "
        "VALUES (?, ?, ?, ?, ?)",
        (table_id, name, slug, col_type, position),
    )
    db.commit()


def create_data_table(slug, column_defs_sql):
    db = get_db()
    db.execute(
        f'CREATE TABLE "{slug}" (id INTEGER PRIMARY KEY AUTOINCREMENT, {column_defs_sql})'
    )
    db.commit()


def fetch_rows(slug, column_slugs):
    db = get_db()
    select_cols = ", ".join(["id"] + [f'"{s}"' for s in column_slugs])
    return db.execute(f'SELECT {select_cols} FROM "{slug}" ORDER BY id').fetchall()


def fetch_row(slug, column_slugs, row_id):
    db = get_db()
    select_cols = ", ".join(["id"] + [f'"{s}"' for s in column_slugs])
    return db.execute(
        f'SELECT {select_cols} FROM "{slug}" WHERE id = ?', (row_id,)
    ).fetchone()


def row_exists(slug, row_id):
    db = get_db()
    row = db.execute(f'SELECT id FROM "{slug}" WHERE id = ?', (row_id,)).fetchone()
    return row is not None


def insert_row(slug, values):
    db = get_db()
    col_slugs = list(values.keys())
    col_list = ", ".join(f'"{c}"' for c in col_slugs)
    placeholders = ", ".join("?" for _ in col_slugs)
    cursor = db.execute(
        f'INSERT INTO "{slug}" ({col_list}) VALUES ({placeholders})',
        [values[c] for c in col_slugs],
    )
    db.commit()
    return cursor.lastrowid


def update_row_values(slug, values, row_id):
    db = get_db()
    col_slugs = list(values.keys())
    assignments = ", ".join(f'"{c}" = ?' for c in col_slugs)
    db.execute(
        f'UPDATE "{slug}" SET {assignments} WHERE id = ?',
        [*(values[c] for c in col_slugs), row_id],
    )
    db.commit()


def delete_row_record(slug, row_id):
    db = get_db()
    cursor = db.execute(f'DELETE FROM "{slug}" WHERE id = ?', (row_id,))
    db.commit()
    return cursor.rowcount
