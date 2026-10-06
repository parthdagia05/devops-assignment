"""In-memory notes store used by the API."""
import threading

MAX_TITLE = 100
MAX_BODY = 1000


class NoteError(ValueError):
    pass


class NoteStore:
    def __init__(self):
        self._notes = {}
        self._next_id = 1
        self._lock = threading.Lock()

    def add(self, title, body=""):
        title = (title or "").strip()
        body = (body or "").strip()
        if not title:
            raise NoteError("title is required")
        if len(title) > MAX_TITLE:
            raise NoteError(f"title must be at most {MAX_TITLE} characters")
        if len(body) > MAX_BODY:
            raise NoteError(f"body must be at most {MAX_BODY} characters")
        with self._lock:
            note = {"id": self._next_id, "title": title, "body": body}
            self._notes[note["id"]] = note
            self._next_id += 1
        return note

    def get(self, note_id):
        return self._notes.get(note_id)

    def list(self):
        return sorted(self._notes.values(), key=lambda n: n["id"])

    def delete(self, note_id):
        with self._lock:
            return self._notes.pop(note_id, None) is not None
