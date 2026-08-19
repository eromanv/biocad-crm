# Bruno — Biocad

One collection for all REST endpoints (do not create another).

Environment: `environments/local.bru` (`backendUrl`, `mcpUrl`).

## Health

- `GET {{backendUrl}}/health`
- `GET {{mcpUrl}}/health`

## Plan API

- `GET {{backendUrl}}/api/plan`
- `POST {{backendUrl}}/api/plan/import` (multipart `file`)
- `GET {{backendUrl}}/api/plan/export`
- `POST {{backendUrl}}/api/plan/reset`
- `GET {{backendUrl}}/api/tasks/{id}`
- `POST {{backendUrl}}/api/chat` — SSE (`token`, `plan_updated`, `error`); needs `OPENROUTER_API_KEY` and `CHAT_ENABLED=true`
  - Guardrails: max input length, 3 tool rounds, rate limit (default 10/min), no `delete_task` from chat
