"""Pruebas de integración de la API, validación y persistencia en SQLite."""

from pathlib import Path
import json
import sqlite3
import tempfile
import unittest

from app import create_app


class MissionAPITests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "orbita.sqlite3"
        self.config = {
            "TESTING": True,
            "DATABASE_PATH": str(self.database_path),
            "SEED_DEMO_DATA": False,
        }
        self.app = create_app(self.config)
        self.client = self.app.test_client()
        self.example = {
            "nombre": "Observación lunar",
            "destino": "La Luna",
            "fecha": "2026-11-08",
            "estado": "Planificada",
            "notas": "Comparar las fases lunares.",
        }

    def tearDown(self):
        self.temporary_directory.cleanup()

    def create_record(self, **changes):
        payload = {**self.example, **changes}
        response = self.client.post("/api/misiones", json=payload)
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()["registro"]

    def test_full_crud_workflow(self):
        self.assertEqual(self.client.get("/api/misiones").get_json(), {"registros": [], "total": 0})
        first = self.create_record()
        second = self.create_record(nombre="Observar Marte", destino="Marte")
        self.assertIsInstance(first["id"], int)
        self.assertTrue(first["creado_en"].endswith("Z"))
        listed = self.client.get("/api/misiones").get_json()
        self.assertEqual(listed["total"], 2)
        self.assertEqual({row["id"] for row in listed["registros"]}, {first["id"], second["id"]})
        self.assertEqual(self.client.get(f'/api/misiones/{first["id"]}').get_json()["registro"], first)

        edited = {**self.example, "nombre": "Misión lunar revisada", "estado": "Completada", "notas": "Finalizada."}
        response = self.client.put(f'/api/misiones/{first["id"]}', json=edited)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["registro"]["estado"], "Completada")
        self.assertEqual(response.get_json()["registro"]["creado_en"], first["creado_en"])
        self.assertEqual(response.get_json()["registro"]["notas"], "Finalizada.")

        deleted = self.client.delete(f'/api/misiones/{first["id"]}')
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(self.client.get(f'/api/misiones/{first["id"]}').status_code, 404)
        self.assertEqual(self.client.get("/api/misiones").get_json()["total"], 1)
        self.assertEqual(self.client.get(f'/api/misiones/{second["id"]}').status_code, 200)

    def test_saved_and_deleted_records_persist_after_restart(self):
        record = self.create_record()
        restarted = create_app(self.config).test_client()
        self.assertEqual(restarted.get(f'/api/misiones/{record["id"]}').get_json()["registro"], record)
        restarted.delete(f'/api/misiones/{record["id"]}')
        another_restart = create_app({**self.config, "SEED_DEMO_DATA": True}).test_client()
        self.assertEqual(another_restart.get("/api/misiones").get_json()["total"], 0)

    def test_demo_data_is_only_created_once(self):
        path = Path(self.temporary_directory.name) / "demo.sqlite3"
        config = {**self.config, "DATABASE_PATH": str(path), "SEED_DEMO_DATA": True}
        demo_client = create_app(config).test_client()
        records = demo_client.get("/api/misiones").get_json()["registros"]
        self.assertEqual(len(records), 3)
        for record in records:
            self.assertTrue(record["nombre"].startswith("Ejemplo"))
            self.assertEqual(demo_client.delete(f'/api/misiones/{record["id"]}').status_code, 200)
        self.assertEqual(create_app(config).test_client().get("/api/misiones").get_json()["total"], 0)

    def test_invalid_records_do_not_write_to_database(self):
        invalid = [
            ({"nombre": "   "}, "nombre"),
            ({"destino": ""}, "destino"),
            ({"nombre": "a" * 121}, "nombre"),
            ({"destino": "a" * 101}, "destino"),
            ({"notas": "a" * 2001}, "notas"),
            ({"fecha": "2026-02-30"}, "fecha"),
            ({"fecha": "20261108"}, "fecha"),
            ({"fecha": "2026-W01-1"}, "fecha"),
            ({"estado": "desconocida"}, "estado"),
            ({"nombre": 123}, "nombre"),
            ({"fecha": None}, "fecha"),
            ({"nombre": "\x00"}, "nombre"),
            ({"notas": "\ud800"}, "notas"),
        ]
        for changes, field in invalid:
            with self.subTest(changes=changes):
                response = self.client.post(
                    "/api/misiones", data=json.dumps({**self.example, **changes}), content_type="application/json"
                )
                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.get_json()["campos"])
        self.assertEqual(self.client.get("/api/misiones").get_json()["total"], 0)

    def test_invalid_edit_keeps_existing_record(self):
        record = self.create_record()
        response = self.client.put(f'/api/misiones/{record["id"]}', json={**self.example, "estado": "No válido"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.client.get(f'/api/misiones/{record["id"]}').get_json()["registro"], record)

    def test_json_shape_unknown_fields_and_content_type(self):
        for payload in ([], "not an object", False, {**self.example, "id": 500}):
            with self.subTest(payload=payload):
                response = self.client.post("/api/misiones", json=payload)
                self.assertEqual(response.status_code, 400)
                self.assertIn("error", response.get_json())
        response = self.client.post("/api/misiones", data="{", content_type="application/json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.get_json())
        self.assertEqual(self.client.post("/api/misiones", data=self.example).status_code, 415)
        self.assertEqual(self.client.post("/api/misiones", data="x" * 33000, content_type="application/json").status_code, 413)
        self.assertEqual(self.client.get("/api/misiones").get_json()["total"], 0)

    def test_missing_records_and_routes_return_json(self):
        for path, method in (
            ("/api/misiones/999", "get"),
            ("/api/misiones/0", "get"),
            ("/api/misiones/999999999999999999999999", "get"),
            ("/api/misiones/999", "put"),
            ("/api/misiones/999", "delete"),
            ("/api/misiones/no-es-id", "get"),
            ("/api/no-existe", "get"),
        ):
            with self.subTest(path=path, method=method):
                kwargs = {"json": self.example} if method == "put" else {}
                response = getattr(self.client, method)(path, **kwargs)
                self.assertEqual(response.status_code, 404)
                self.assertIn("error", response.get_json())

    def test_text_is_parameterized_and_survives_as_data(self):
        injection = "'); DROP TABLE misiones; --"
        record = self.create_record(nombre=injection, notas='<script>alert("hola")</script>')
        self.assertEqual(record["nombre"], injection)
        self.assertEqual(record["notas"], '<script>alert("hola")</script>')
        self.assertEqual(self.client.get("/api/misiones").get_json()["total"], 1)
        self.assertEqual(self.create_record()["id"], record["id"] + 1)

    def test_whitespace_and_optional_fields(self):
        response = self.client.post("/api/misiones", json={"nombre": "  Mi misión  ", "destino": "  La Luna  "})
        self.assertEqual(response.status_code, 201)
        record = response.get_json()["registro"]
        self.assertEqual(record["nombre"], "Mi misión")
        self.assertEqual(record["destino"], "La Luna")
        self.assertEqual(record["fecha"], "")
        self.assertEqual(record["estado"], "Planificada")

    def test_cross_site_mutations_are_blocked_but_same_site_is_allowed(self):
        denied = self.client.post("/api/misiones", json=self.example, headers={"Origin": "https://otro-sitio.example"})
        self.assertEqual(denied.status_code, 403)
        allowed = self.client.post("/api/misiones", json=self.example, headers={"Origin": "https://localhost"})
        self.assertEqual(allowed.status_code, 201)
        record_id = allowed.get_json()["registro"]["id"]
        self.assertEqual(self.client.delete(f"/api/misiones/{record_id}", headers={"Origin": "null"}).status_code, 403)
        self.assertEqual(self.client.get("/api/misiones").get_json()["total"], 1)

    def test_healthcheck_static_files_and_private_paths(self):
        self.assertEqual(self.client.get("/healthz").status_code, 200)
        self.assertEqual(self.client.get("/healthz").get_json()["estado"], "ok")
        for path in ("/", "/index.html", "/styles.css", "/assets/logo-orbita.svg", "/procedimiento.html"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                response.close()
        for path in ("/app.py", "/schema.sql", "/data/orbita.sqlite3", "/assets/../../app.py", "/.git/config"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 404)
        self.assertEqual(self.client.get("/api/misiones").headers["Cache-Control"], "no-store")

    def test_database_constraints_reject_invalid_status(self):
        record = self.create_record()
        with sqlite3.connect(self.database_path) as connection:
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute("UPDATE misiones SET estado = ? WHERE id = ?", ("incorrecto", record["id"]))


if __name__ == "__main__":
    unittest.main()
