from pathlib import Path

from zipora.core.favorites import FavoritesStore


def test_favorites_add_remove(tmp_path: Path) -> None:
    store = FavoritesStore(tmp_path / "favorites.json")
    path = tmp_path / "archive.zip"

    store.add("Archive", path)
    store.add("Archive Updated", path)
    assert len(store.list_items()) == 1
    assert store.list_items()[0].name == "Archive Updated"

    store.remove(path)
    assert store.list_items() == []
