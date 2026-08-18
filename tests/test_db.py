import pytest

import db
from app import app as flask_app


@pytest.fixture
def app_context(tmp_path):
    flask_app.config["TESTING"] = True
    flask_app.config["DATABASE"] = str(tmp_path / "test.db")
    with flask_app.app_context():
        yield
        db.close_db()


def test_fetch_all_tables_empty(app_context):
    assert db.fetch_all_tables() == []


def test_fetch_table_by_slug_missing(app_context):
    assert db.fetch_table_by_slug("missing") is None


def test_insert_and_fetch_table_record(app_context):
    table_id = db.insert_table_record("Employees", "employees")
    row = db.fetch_table_by_slug("employees")
    assert row["id"] == table_id
    assert row["name"] == "Employees"
    assert row["slug"] == "employees"
    assert [dict(t) for t in db.fetch_all_tables()] == [
        {"name": "Employees", "slug": "employees"}
    ]


def test_insert_and_fetch_columns(app_context):
    table_id = db.insert_table_record("Employees", "employees")
    db.insert_column_record(table_id, "Name", "name", "text", 0)
    db.insert_column_record(table_id, "Age", "age", "number", 1)

    columns = db.fetch_columns(table_id)
    assert [dict(c) for c in columns] == [
        {"name": "Name", "slug": "name", "type": "text"},
        {"name": "Age", "slug": "age", "type": "number"},
    ]


def test_data_table_row_crud(app_context):
    table_id = db.insert_table_record("Employees", "employees")
    db.insert_column_record(table_id, "Name", "name", "text", 0)
    db.insert_column_record(table_id, "Age", "age", "number", 1)
    db.create_data_table("employees", '"name" TEXT, "age" REAL')

    row_id = db.insert_row("employees", {"name": "Ada", "age": 36.0})
    row = db.fetch_row("employees", ["name", "age"], row_id)
    assert dict(row) == {"id": row_id, "name": "Ada", "age": 36.0}

    rows = db.fetch_rows("employees", ["name", "age"])
    assert [dict(r) for r in rows] == [{"id": row_id, "name": "Ada", "age": 36.0}]

    assert db.row_exists("employees", row_id) is True
    assert db.row_exists("employees", row_id + 1) is False

    db.update_row_values("employees", {"name": "Ada Lovelace"}, row_id)
    updated = db.fetch_row("employees", ["name"], row_id)
    assert dict(updated) == {"id": row_id, "name": "Ada Lovelace"}

    deleted_count = db.delete_row_record("employees", row_id)
    assert deleted_count == 1
    assert db.row_exists("employees", row_id) is False


def test_delete_row_record_returns_zero_when_missing(app_context):
    table_id = db.insert_table_record("Employees", "employees")
    db.insert_column_record(table_id, "Name", "name", "text", 0)
    db.create_data_table("employees", '"name" TEXT')

    assert db.delete_row_record("employees", 999) == 0

