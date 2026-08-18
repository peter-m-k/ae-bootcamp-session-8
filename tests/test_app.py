import pytest

from app import app


@pytest.fixture
def client(tmp_path):
    app.config["TESTING"] = True
    app.config["DATABASE"] = str(tmp_path / "test.db")
    with app.test_client() as client:
        yield client


def test_index_serves_spa_shell(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b'id="app"' in response.data
    assert b"Reference Data Management" in response.data


def test_list_tables_empty(client):
    response = client.get("/api/tables")
    assert response.status_code == 200
    assert response.get_json() == []


def test_create_table_success(client):
    response = client.post(
        "/api/tables",
        json={"name": "Employees", "columns": [{"name": "Name", "type": "text"}]},
    )
    assert response.status_code == 201
    assert response.get_json()["slug"] == "employees"

    listed = client.get("/api/tables").get_json()
    assert listed == [{"name": "Employees", "slug": "employees"}]


def test_create_table_validation_error_returns_400(client):
    response = client.post("/api/tables", json={"name": "", "columns": []})
    assert response.status_code == 400
    assert "error" in response.get_json()


def test_create_table_rejects_reserved_column_name(client):
    response = client.post(
        "/api/tables",
        json={"name": "Bad", "columns": [{"name": "PK", "type": "text"}]},
    )
    assert response.status_code == 400


def test_integer_column_round_trip(client):
    client.post(
        "/api/tables",
        json={"name": "Orders", "columns": [{"name": "Quantity", "type": "integer"}]},
    )
    create_resp = client.post("/api/tables/orders/rows", json={"quantity": "5"})
    assert create_resp.status_code == 201
    assert create_resp.get_json()["quantity"] == 5

    invalid_resp = client.post("/api/tables/orders/rows", json={"quantity": "3.5"})
    assert invalid_resp.status_code == 400


def test_get_table_not_found_returns_404(client):
    response = client.get("/api/tables/missing")
    assert response.status_code == 404


def _create_sample_table(client):
    client.post(
        "/api/tables",
        json={
            "name": "Employees",
            "columns": [
                {"name": "Name", "type": "text"},
                {"name": "Age", "type": "number"},
            ],
        },
    )


def test_row_crud_over_http(client):
    _create_sample_table(client)

    create_resp = client.post(
        "/api/tables/employees/rows", json={"name": "Ada", "age": "36"}
    )
    assert create_resp.status_code == 201
    row = create_resp.get_json()
    assert row["name"] == "Ada"
    assert row["age"] == 36
    assert row["CREATE_TS"]
    assert row["UPDATE_TS"] is None
    row_id = row["PK"]

    get_resp = client.get("/api/tables/employees")
    assert get_resp.status_code == 200
    assert get_resp.get_json()["rows"] == [row]

    update_resp = client.put(
        f"/api/tables/employees/rows/{row_id}",
        json={"name": "Ada Lovelace", "age": "37"},
    )
    assert update_resp.status_code == 200
    assert update_resp.get_json()["name"] == "Ada Lovelace"
    assert update_resp.get_json()["UPDATE_TS"]

    delete_resp = client.delete(f"/api/tables/employees/rows/{row_id}")
    assert delete_resp.status_code == 204

    final = client.get("/api/tables/employees").get_json()
    assert final["rows"] == []


def test_create_row_invalid_value_returns_400(client):
    _create_sample_table(client)
    response = client.post(
        "/api/tables/employees/rows", json={"name": "Ada", "age": "not-a-number"}
    )
    assert response.status_code == 400


def test_create_row_table_not_found_returns_404(client):
    response = client.post("/api/tables/missing/rows", json={"name": "Ada"})
    assert response.status_code == 404


def test_update_row_not_found_returns_404(client):
    _create_sample_table(client)
    response = client.put(
        "/api/tables/employees/rows/999", json={"name": "Ada", "age": "1"}
    )
    assert response.status_code == 404


def test_delete_row_not_found_returns_404(client):
    _create_sample_table(client)
    response = client.delete("/api/tables/employees/rows/999")
    assert response.status_code == 404

