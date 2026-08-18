import os
from pathlib import Path

from flask import Flask, jsonify, render_template, request

import db

app = Flask(__name__)
app.config["DATABASE"] = os.environ.get(
    "DATABASE", str(Path(__file__).parent / "data.db")
)
db.init_app(app)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/tables", methods=["GET"])
def list_tables():
    return jsonify(db.list_tables())


@app.route("/api/tables", methods=["POST"])
def create_table():
    payload = request.get_json(silent=True) or {}
    try:
        table = db.create_table(payload.get("name"), payload.get("columns") or [])
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    return jsonify(table), 201


@app.route("/api/tables/<slug>", methods=["GET"])
def get_table(slug):
    try:
        return jsonify(db.get_table_data(slug))
    except db.TableNotFoundError:
        return jsonify(error="Table not found."), 404


@app.route("/api/tables/<slug>/rows", methods=["POST"])
def create_row(slug):
    payload = request.get_json(silent=True) or {}
    try:
        row = db.create_row(slug, payload)
    except db.TableNotFoundError:
        return jsonify(error="Table not found."), 404
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    return jsonify(row), 201


@app.route("/api/tables/<slug>/rows/<int:row_id>", methods=["PUT"])
def update_row(slug, row_id):
    payload = request.get_json(silent=True) or {}
    try:
        row = db.update_row(slug, row_id, payload)
    except db.TableNotFoundError:
        return jsonify(error="Table not found."), 404
    except db.RowNotFoundError:
        return jsonify(error="Record not found."), 404
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    return jsonify(row)


@app.route("/api/tables/<slug>/rows/<int:row_id>", methods=["DELETE"])
def delete_row(slug, row_id):
    try:
        db.delete_row(slug, row_id)
    except db.TableNotFoundError:
        return jsonify(error="Table not found."), 404
    except db.RowNotFoundError:
        return jsonify(error="Record not found."), 404
    return "", 204


if __name__ == "__main__":
    app.run()
