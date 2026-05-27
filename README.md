# riot-match-service

Backend-сервис для сбора и чтения статистики матчей League of Legends через Riot API.

## Quick start

```bash
cp .env.example .env
docker compose up --build
```

После запуска:

- API: http://127.0.0.1:8000
- OpenAPI docs: http://127.0.0.1:8000/docs
- Healthcheck: http://127.0.0.1:8000/healthz
