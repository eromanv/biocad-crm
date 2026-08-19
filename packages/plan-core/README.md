# plan-core

Shared domain package used by `apps/backend` and `apps/mcp`:

- models (`Plan`, `Task`)
- CPM schedule from `project_start` + predecessors
- Excel import/export (columns: задача, описание, исполнитель, длительность, предшественники)
- Postgres repository + seed plan
- Alembic migrations (`alembic/`) — backend and MCP run `upgrade head` on startup

```bash
cd packages/plan-core
uv run --extra dev pytest
```

Новая миграция (Postgres должен быть запущен: `docker compose up -d db`):

```bash
cd packages/plan-core
uv run alembic revision --autogenerate -m "describe change"
```

URL берётся из корневого `.env` (`DATABASE_URL` / `POSTGRES_*`). `alembic.ini` при смене кредов править не нужно.
