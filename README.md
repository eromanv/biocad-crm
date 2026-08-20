# Biocad

Система управления проектным планом: интерактивная диаграмма Ганта и чат на естественном языке. Стек — React, FastAPI, MCP-сервис и PostgreSQL. Сроки задач рассчитываются методом критического пути (CPM) от даты начала проекта и списка предшественников; даты старта в Excel не задаются.

## Запуск локально

```bash
cp .env.example .env
docker compose up --build
```

Интерфейс: [http://localhost:5174](http://localhost:5174).

Для чата в `.env` необходимо указать `OPENROUTER_API_KEY`. Без ключа доступны план, импорт и экспорт Excel, а также проверки работоспособности; `POST /api/chat` возвращает код 503.

## Архитектура

```
Браузер
  → FastAPI (backend)  →  OpenRouter (модель с tool-calling)
                       →  MCP          →  plan-core  →  PostgreSQL
```

- Источник данных — PostgreSQL.
- Пакет `packages/plan-core` содержит модели, расчёт CPM, импорт и экспорт Excel и репозиторий; используется backend и MCP.
- Языковая модель не обращается к базе напрямую. Изменения плана выполняются только через инструменты MCP: `list_tasks`, `get_task`, `add_task`, `update_task`, `add_predecessors`, `set_predecessors`, `shift_tasks`, `reassign_tasks`, `delete_task`, `recalc_schedule`.
- Чат держит краткую серверную сессию (HttpOnly cookie, in-memory, TTL 30 минут): последние реплики и `last_task_id`. Это не аудит и не хранилище на несколько процессов.
- Ответы чата передаются потоком SSE: события `{type:"token"}`, `{type:"plan_updated", plan}`, `{type:"error"}`.

### HTTP API

| Метод | Путь | Назначение |
|-------|------|------------|
| GET | `/health` | состояние сервиса, признак настройки OpenRouter |
| GET | `/api/plan` | текущий план |
| POST | `/api/plan/import` | импорт Excel (`file`) |
| GET | `/api/plan/export` | выгрузка Excel |
| POST | `/api/plan/reset` | возврат к начальному набору задач |
| GET | `/api/tasks/{id}` | карточка задачи |
| POST | `/api/chat` | запрос на естественном языке, ответ SSE |

Коллекция запросов: [`bruno/`](bruno/). Пример файла импорта: [`examples/sample-plan.xlsx`](examples/sample-plan.xlsx).

### MCP

Локальный адрес Streamable HTTP: `http://localhost:8101/mcp`. Набор инструментов совпадает с чатом. В производственной конфигурации порт MCP на хост не публикуется.

## Порты (локальный compose)

| Сервис   | Порт на хосте | Порт в контейнере | URL |
|----------|---------------|-------------------|-----|
| frontend | 5174 | 5174 | http://localhost:5174 |
| backend  | 8001 | 8001 | http://localhost:8001/health |
| mcp      | 8101 | 8101 | http://localhost:8101/health |
| postgres | 5433 | 5432 | `localhost:5433` |

В сети Compose база доступна как `db:5432`, MCP — `http://mcp:8101/mcp`. Браузер обращается к backend по `VITE_API_URL` (по умолчанию `http://localhost:8001`).

## Развёртывание

Ветка `develop` запускает проверки (lint, тесты, сборка образов). Развёртывание выполняется только при обновлении ветки `master`.

1. Рекомендуется закрытый GitHub-репозиторий. Файл `.env` в систему контроля версий не включается.
2. На сервере клонировать ветку `master`, скопировать `.env.example` в `.env`. Задать `OPENROUTER_API_KEY`, уникальные `POSTGRES_PASSWORD` и `DATABASE_URL`. Значения из примера предназначены только для локальной разработки. При необходимости указать `CORS_ORIGINS`.
3. В GitHub → Settings → Secrets задать `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_SSH_KEY`, `DEPLOY_PATH`.
4. Ключ OpenRouter хранится только в `.env` на сервере, не в секретах GitHub. Compose читает этот файл при запуске.
5. Обновление `develop` запускает [конвейер CI](.github/workflows/ci.yml) без выкладки. Обновление `master` дополнительно выполняет на сервере `git reset --hard origin/master` и `docker compose -f docker-compose.prod.yml --env-file .env up --build -d`.

В производственной среде наружу открыт только nginx (порт 80): `/` — интерфейс, `/api` и `/health` — backend. PostgreSQL и MCP извне недоступны.

## Структура репозитория

```
apps/backend       FastAPI, агент OpenRouter, SSE
apps/mcp           FastMCP (Streamable HTTP)
apps/frontend      Vite, React
apps/nginx         обратный прокси (production)
packages/plan-core доменная логика и миграции Alembic
uv.lock            фиксация зависимостей Python (uv workspace)
bruno/             коллекция HTTP-запросов
examples/          sample-plan.xlsx
docs/              roadmap
```

## Документация

- [docs/ROADMAP_TO_PRODUCTION.md](docs/ROADMAP_TO_PRODUCTION.md) — ограничения MVP и шаги к промышленной эксплуатации
