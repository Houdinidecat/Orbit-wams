"""Órbita: sitio web y API de práctica con almacenamiento real en SQLite."""

from datetime import date, datetime, timezone
import os
from pathlib import Path
import re
import sqlite3
from urllib.parse import urlsplit

from flask import Flask, abort, g, jsonify, request, send_from_directory
from werkzeug.exceptions import HTTPException


PROJECT_ROOT = Path(__file__).resolve().parent
ESTADOS = {"Planificada", "En curso", "Completada"}
FIELDS = {"nombre", "destino", "fecha", "estado", "notas"}
DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}\Z", re.ASCII)
MAX_RECORD_ID = 2**63 - 1


def now_utc():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def connect_database(path):
    connection = sqlite3.connect(str(path), timeout=5)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout = 5000")
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database(app):
    path = Path(app.config["DATABASE_PATH"]).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    app.config["DATABASE_PATH"] = str(path)
    connection = connect_database(path)
    try:
        connection.execute("PRAGMA journal_mode = WAL")
        # The write lock also prevents two workers from both seeding a new database.
        connection.executescript("BEGIN IMMEDIATE;\n" + (PROJECT_ROOT / "schema.sql").read_text())
        first_initialization = connection.execute("PRAGMA user_version").fetchone()[0] == 0
        if first_initialization:
            if app.config["SEED_DEMO_DATA"]:
                timestamp = now_utc()
                examples = [
                    ("Ejemplo · Observación lunar", "La Luna", "", "Planificada"),
                    ("Ejemplo · Explorar Marte", "Marte", "", "En curso"),
                    ("Ejemplo · Conocer la Tierra", "La Tierra", "", "Completada"),
                ]
                connection.executemany(
                    "INSERT INTO misiones "
                    "(nombre, destino, fecha, estado, notas, creado_en, actualizado_en) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    [
                        (*example, "Registro de demostración. Puedes editarlo o eliminarlo.", timestamp, timestamp)
                        for example in examples
                    ],
                )
            connection.execute("PRAGMA user_version = 1")
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def validate_payload(payload):
    if not isinstance(payload, dict):
        return None, {"formulario": "Envía un objeto JSON con los datos de la misión."}
    unknown = set(payload) - FIELDS
    if unknown:
        return None, {"formulario": "El registro contiene campos no permitidos."}

    values = {}
    errors = {}
    defaults = {"nombre": "", "destino": "", "fecha": "", "estado": "Planificada", "notas": ""}
    for field, default in defaults.items():
        value = payload.get(field, default)
        if not isinstance(value, str):
            errors[field] = "Este campo debe ser texto."
        else:
            try:
                value.encode("utf-8")
                if "\x00" in value:
                    raise ValueError
            except (UnicodeEncodeError, ValueError):
                errors[field] = "Este campo contiene caracteres no válidos."
            else:
                values[field] = value.strip()

    for field, label, limit in (("nombre", "El nombre", 120), ("destino", "El destino", 100)):
        if field in errors:
            continue
        if not values[field]:
            errors[field] = f"{label} es obligatorio."
        elif len(values[field]) > limit:
            errors[field] = f"{label} admite hasta {limit} caracteres."

    if "estado" not in errors and values["estado"] not in ESTADOS:
        errors["estado"] = "Selecciona Planificada, En curso o Completada."
    if "notas" not in errors and len(values["notas"]) > 2000:
        errors["notas"] = "Las notas admiten hasta 2000 caracteres."
    if "fecha" not in errors and values["fecha"]:
        try:
            if not DATE_PATTERN.fullmatch(values["fecha"]):
                raise ValueError
            date.fromisoformat(values["fecha"])
        except ValueError:
            errors["fecha"] = "Introduce una fecha válida con el formato AAAA-MM-DD."
    return values, errors


