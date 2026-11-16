"""Local maintenance work-order demo with synthetic tenant separation."""
from __future__ import annotations

import json
import os
import re
import sqlite3
from contextlib import closing
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

ROOT = Path(__file__).resolve().parent
DB = Path(os.environ.get("TITAN_DB_PATH", ROOT / "maintenance.sqlite3"))
TENANTS = {"demo-north", "demo-south"}
STATUSES = {"open", "in_progress", "closed"}
PRIORITIES = {"low", "normal", "high", "critical"}


def connect():
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    db.execute("""CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY, tenant_id TEXT NOT NULL, asset_code TEXT NOT NULL,
        title TEXT NOT NULL, description TEXT NOT NULL, priority TEXT NOT NULL,
        due_date TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'open',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
    db.commit()
    return db


def validate(payload):
    if not isinstance(payload, dict): raise ValueError("El cuerpo debe ser un objeto JSON.")
    asset = str(payload.get("asset_code", "")).strip().upper()
    title = str(payload.get("title", "")).strip()
    description = str(payload.get("description", "")).strip()
    priority = payload.get("priority")
    try: due = date.fromisoformat(payload.get("due_date", ""))
    except (ValueError, TypeError): raise ValueError("La fecha objetivo debe tener formato AAAA-MM-DD.")
    if not re.fullmatch(r"[A-Z0-9_-]{2,24}", asset): raise ValueError("El código de equipo debe tener entre 2 y 24 caracteres válidos.")
    if not 4 <= len(title) <= 100: raise ValueError("El título debe tener entre 4 y 100 caracteres.")
    if len(description) > 1000: raise ValueError("La descripción admite hasta 1000 caracteres.")
    if priority not in PRIORITIES: raise ValueError("Prioridad no admitida.")
    return {"asset_code": asset, "title": title, "description": description,
            "priority": priority, "due_date": due.isoformat()}


class Handler(BaseHTTPRequestHandler):
    def json(self, status, body):
        raw = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(status); self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store"); self.send_header("Content-Length", str(len(raw)))
        self.end_headers(); self.wfile.write(raw)

    def tenant(self):
        tenant = self.headers.get("X-Tenant-ID", "")
        if tenant not in TENANTS: raise ValueError("Selecciona un tenant demo válido.")
        return tenant

    def body(self):
        size = int(self.headers.get("Content-Length", "0"))
        if not 1 <= size <= 16384: raise ValueError("El cuerpo debe tener entre 1 y 16384 bytes.")
        try: return json.loads(self.rfile.read(size))
        except json.JSONDecodeError: raise ValueError("JSON inválido.")

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/health": return self.json(200, {"status": "ok"})
        if path in ("/", "/index.html", "/app.js", "/styles.css"):
            file = "index.html" if path == "/" else path[1:]
            types = {"index.html": "text/html", "app.js": "text/javascript", "styles.css": "text/css"}
            data = (ROOT / "static" / file).read_bytes()
            self.send_response(200); self.send_header("Content-Type", types[file] + "; charset=utf-8")
            self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data); return
        if path != "/api/orders": return self.json(404, {"error": "Ruta no encontrada."})
        try: tenant = self.tenant()
        except ValueError as exc: return self.json(400, {"error": str(exc)})
        status = parse_qs(urlparse(self.path).query).get("status", [None])[0]
        if status and status not in STATUSES: return self.json(400, {"error": "Estado no admitido."})
        sql, args = "SELECT * FROM orders WHERE tenant_id = ?", [tenant]
        if status: sql += " AND status = ?"; args.append(status)
        sql += " ORDER BY CASE priority WHEN 'critical' THEN 0 WHEN 'high' THEN 1 WHEN 'normal' THEN 2 ELSE 3 END, due_date"
        with closing(connect()) as db: rows = db.execute(sql, args).fetchall()
        return self.json(200, {"orders": [dict(row) for row in rows]})

    def do_POST(self):
        if urlparse(self.path).path != "/api/orders": return self.json(404, {"error": "Ruta no encontrada."})
        try: tenant, value = self.tenant(), validate(self.body())
        except ValueError as exc: return self.json(400, {"error": str(exc)})
        with closing(connect()) as db, db:
            cursor = db.execute("""INSERT INTO orders (tenant_id,asset_code,title,description,priority,due_date)
                VALUES (:tenant_id,:asset_code,:title,:description,:priority,:due_date)"", {**value, "tenant_id": tenant})
            row = db.execute("SELECT * FROM orders WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return self.json(201, dict(row))

    def do_PATCH(self):
        match = re.fullmatch(r"/api/orders/(\d+)", urlparse(self.path).path)
        if not match: return self.json(404, {"error": "Ruta no encontrada."})
        try:
            tenant, payload = self.tenant(), self.body()
            if not isinstance(payload, dict) or set(payload) != {"status"} or payload["status"] not in STATUSES:
                raise ValueError("El cuerpo debe incluir un estado admitido.")
        except ValueError as exc: return self.json(400, {"error": str(exc)})
        with closing(connect()) as db, db:
            db.execute("UPDATE orders SET status = ? WHERE id = ? AND tenant_id = ?", (payload["status"], int(match.group(1)), tenant))
            row = db.execute("SELECT * FROM orders WHERE id = ? AND tenant_id = ?", (int(match.group(1)), tenant)).fetchone()
        return self.json(200, dict(row)) if row else self.json(404, {"error": "Orden no encontrada."})

    def do_DELETE(self):
        match = re.fullmatch(r"/api/orders/(\d+)", urlparse(self.path).path)
        if not match: return self.json(404, {"error": "Ruta no encontrada."})
        try: tenant = self.tenant()
        except ValueError as exc: return self.json(400, {"error": str(exc)})
        with closing(connect()) as db, db:
            count = db.execute("DELETE FROM orders WHERE id = ? AND tenant_id = ?", (int(match.group(1)), tenant)).rowcount
        return self.json(200, {"deleted": True}) if count else self.json(404, {"error": "Orden no encontrada."})


def main():
    connect().close()
    port = int(os.environ.get("PORT", "8090"))
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Titan Maintenance SaaS demo en http://127.0.0.1:{port}")
    server.serve_forever()


if __name__ == "__main__": main()
