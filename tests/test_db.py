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


def _create_sample_table():
    return db.create_table(
        "Employees",
        [{"name": "Name", "type": "text"}, {"name": "Age", "type": "number"}],
    )


def test_slugify_basic():
    assert db.slugify("First Name") == "first_name"


def test_slugify_leading_digit():
    assert db.slugify("2fast") == "f_2fast"


def test_slugify_rejects_empty():
    with pytest.raises(ValueError):
        db.slugify("   ")


def test_list_tables_empty(app_context):
    assert db.list_tables() == []


def test_create_table(app_context):
    meta = _create_sample_table()
    assert meta["name"] == "Employees"
    assert meta["slug"] == "employees"
    assert [c["slug"] for c in meta["columns"]] == ["name", "age"]
    assert db.list_tables() == [{"name": "Employees", "slug": "employees"}]


def test_create_table_requires_name(app_context):
    with pytest.raises(ValueError):
        db.create_table("", [{"name": "A", "type": "text"}])


def test_create_table_requires_columns(app_context):
    with pytest.raises(ValueError):
        db.create_table("Empty", [])


def test_create_table_rejects_duplicate_name(app_context):
    _create_sample_table()
    with pytest.raises(ValueError):
        db.create_table(
            "Employees", [{"name": "Other", "type": "text"}]
        )


def test_create_table_rejects_unknown_type(app_context):
    with pytest.raises(ValueError):
        db.create_table("Bad", [{"name": "Field", "type": "date"}])


def test_create_table_rejects_duplicate_field_names(app_context):
    with pytest.raises(ValueError):
        db.create_table(
            "Dup", [{"name": "Name", "type": "text"}, {"name": "name", "type": "text"}]
        )


def test_get_table_data_not_found(app_context):
    with pytest.raises(db.TableNotFoundError):
        db.get_table_data("missing")


def test_row_crud_lifecycle(app_context):
    _create_sample_table()

    row = db.create_row("employees", {"name": "Ada", "age": "36"})
    assert row["name"] == "Ada"
    assert row["age"] == 36
    row_id = row["id"]

    data = db.get_table_data("employees")
    assert data["rows"] == [row]

    updated = db.update_row("employees", row_id, {"name": "Ada Lovelace", "age": "37"})
    assert updated["name"] == "Ada Lovelace"

    db.delete_row("employees", row_id)

    final = db.get_table_data("employees")
    assert final["rows"] == []


def test_create_row_rejects_invalid_number(app_context):
    _create_sample_table()
    with pytest.raises(ValueError):
        db.create_row("employees", {"name": "Ada", "age": "not-a-number"})


def test_create_row_table_not_found(app_context):
    with pytest.raises(db.TableNotFoundError):
        db.create_row("missing", {"name": "Ada"})


def test_update_row_not_found(app_context):
    _create_sample_table()
    with pytest.raises(db.RowNotFoundError):
        db.update_row("employees", 999, {"name": "Ada", "age": "1"})


def test_update_row_table_not_found(app_context):
    with pytest.raises(db.TableNotFoundError):
        db.update_row("missing", 1, {"name": "Ada"})


def test_delete_row_not_found(app_context):
    _create_sample_table()
    with pytest.raises(db.RowNotFoundError):
        db.delete_row("employees", 999)


def test_delete_row_table_not_found(app_context):
    with pytest.raises(db.TableNotFoundError):
        db.delete_row("missing", 1)
