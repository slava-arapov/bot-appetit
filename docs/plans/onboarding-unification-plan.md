# План реализации: единый формат порций, времени и техники

Дизайн: `docs/onboarding-unification.md`. Порядок — от чистой логики к интеграции; каждый шаг начинается с теста (TDD) и заканчивается зелёным `pytest` / `npm test` в `webapp/`. Один шаг — один коммит.

## Шаг 1. Константы и `normalize_cooking_time`

- [ ] `tests/test_settings.py`: параметризованный тест `normalize_cooking_time` — все реальные значения из прода («до 30 минут», «30 мин», «Не важно», «Не более 1 часа», «1 час», «Как можно меньше», «до часа», «60 минут», «1 ч», «40 минут» → `None`, «полтора часа» → `None`); заодно проверка, что `normalize_servings` не изменилась («1, иногда 2» → 1, «на 1» → 1).
- [ ] `memory/store.py`: расширить `normalize_cooking_time` (часы → минуты, «до часа», «1 ч»); число принимается, только если это пресет.
- [ ] `config.py`: `EQUIPMENT_OPTIONS` (те же 12 пунктов, что сейчас в `DEFAULT_EQUIPMENT`).
- Готово, когда: новые тесты зелёные, старые `test_settings.py` не сломаны.

## Шаг 2. Типизированные шаги и `StepView`

- [ ] Новый `tests/test_onboarding.py` (фикстуры БД из `conftest.py`).
- [ ] `agent/chef.py`: `Step` + список `ONBOARDING_STEPS`, убрать `ONBOARDING_QUESTIONS`/`ONBOARDING_FIELDS`; тексты вопросов не меняются, кроме подсказок в скобках у шагов с кнопками.
- [ ] `StepView(text, keyboard)`, где `keyboard` — `InlineKeyboardMarkup | None`; клавиатуры собираются в `bot/keyboards.py` (чистые функции: `servings_keyboard()`, `time_keyboard()`, `equipment_keyboard(selected: set[int])`).
- [ ] `run_onboarding(user_id, user_message) -> StepView`; ответ на `choice` проходит через `normalize_*` и пишется пресетом; нераспознанный возвращает тот же шаг с подсказкой «Выбери вариант кнопкой 👇» без смены `onboarding_step`.
- [ ] `current_onboarding_question(user_id) -> StepView`.
- [ ] Новая функция для колбэков: `apply_onboarding_choice(user_id, step_field, value) -> StepView | None` (None — шаг устарел). Проверка устаревания: поле шага совпадает с `ONBOARDING_STEPS[onboarding_step - 1].field` и онбординг не завершён.
- Тесты: нажатие пишет пресет; валидный текст принимается; невалидный не двигает шаг; устаревший колбэк ничего не пишет; двойной вызов идемпотентен; шаг `text` работает как раньше; в конце `onboarding_done = True`.
- Готово, когда: всё выше зелёное, `bot/handlers.py` пока не трогаем (старые вызовы временно используют `view.text`).

## Шаг 3. Хендлеры и колбэки

- [ ] `bot/handlers.py`: везде, где вызывается `run_onboarding`/`current_onboarding_question` (`_show_onboarding_question`, обработка текста, одобрение заявки), отправлять `view.text` с `reply_markup=view.keyboard`.
- [ ] `handle_onboarding_callback` (`pattern=r"^onb:"`): гейт `_require_approved`; разбор `onb:servings:<n>`, `onb:time:<preset>`, `onb:eq:<idx|other|done>`; редактирование сообщения в «✓ …» без клавиатуры, `BadRequest` → новое сообщение; устаревший колбэк → `query.answer("Этот вопрос уже неактуален")`.
- [ ] Техника: `context.user_data["onb_equipment"]` (набор индексов), переключение перерисовывает клавиатуру через `edit_message_reply_markup`; «Другое» ставит `user_data["onb_awaiting_custom"]`, следующий текст добавляется к выбору (`normalize_tag`) и клавиатура рисуется заново; «Готово» пишет итог в `equipment`, сбрасывает состояние.
- [ ] Текст на шаге техники без флага трактуется как «Другое».
- [ ] `/start` сбрасывает `onb_*` в `user_data`.
- [ ] `main.py`: `app.add_handler(CallbackQueryHandler(handle_onboarding_callback, pattern=r"^onb:"))`.
- Тесты (`tests/test_onboarding_handlers.py`, моки `Update`/`CallbackQuery`): переключение и «Готово», «Другое», потеря `user_data`, неподтверждённый пользователь, `BadRequest` при редактировании.
- Готово, когда: ручная проверка с тестовым ботом проходит всю анкету кнопками и текстом.

