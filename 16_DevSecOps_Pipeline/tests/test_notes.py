import pytest

from app.notes import MAX_TITLE, NoteError, NoteStore


def test_add_and_get():
    store = NoteStore()
    note = store.add("  First  ", "hello")
    assert note == {"id": 1, "title": "First", "body": "hello"}
    assert store.get(1) == note


def test_ids_increase():
    store = NoteStore()
    assert store.add("a")["id"] == 1
    assert store.add("b")["id"] == 2
    assert [n["title"] for n in store.list()] == ["a", "b"]


def test_title_required():
    with pytest.raises(NoteError):
        NoteStore().add("   ")


def test_title_too_long():
    with pytest.raises(NoteError):
        NoteStore().add("x" * (MAX_TITLE + 1))


def test_delete():
    store = NoteStore()
    store.add("a")
    assert store.delete(1) is True
    assert store.delete(1) is False
    assert store.get(1) is None
