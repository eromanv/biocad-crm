# Roadmap to production

MVP намеренно урезан: один пользователь, локальный compose, без auth. Ниже — пробелы и порядок закрытия перед выкладкой на VPS / прод.

## Текущие ограничения MVP

| Область | Сейчас | Риск |
|---------|--------|------|
| Auth / роли | Нет | Любой с URL может читать/менять план и дергать чат |
| Мультипользователи | Одна БД-таблица плана | Гонки, взаимные перезаписи |
| Сессии чата | In-memory / без истории на сервере | Нет аудита диалога, нет resume |
| Аудит MCP/LLM | Нет лога tool-calls | Сложно расследовать «кто сдвинул задачи» |
| Секреты | `.env` на хосте | Утечка ключа OpenRouter = деньги + доступ к модели |
| MCP | Без токена (удобно для демо) | Любой в сети может вызывать тулы |
| Лимиты LLM | Нет rate limit / budget | Стоимость и DoS через чат |
| XSS / prompt injection | Текст чата и поля задач без жёсткой политики | Вредоносный Excel/чат → неожиданные tool-calls |
| Бэкапы Postgres | Volume без политики | Потеря плана |
| Наблюдаемость | Только `/health` | Нет метрик latency/ошибок LLM |
| Календарь | Календарные дни без выходных | Нереалистичные сроки |
| Undo | Нет | Ошибочный NL-запрос необратим (кроме reset/Excel) |

## Порядок закрытия

### 1. Секреты и периметр

- Секреты только через secret store / compose secrets; ротация `OPENROUTER_API_KEY`.
- Auth на MCP (Bearer / mTLS); отключить анонимный `/mcp` снаружи.
- CORS строго по origin прод-фронта (уже не `*`).

### 2. Идентичность и доступ

- Login (OIDC / session cookie); роли: viewer / editor / admin.
- Разделение планов по `project_id` / tenant; row-level доступ.

### 3. Надёжность данных

- ~~Миграции (Alembic)~~ — `packages/plan-core/alembic`, upgrade на старте backend/MCP. Осталось: бэкапы Postgres, restore-drill.
- Оптимистичные версии плана или soft-lock при чате/import.
- Аудит: кто вызвал tool, какой prompt, diff задач.

### 4. LLM safety & cost

- Rate limits, max tokens, budget alerts.
- Allowlist тулов; подтверждение деструктивных действий (delete / full replace).
- Санитизация пользовательского ввода и описаний задач в system prompt; отказ от исполнения «системных» инструкций из Excel.

### 5. UX / продукт

- История чата в БД, undo последних N мутаций.
- Календарь с выходными / праздниками.
- Конфликты: показать diff при параллельном редактировании.

### 6. Наблюдаемость и деплой

- Structured logs, tracing (OpenTelemetry), дашборд ошибок 5xx / SSE disconnect.
- Health + readiness (БД + MCP reachable).
- VPS: тот же compose + reverse proxy (Caddy/Nginx) на 80/443, TLS; внутренние порты без смены схемы (8001/8101/5433 за proxy).
- ~~CI: pytest plan-core, ruff, tsc, build prod-образов, деплой по SSH~~ — [`.github/workflows/ci.yml`](../.github/workflows/ci.yml).

### 7. Compliance (по необходимости)

- Хранение ПДн исполнителей, DPA с LLM-провайдером, регион данных.

## Критерии «можно на VPS для пилота»

- [ ] Auth хотя бы basic / single shared password за reverse proxy
- [ ] MCP не торчит в интернет без токена
- [ ] Бэкап volume Postgres
- [ ] Бюджет/лимит OpenRouter
- [ ] CORS + HTTPS
- [ ] Документированный rollback (`docker compose` предыдущего image tag)
