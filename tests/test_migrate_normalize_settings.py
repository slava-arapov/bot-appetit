import glob
import sqlite3

import pytest

import migrate_normalize_settings as migration
from config import SCHEMA_PATH

# (user_id, servings, cooking_time) — значения из прод-БД и граничные случаи
ROWS = [
    (1, "2", "30 мин"),  # время нормализуется, порции уже ок
    (2, "1, иногда 2", "Не важно"),  # оба нормализуются
    (3, "на 1", "Не более 1 часа"),
    (4, "4", "Как можно меньше"),  # время не распознано — остаётся как есть
    (5, "3", "30"),  # уже нормализовано — не трогаем
    (6, None, None),  # анкета не заполнена
    (7, "семья", "1 час"),  # порции не распознаны, время — да
    (8, "2", "30 часов в неделю"),  # число с другой единицей — не минуты
]


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "bot.db"
    conn = sqlite3.connect(path)
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        conn.executescript(f.read())
    for user_id, servings, cooking_time in ROWS:
        conn.execute("INSERT INTO users (user_id, status) VALUES (?, 'approved')", (user_id,))
        conn.execute(
            "INSERT INTO profiles (user_id, servings, cooking_time) VALUES (?, ?, ?)",
            (user_id, servings, cooking_time),
        )
    conn.commit()
    conn.close()
    return str(path)


def read(path):
    conn = sqlite3.connect(path)
    rows = conn.execute("SELECT user_id, servings, cooking_time FROM profiles ORDER BY user_id").fetchall()
    conn.close()
    return rows


def test_plan_lists_only_real_changes(db_path):
    conn = sqlite3.connect(db_path)
    changes, unrecognized = migration.plan(conn)
    conn.close()

    assert {(c.user_id, c.field, c.old, c.new) for c in changes} == {
        (1, "cooking_time", "30 мин", "30"),
        (2, "servings", "1, иногда 2", "1"),
        (2, "cooking_time", "Не важно", "any"),
        (3, "servings", "на 1", "1"),
        (3, "cooking_time", "Не более 1 часа", "60"),
        (7, "cooking_time", "1 час", "60"),
    }
    assert {(u.user_id, u.field, u.value) for u in unrecognized} == {
        (4, "cooking_time", "Как можно меньше"),
        (7, "servings", "семья"),
        (8, "cooking_time", "30 часов в неделю"),
    }


def test_dry_run_changes_nothing(db_path, capsys):
    before = read(db_path)

    assert migration.main(["--db", db_path]) == 0

    assert read(db_path) == before
    assert glob.glob(db_path + ".bak-*") == []
    out = capsys.readouterr().out
    assert "Как можно меньше" in out
    assert "--apply" in out


def test_apply_writes_normalized_values_and_makes_backup(db_path):
    before = read(db_path)

    assert migration.main(["--db", db_path, "--apply"]) == 0

    assert read(db_path) == [
        (1, "2", "30"),
        (2, "1", "any"),
        (3, "1", "60"),
        (4, "4", "Как можно меньше"),
        (5, "3", "30"),
        (6, None, None),
        (7, "семья", "60"),
        (8, "2", "30 часов в неделю"),
    ]
    backups = glob.glob(db_path + ".bak-*")
    assert len(backups) == 1
    assert read(backups[0]) == before


def test_apply_is_idempotent(db_path, capsys):
    migration.main(["--db", db_path, "--apply"])
    after_first = read(db_path)
    capsys.readouterr()

    assert migration.main(["--db", db_path, "--apply"]) == 0

    assert read(db_path) == after_first
    assert "Нечего менять" in capsys.readouterr().out
    assert len(glob.glob(db_path + ".bak-*")) == 1  # без изменений второй бэкап не нужен


def test_missing_db_is_an_error(tmp_path, capsys):
    assert migration.main(["--db", str(tmp_path / "nope.db")]) == 1
    assert "не найден" in capsys.readouterr().out