## Шаг 4. API и Mini App

- [ ] `tests/test_api.py`: `GET /api/profile` содержит `equipment_options` и сохраняет прежние ключи тегов.
- [ ] `webapp_api/routes.py`: добавить `equipment_options` в ответ профиля (из `config.EQUIPMENT_OPTIONS`).
- [ ] `webapp/src/api/client.ts`: `ProfileResponse = Record<TagKind, Tag[]> & { equipment_options: string[] }`.
- [ ] `webapp/src/composables/useProfile.ts`: отдельный `equipmentOptions = ref<string[]>([])`; `tags` собирается без `equipment_options`.
- [ ] `EquipmentChecklist.vue`: проп `options: string[]`, вместо `DEFAULT_EQUIPMENT`; `ProfileView.vue` передаёт его. Пока `options` пуст (загрузка), чек-лист не рисуется.
- [ ] Удалить `DEFAULT_EQUIPMENT` из `utils/profile.ts`; обновить `EquipmentChecklist.test.ts`, `useProfile.test.ts`, `ProfileView`-тесты.
- Готово, когда: `pytest`, `npm test`, `npm run lint`, `npm run build` зелёные; в dev-режиме Mini App показывает чек-лист из API.

## Шаг 5. Скрипт миграции

- [ ] `tests/test_migrate_normalize_settings.py`: временная БД с значениями из прода; dry-run ничего не меняет; `--apply` создаёт `*.bak-<дата>` и переписывает только однозначные значения; второй запуск — ноль изменений; нераспознанные не тронуты и перечислены в отчёте.
- [ ] `migrate_normalize_settings.py` (по образцу `migrate_to_sqlite.py`): аргументы `--db` (по умолчанию `data/bot.db`) и `--apply`; использует `normalize_servings`/`normalize_cooking_time`.
- [ ] Запустить dry-run на `bot-prod.db`, показать отчёт пользователю до любого `--apply`. Боевую БД на VPS мигрирует пользователь вручную после деплоя.
- Готово, когда: отчёт dry-run по `bot-prod.db` совпадает с ожиданием из дизайна («1 час»/«Не более 1 часа» → `60`; «Как можно меньше» нераспознано).

## Шаг 6. Документация и финальная проверка

- [ ] `CLAUDE.md`: раздел «Онбординг» (типы шагов, кнопки, `StepView`, `onb:`-колбэки), таблица роутинга `CallbackQueryHandler`, строка про `EQUIPMENT_OPTIONS` в Mini App, упоминание скрипта миграции.
- [ ] Полный прогон: `pytest`, `npm test`, `npm run lint`, `npm run build`; ручной сценарий — новый пользователь проходит анкету кнопками, затем проверяет те же значения в Mini App.
- [ ] Ревью диффа (`/code-review`) перед слиянием.

## Порядок выкладки

1. Деплой кода (бот + Mini App вместе, API вне флага).
2. На VPS: бэкап `bot.db` (делает скрипт), `migrate_normalize_settings.py` dry-run, затем `--apply`.
3. Проверить Mini App у пары существующих пользователей.

## Замечания

- В `git status` есть чужие изменения (`brag-output/`, `bot-prod.db`, `webapp/.../node_modules`): в коммиты плана не попадают, добавляем файлы явно по именам.
- `bot-prod.db` читается только в режиме `mode=ro`.