def create_app(config=None):
    app = Flask(__name__, static_folder=None)
    app.config.from_mapping(
        DATABASE_PATH=os.environ.get("DATABASE_PATH", str(PROJECT_ROOT / "data" / "orbita.sqlite3")),
        SEED_DEMO_DATA=True,
        MAX_CONTENT_LENGTH=32 * 1024,
        JSON_SORT_KEYS=False,
    )
    if config:
        app.config.update(config)
    app.json.ensure_ascii = False
    initialize_database(app)

    def database():
        if "database" not in g:
            g.database = connect_database(app.config["DATABASE_PATH"])
        return g.database

    @app.teardown_appcontext
    def close_database(_error=None):
        connection = g.pop("database", None)
        if connection is not None:
            connection.close()

    @app.before_request
    def protect_mutations():
        if request.path.startswith("/api/") and request.method in {"POST", "PUT", "DELETE"}:
            origin = request.headers.get("Origin")
            if origin:
                try:
                    parsed = urlsplit(origin)
                    same_origin_host = parsed.scheme in {"http", "https"} and parsed.netloc == request.host
                except ValueError:
                    same_origin_host = False
                if not same_origin_host:
                    return jsonify(error="Esta operación debe realizarse desde el sitio de Órbita."), 403
            # DELETE has no body. POST and PUT accept only JSON, never form submissions.
            if request.method in {"POST", "PUT"} and not request.is_json:
                return jsonify(error="Envía los datos con Content-Type: application/json."), 415

    @app.after_request
    def response_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if request.path.startswith("/api/") or request.path == "/healthz":
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.errorhandler(HTTPException)
    def http_error(error):
        if request.path.startswith("/api/") or request.path == "/healthz":
            messages = {
                400: "No se pudo leer el JSON enviado. Revisa los datos e inténtalo de nuevo.",
                404: "Registro o recurso no encontrado.",
                405: "Método no permitido para este recurso.",
                413: "El registro supera el tamaño máximo permitido.",
                415: "Envía los datos con Content-Type: application/json.",
            }
            return jsonify(error=messages.get(error.code, "No se pudo completar la solicitud.")), error.code
        return error

    @app.errorhandler(sqlite3.Error)
    def database_error(error):
        app.logger.exception("No se pudo completar una operación con SQLite")
        busy = isinstance(error, sqlite3.OperationalError) and any(
            word in str(error).lower() for word in ("locked", "busy")
        )
        message = (
            "La base de datos está ocupada. Inténtalo de nuevo en unos segundos."
            if busy else "No se pudo acceder a la base de datos. Inténtalo de nuevo."
        )
        return jsonify(error=message), 503

    @app.errorhandler(500)
    def unexpected_error(error):
        if request.path.startswith("/api/") or request.path == "/healthz":
            return jsonify(error="No se pudo completar la operación. Inténtalo de nuevo."), 500
        return error

    def record_or_404(record_id):
        if not 1 <= record_id <= MAX_RECORD_ID:
            abort(404)
        row = database().execute("SELECT * FROM misiones WHERE id = ?", (record_id,)).fetchone()
        if row is None:
            abort(404)
        return dict(row)

    @app.get("/api/misiones")
    def list_records():
        rows = database().execute("SELECT * FROM misiones ORDER BY id DESC").fetchall()
        return jsonify(registros=[dict(row) for row in rows], total=len(rows))

    @app.get("/api/misiones/<int:record_id>")
    def get_record(record_id):
        return jsonify(registro=record_or_404(record_id))

    @app.post("/api/misiones")
    def add_record():
        values, errors = validate_payload(request.get_json())
        if errors:
            return jsonify(error="Revisa los campos del formulario.", campos=errors), 400
        timestamp = now_utc()
        connection = database()
        with connection:
            cursor = connection.execute(
                "INSERT INTO misiones "
                "(nombre, destino, fecha, estado, notas, creado_en, actualizado_en) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    values["nombre"], values["destino"], values["fecha"], values["estado"],
                    values["notas"], timestamp, timestamp,
                ),
            )
        response = jsonify(registro=record_or_404(cursor.lastrowid))
        response.status_code = 201
        response.headers["Location"] = f"/api/misiones/{cursor.lastrowid}"
        return response

    @app.put("/api/misiones/<int:record_id>")
    def edit_record(record_id):
        record_or_404(record_id)
        values, errors = validate_payload(request.get_json())
        if errors:
            return jsonify(error="Revisa los campos del formulario.", campos=errors), 400
        connection = database()
        with connection:
            cursor = connection.execute(
                "UPDATE misiones SET nombre = ?, destino = ?, fecha = ?, estado = ?, notas = ?, actualizado_en = ? "
                "WHERE id = ?",
                (
                    values["nombre"], values["destino"], values["fecha"], values["estado"],
                    values["notas"], now_utc(), record_id,
                ),
            )
            if cursor.rowcount == 0:
                abort(404)
        return jsonify(registro=record_or_404(record_id))

    @app.delete("/api/misiones/<int:record_id>")
    def delete_record(record_id):
        if not 1 <= record_id <= MAX_RECORD_ID:
            abort(404)
        connection = database()
        with connection:
            cursor = connection.execute("DELETE FROM misiones WHERE id = ?", (record_id,))
            if cursor.rowcount == 0:
                abort(404)
        return jsonify(mensaje="Registro eliminado.")

    @app.get("/healthz")
    def healthcheck():
        database().execute("SELECT 1").fetchone()
        return jsonify(estado="ok", base_de_datos="conectada")

    @app.get("/")
    def home():
        return send_from_directory(PROJECT_ROOT / "dist", "index.html")

    @app.get("/assets/<path:filename>")
    def assets(filename):
        return send_from_directory(PROJECT_ROOT / "dist" / "assets", filename)

    @app.get("/<path:filename>")
    def frontend(filename):
        allowed = {"index.html", "registro.html", "procedimiento.html", "styles.css", "crud.css", "crud.js"}
        if filename not in allowed:
            abort(404)
        return send_from_directory(PROJECT_ROOT / "dist", filename)

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")), debug=False)
