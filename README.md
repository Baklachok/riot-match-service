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

## Match Sync Defaults

- Для sync матчей используется Match-V5 и берутся последние `N` матчей игрока.
- По умолчанию: `RIOT_MATCH_SYNC_COUNT=30` и `RIOT_MATCH_SYNC_QUEUE=420` (SoloQ).
- Рекомендуемый диапазон для `N`: 20-50.
- Детали запрашиваются только для отсутствующих локально `match_id`.
