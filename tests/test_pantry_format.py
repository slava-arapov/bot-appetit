from agent.chef import SYSTEM_PROMPT_TEMPLATE, _format_pantry, build_system_prompt


def test_prompt_marks_shopping_list_items_as_missing():
    text = _format_pantry(
        [
            {"name": "Сыр", "status": "have", "added_date": "2026-10-01"},
            {"name": "Молоко", "status": "to_buy", "quantity": "1 л"},
        ]
    )
    assert "Молоко (нужно купить, 1 л)" in text
    assert "to_buy" not in text


def test_prompt_documents_all_pantry_statuses():
    assert '"status": "have|low|to_buy|out"' in SYSTEM_PROMPT_TEMPLATE


def test_prompt_asks_about_shopping_list_instead_of_adding_it():
    prompt = build_system_prompt({}, [], [])
    # закончилось → out + вопрос про покупки; согласие пользователя → to_buy
    assert "спроси" in prompt and "список покупок" in prompt
    assert 'status "out"' in prompt
    assert 'status "to_buy"' in prompt


def test_prompt_treats_shopping_list_as_missing_for_recipes():
    prompt = build_system_prompt({}, [], [])
    assert "отсутствующими" in prompt
