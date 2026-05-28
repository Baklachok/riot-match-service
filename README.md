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

## API

- `GET /healthz`
- `GET /api/v1/players/search?riot_id=G2%20SkewMond%233327`
- `GET /api/v1/players/{puuid}/profile`
- `GET /api/v1/players/{puuid}/matches?limit=20`
- `GET /api/v1/players/{puuid}/champions?limit=20`
- `POST /api/v1/admin/players/refresh`

`POST /api/v1/admin/players/refresh` принимает:

- Riot ID:
  `{"identifier": "G2 SkewMond#3327"}`
- или PUUID:
  `{"identifier": "some-puuid"}`

В ответе есть `summary`:

- `matches_found`
- `new_matches_saved`
- `refreshed_at`

Read endpoint-ы (`GET /api/v1/players/*`) читают только локальную БД и не ходят в Riot API.
