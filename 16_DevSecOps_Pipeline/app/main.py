import os

from flask import Flask, jsonify, request

from app.notes import NoteError, NoteStore

app = Flask(__name__)
store = NoteStore()

APP_VERSION = os.environ.get("APP_VERSION", "dev")
APP_ENV = os.environ.get("APP_ENV", "local")


@app.get("/")
def index():
    return jsonify(
        app="Session 17 DevSecOps Notes API",
        version=APP_VERSION,
        environment=APP_ENV,
        endpoints=[
            "GET /health",
            "GET /notes",
            "POST /notes",
            "GET /notes/<id>",
            "DELETE /notes/<id>",
        ],
    )


@app.get("/health")
def health():
    return jsonify(status="ok", version=APP_VERSION)


@app.get("/notes")
def list_notes():
    return jsonify(store.list())


@app.post("/notes")
def create_note():
    data = request.get_json(silent=True) or {}
    try:
        note = store.add(data.get("title"), data.get("body", ""))
    except NoteError as e:
        return jsonify(error=str(e)), 400
    return jsonify(note), 201


@app.get("/notes/<int:note_id>")
def get_note(note_id):
    note = store.get(note_id)
    if note is None:
        return jsonify(error="note not found"), 404
    return jsonify(note)


@app.delete("/notes/<int:note_id>")
def delete_note(note_id):
    if not store.delete(note_id):
        return jsonify(error="note not found"), 404
    return "", 204


@app.after_request
def security_headers(res):
    res.headers["X-Content-Type-Options"] = "nosniff"
    res.headers["X-Frame-Options"] = "DENY"
    res.headers["Content-Security-Policy"] = "default-src 'none'"
    return res


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 5000)))
