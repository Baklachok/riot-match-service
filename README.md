# riot-match-service

Backend-сервис для сбора и чтения статистики матчей League of Legends через Riot API.

## Quick start

1. Создай `.env`:

```bash
cp .env.example .env
```

2. Укажи ключ Riot в `.env`:

```env
RIOT_API_KEY=your_riot_api_key
```

3. Подними сервис:

```bash
docker compose up
```

После запуска:

- API: http://127.0.0.1:8000
- OpenAPI docs: http://127.0.0.1:8000/docs
- Healthcheck: http://127.0.0.1:8000/healthz

## Стратегия обновления данных

- Глубина истории задаётся `RIOT_MATCH_SYNC_COUNT` (по умолчанию `30`, рекомендованный диапазон `20-50`).
- Очередь для sync по умолчанию `RIOT_MATCH_SYNC_QUEUE=420` (SoloQ).
- Перед запросом деталей матчей сервис проверяет локальную БД и запрашивает в Riot только отсутствующие `match_id`.
- Дедупликация на уровне БД: `matches` upsert по `match_id`, `player_matches` upsert по паре `(player_puuid, match_id)`.
- Кэширование/TTL: используется soft TTL через локальную БД и `last_refreshed_at`. Жёсткого авто-TTL в коде нет; обновление выполняется через `POST /api/v1/admin/players/refresh`.
- Read endpoint-ы не ходят в Riot, потому что отдают снимок из локальной БД: это снижает latency, не упирается в лимиты Riot на чтении и не ломает пользовательские запросы при проблемах внешнего API.

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

## Примеры curl

Проверка health:

```
curl -X 'GET' \
  'http://127.0.0.1:8000/healthz' \
  -H 'accept: application/json'
```

Refresh по Riot ID:

```
curl -X 'POST' \
  'http://127.0.0.1:8000/api/v1/admin/players/refresh' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{"identifier":"G2 SkewMond#3327"}'
```

Refresh по PUUID:

```
curl -X 'POST' \
  'http://127.0.0.1:8000/api/v1/admin/players/refresh' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{"identifier":"<PUUID>"}'
```

Поиск игрока по Riot ID:

```
curl -X 'GET' \
  'http://127.0.0.1:8000/api/v1/players/search?riot_id=G2%20SkewMond%233327' \
  -H 'accept: application/json'
```

Профиль игрока:

```
curl -X 'GET' \
  'http://127.0.0.1:8000/api/v1/players/<PUUID>/profile' \
  -H 'accept: application/json'
```

Последние матчи:

```
curl -X 'GET' \
  'http://127.0.0.1:8000/api/v1/players/<PUUID>/matches?limit=20' \
  -H 'accept: application/json'
```

Агрегаты по чемпионам:

```
curl -X 'GET' \
  'http://127.0.0.1:8000/api/v1/players/<PUUID>/champions?limit=20' \
  -H 'accept: application/json'
```

Пример ошибки (невалидный identifier):

```
curl -X 'POST' \
  'http://127.0.0.1:8000/api/v1/admin/players/refresh' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{"identifier":"bad#"}'
```
