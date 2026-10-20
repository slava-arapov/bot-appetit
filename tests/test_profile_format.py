from agent.chef import build_system_prompt


def test_system_prompt_includes_readable_settings():
    prompt = build_system_prompt({"servings": "4", "cooking_time": "30"}, [], [])
    assert "Обычно готовит на: 4 порции" in prompt
    assert "Время на готовку: до 30 минут" in prompt


def test_system_prompt_marks_missing_settings():
    prompt = build_system_prompt({}, [], [])
    assert "Обычно готовит на: не указано" in prompt
    assert "Время на готовку: не указано" in prompt


def test_system_prompt_shows_context_with_update_date():
    profile = {"current_context": {"notes": "ужин на двоих", "updated": "2026-10-18"}}
    assert "Текущий контекст: ужин на двоих (обновлено 2026-10-18)" in build_system_prompt(profile, [], [])


def test_system_prompt_shows_context_without_date():
    profile = {"current_context": {"notes": "ужин на двоих", "updated": ""}}
    assert "Текущий контекст: ужин на двоих\n" in build_system_prompt(profile, [], [])


def test_system_prompt_marks_missing_context():
    prompt = build_system_prompt({"current_context": {"notes": "", "updated": "2026-10-18"}}, [], [])
    assert "Текущий контекст: нет\n" in prompt


def test_system_prompt_keeps_legacy_free_text():
    prompt = build_system_prompt({"servings": "семья из пяти", "cooking_time": "до получаса"}, [], [])
    assert "Обычно готовит на: семья из пяти" in prompt
    assert "Время на готовку: до получаса" in prompt

