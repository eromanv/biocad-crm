# Roadmap to production

Сценарий задания закрыт и уже выкатывается на VPS: `docker-compose.prod.yml`, nginx на порту 80, CI на `develop`, деплой только с `master`. Это демо одного плана, не продукт: нет auth, TLS и изоляции пользователей. Ниже — что сделано сознательно урезанным, какие риски это даёт и в каком порядке закрывать.

## Что уже есть (и почему этого мало)

| Тема | Сейчас | Остаточный риск |
|------|--------|-----------------|
| Периметр сети | В prod наружу только nginx `:80` (`/`, `/api`, `/health`). Postgres и MCP без publish портов | Кто попал в docker-сеть, ходит в MCP без токена |
| CORS | Allowlist из `CORS_ORIGINS`, не `*` | Без HTTPS cookie сессии нельзя пометить `Secure` |
| Лимиты чата | Длина входа, число раундов tool-calling, длина ответа, rate limit по IP (`CHAT_RATE_LIMIT` / 60 с) | Лимит in-memory на процесс, не бюджет OpenRouter. Несколько воркеров / X-Forwarded-For его обходят |
| MCP vs чат | У LLM allowlist тулов; `delete_task` в MCP есть, в чат не отдаётся | Прямой вызов MCP минует промпт |
| Сессия чата | HttpOnly cookie, in-memory, TTL 30 мин, лимит числа сессий | Нет multi-worker, нет аудита, нет resume после рестарта |
| Миграции | Alembic, `upgrade head` на старте backend и MCP | Схема версионируется, данные — нет (бэкапов нет) |
| CI / деплой | lint, pytest (`plan-core`, backend), сборка prod-образов; на `master` — `git reset --hard` и `compose up --build` | Нет тегов образов, нет rollback, секрет OpenRouter живёт в `.env` на хосте |
| Health | `/health` у backend и MCP, healthcheck'и Compose | Это liveness: backend не проверяет БД и MCP в JSON health |

## Сознательные долги MVP

Оставлено специально, чтобы не раздувать демо:

- Один план на всю БД, без `project_id` / tenant.
- Нет login. Кто знает URL — читает и меняет план, жжёт токены модели.
- Календарные дни без выходных и праздников: CPM простой, сроки оптимистичные.
- Нет undo: ошибочный NL-запрос откатывается только reset/повторным Excel.
- HTTP без TLS (`CHAT_COOKIE_SECURE=false`) — иначе чат на голом HTTP не держит cookie.
- Деплой пересобирает образы на сервере, а не тянет неизменяемый tag.

## Ограничения, которые надо закрыть до боя

| Область | Сейчас | Риск |
|---------|--------|------|
| Auth / роли | Нет | Любой с URL меняет план и дергает чат |
| Мультипользователи | Одна таблица плана | Гонки, взаимные перезаписи |
| Аудит MCP/LLM | Нет лога tool-calls | Не восстановить, кто и каким промптом сдвинул задачи |
| Секреты | `.env` на хосте | Утечка `OPENROUTER_API_KEY` = деньги + доступ к модели |
| Prompt injection / XSS | Текст чата и поля задач без политики | Вредоносный Excel или сообщение → неожиданные tool-calls |
| Бюджет LLM | Нет cap в долларах, только RPS-like лимит | Счёт OpenRouter не ограничен сверху |
| Бэкапы Postgres | Volume без политики | Потеря единственного плана |
| Наблюдаемость | Только `/health` | Нет latency LLM, обрывов SSE, 5xx |
| Календарь | Без выходных | Нереалистичные сроки |
| Undo | Нет | Ошибочный чат необратим |
| TLS | Нет | Перехват сессии и ключей на сети |

## Порядок закрытия

### 1. Периметр и секреты

- TLS (Caddy/nginx) и `CHAT_COOKIE_SECURE=true`.
- Секреты через secret store / compose secrets; ротация `OPENROUTER_API_KEY`.
- Bearer (или mTLS) на MCP; даже во внутренней сети не анонимно.
- CORS только origin прод-UI (уже allowlist — не расширять до `*`).

### 2. Идентичность и доступ

- Login (OIDC или session cookie); роли viewer / editor / admin.
- Shared password за reverse proxy — минимум для закрытого пилота.
- Планы по `project_id` / tenant, row-level доступ.

### 3. Данные

- Бэкап volume Postgres и restore-drill.
- Оптимистичная версия плана или soft-lock на время чата/import.
- Аудит: кто вызвал tool, какой prompt, diff задач.
- Горизонталь: сессии чата не in-memory, а Redis/БД.

### 4. LLM: стоимость и safety

- Budget cap / alert в OpenRouter; rate limit не только in-process.
- Подтверждение деструктивных действий (`delete_task`, полная замена плана).
- Санитизация полей задач и сообщений в system prompt; отказ исполнять «системные» инструкции из Excel.
- `delete_task` либо убрать с MCP, либо закрыть тем же auth, что и остальной периметр.

### 5. Продукт

- История чата в БД, undo последних N мутаций.
- Календарь с выходными / праздниками.
- Конфликт: показать diff при параллельном редактировании.

### 6. Наблюдаемость и деплой

- Structured logs, tracing (OpenTelemetry), отдельно ошибки LLM и обрывы SSE.
- Readiness: БД доступна, MCP отвечает, не только процесс жив.
- Образы с тегом (`:0.2.3`), деплой pull tag, документированный rollback на предыдущий tag. Сейчас `git reset --hard origin/master` + rebuild — для пилота терпимо, для боя нет.

### 7. Compliance (если появятся ПДн)

- Имена исполнителей, DPA с провайдером LLM, регион данных.

## Критерии «можно отдать пилоту на VPS»

- [x] MCP не проксируется nginx наружу (осталось закрыть токеном внутри сети)
- [x] CORS allowlist, не `*`
- [x] Лимит частоты чата (не замена бюджету)
- [ ] Auth хотя бы basic / shared password за reverse proxy
- [ ] HTTPS + Secure cookie
- [ ] Бэкап volume Postgres и проверенный restore
- [ ] Бюджетный лимит OpenRouter
- [ ] Rollback образом с тегом, не только `git reset --hard`
- [ ] Аудит mutating tool-calls
