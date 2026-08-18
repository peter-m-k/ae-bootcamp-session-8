import pytest

import logic
from app import app as flask_app


@pytest.fixture
def app_context(tmp_path):
    flask_app.config["TESTING"] = True
    flask_app.config["DATABASE"] = str(tmp_path / "test.db")
    with flask_app.app_context():
        yield
        logic.db.close_db()


def _create_sample_table():
    return logic.create_table(
        "Employees",
        [{"name": "Name", "type": "text"}, {"name": "Age", "type": "number"}],
    )


def test_slugify_basic():
    assert logic.slugify("First Name") == "first_name"


def test_slugify_leading_digit():
    assert logic.slugify("2fast") == "f_2fast"


def test_slugify_rejects_empty():
    with pytest.raises(ValueError):
        logic.slugify("   ")


def test_list_tables_empty(app_context):
    assert logic.list_tables() == []


def test_create_table(app_context):
    meta = _create_sample_table()
    assert meta["name"] == "Employees"
    assert meta["slug"] == "employees"
    assert [c["slug"] for c in meta["columns"]] == [
        "PK",
        "CREATE_TS",
        "UPDATE_TS",
        "name",
        "age",
    ]
    assert logic.list_tables() == [{"name": "Employees", "slug": "employees"}]


def test_create_table_requires_name(app_context):
    with pytest.raises(ValueError):
        logic.create_table("", [{"name": "A", "type": "text"}])


def test_create_table_requires_columns(app_context):
    with pytest.raises(ValueError):
        logic.create_table("Empty", [])


def test_create_table_rejects_duplicate_name(app_context):
    _create_sample_table()
    with pytest.raises(ValueError):
        logic.create_table("Employees", [{"name": "Other", "type": "text"}])


def test_create_table_rejects_unknown_type(app_context):
    with pytest.raises(ValueError):
        logic.create_table("Bad", [{"name": "Field", "type": "date"}])


def test_create_table_rejects_duplicate_field_names(app_context):
    with pytest.raises(ValueError):
        logic.create_table(
            "Dup", [{"name": "Name", "type": "text"}, {"name": "name", "type": "text"}]
        )


@pytest.mark.parametrize("reserved_name", ["PK", "pk", "Create_TS", "UPDATE_TS"])
def test_create_table_rejects_reserved_column_names(app_context, reserved_name):
    with pytest.raises(ValueError):
        logic.create_table("Bad", [{"name": reserved_name, "type": "text"}])


def test_get_table_data_not_found(app_context):
    with pytest.raises(logic.TableNotFoundError):
        logic.get_table_data("missing")


def test_row_crud_lifecycle(app_context):
    _create_sample_table()

    row = logic.create_row("employees", {"name": "Ada", "age": "36"})
    assert row["name"] == "Ada"
    assert row["age"] == 36
    assert row["PK"] is not None
    assert row["CREATE_TS"]
    assert row["UPDATE_TS"] is None
    row_id = row["PK"]

    data = logic.get_table_data("employees")
    assert data["rows"] == [row]

    updated = logic.update_row(
        "employees", row_id, {"name": "Ada Lovelace", "age": "37"}
    )
    assert updated["name"] == "Ada Lovelace"
    assert updated["CREATE_TS"] == row["CREATE_TS"]
    assert updated["UPDATE_TS"]

    logic.delete_row("employees", row_id)

    final = logic.get_table_data("employees")
    assert final["rows"] == []


def test_create_row_rejects_invalid_number(app_context):
    _create_sample_table()
    with pytest.raises(ValueError):
        logic.create_row("employees", {"name": "Ada", "age": "not-a-number"})


def test_create_table_with_integer_column(app_context):
    meta = logic.create_table(
        "Orders", [{"name": "Quantity", "type": "integer"}]
    )
    system_slugs = {c["slug"] for c in logic.SYSTEM_COLUMNS}
    user_columns = [c for c in meta["columns"] if c["slug"] not in system_slugs]
    assert user_columns == [
        {"name": "Quantity", "slug": "quantity", "type": "integer", "editable": True, "filterable": True}
    ]

    row = logic.create_row("orders", {"quantity": "5"})
    assert row["quantity"] == 5
    assert isinstance(row["quantity"], int)


def test_create_row_rejects_non_integer_value(app_context):
    logic.create_table("Orders", [{"name": "Quantity", "type": "integer"}])
    with pytest.raises(ValueError):
        logic.create_row("orders", {"quantity": "3.5"})


def test_create_row_table_not_found(app_context):
    with pytest.raises(logic.TableNotFoundError):
        logic.create_row("missing", {"name": "Ada"})


def test_update_row_not_found(app_context):
    _create_sample_table()
    with pytest.raises(logic.RowNotFoundError):
        logic.update_row("employees", 999, {"name": "Ada", "age": "1"})


def test_update_row_table_not_found(app_context):
    with pytest.raises(logic.TableNotFoundError):
        logic.update_row("missing", 1, {"name": "Ada"})


def test_delete_row_not_found(app_context):
    _create_sample_table()
    with pytest.raises(logic.RowNotFoundError):
        logic.delete_row("employees", 999)


def test_delete_row_table_not_found(app_context):
    with pytest.raises(logic.TableNotFoundError):
        logic.delete_row("missing", 1)
