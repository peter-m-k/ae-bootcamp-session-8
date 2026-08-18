"""Business logic bridging the display layer (app.py) and the data-access
layer (db.py): validation, naming rules, and workflow orchestration.
"""

import re

import db

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
    db.init_app(app)


def slugify(value):
    """Turn a user-supplied name into a safe SQL identifier (a-z, 0-9, _)."""
    slug = _SLUG_INVALID_RE.sub("_", value.strip().lower()).strip("_")
    if not slug:
        raise ValueError("Name must contain at least one letter or number.")
    if slug[0].isdigit():
        slug = f"f_{slug}"
    return slug


def get_table_meta(slug):
    """Return {"id", "name", "slug", "columns"} for a table, or None."""
    table = db.fetch_table_by_slug(slug)
    if table is None:
        return None
    columns = db.fetch_columns(table["id"])
    return {
        "id": table["id"],
        "name": table["name"],
        "slug": table["slug"],
        "columns": [dict(column) for column in columns],
    }


def list_tables():
    return [dict(row) for row in db.fetch_all_tables()]


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
    if db.fetch_table_by_slug(table_slug) is not None:
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

    table_id = db.insert_table_record(name, table_slug)

    column_defs = ", ".join(
        f'"{col_slug}" {ALLOWED_TYPES[col_type]}'
        for _, col_slug, col_type in prepared_columns
    )
    db.create_data_table(table_slug, column_defs)

    for position, (col_name, col_slug, col_type) in enumerate(prepared_columns):
        db.insert_column_record(table_id, col_name, col_slug, col_type, position)

    return get_table_meta(table_slug)


def get_table_data(slug):
    """Return {"name", "slug", "columns", "rows"} for a table.

    Raises TableNotFoundError if the slug is unknown.
    """
    meta = get_table_meta(slug)
    if meta is None:
        raise TableNotFoundError(f'Table "{slug}" not found.')

    column_slugs = [column["slug"] for column in meta["columns"]]
    rows = db.fetch_rows(meta["slug"], column_slugs)
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
    col_slugs = list(values.keys())

    row_id = db.insert_row(meta["slug"], values)
    row = db.fetch_row(meta["slug"], col_slugs, row_id)
    return dict(row)


def update_row(slug, row_id, payload):
    """Update a row in place and return the new values.

    Raises TableNotFoundError, RowNotFoundError, or ValueError.
    """
    meta = get_table_meta(slug)
    if meta is None:
        raise TableNotFoundError(f'Table "{slug}" not found.')
    if not db.row_exists(meta["slug"], row_id):
        raise RowNotFoundError(f"Record {row_id} not found.")

    values = _coerce_row_values(meta["columns"], payload)
    col_slugs = list(values.keys())

    db.update_row_values(meta["slug"], values, row_id)
    row = db.fetch_row(meta["slug"], col_slugs, row_id)
    return dict(row)


def delete_row(slug, row_id):
    """Delete a row. Raises TableNotFoundError or RowNotFoundError."""
    meta = get_table_meta(slug)
    if meta is None:
        raise TableNotFoundError(f'Table "{slug}" not found.')

    deleted_count = db.delete_row_record(meta["slug"], row_id)
    if deleted_count == 0:
        raise RowNotFoundError(f"Record {row_id} not found.")
