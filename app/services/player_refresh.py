from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.player_refresh_mapper import (
    build_match_record,
    build_player_match_record,
    build_refresh_result,
    extract_player_participant,
    normalize_error_message,
    normalize_match_sync_error,
    normalize_ranked_entries,
    parse_match_from_raw,
)
from app.services.player_refresh_models import (
    MatchSyncSummary,
    PlayerRefreshResult,
    RefreshedPlayer,
    RefreshedRankedEntry,
)
from app.services.player_refresh_repository import PlayerRefreshRepository
from app.services.riot.client import RiotClient
from app.services.riot.errors import RiotClientError
from app.services.riot.schemas import RiotAccount, RiotSummoner

__all__ = (
    "MatchSyncSummary",
    "PlayerRefreshResult",
    "PlayerRefreshService",
    "RefreshedPlayer",
    "RefreshedRankedEntry",
)


@dataclass(frozen=True)
class _MatchRecordsBatch:
    match_records: list[dict[str, object]]
    player_match_records: list[dict[str, object]]
    failed_match_ids: list[str]


@dataclass(frozen=True)
class _MatchSyncResult:
    summary: MatchSyncSummary
    match_records: list[dict[str, object]]
    player_match_records: list[dict[str, object]]


class _MatchSyncCollector:
    def __init__(
        self,
        *,
        riot_client: RiotClient,
        repository: PlayerRefreshRepository,
        match_sync_count: int,
        match_sync_queue: int,
    ) -> None:
        self._riot_client = riot_client
        self._repository = repository
        self._match_sync_count = max(1, match_sync_count)
        self._match_sync_queue = match_sync_queue

    async def collect(self, *, player_puuid: str) -> _MatchSyncResult:
        match_ids, fetch_failed_ids = await self._fetch_match_ids(player_puuid=player_puuid)
        if not match_ids:
            return _MatchSyncResult(
                summary=MatchSyncSummary(
                    queue=self._match_sync_queue,
                    requested_count=self._match_sync_count,
                    match_ids_received=0,
                    new_matches_saved=0,
                    existing_matches_skipped=0,
                    player_matches_upserted=0,
                    backfilled_from_raw=0,
                    failed_matches=len(fetch_failed_ids),
                    failed_match_ids=fetch_failed_ids,
                ),
                match_records=[],
                player_match_records=[],
            )

        existing_matches_raw = await self._repository.get_existing_matches_raw(match_ids)
        existing_player_match_ids = await self._repository.get_existing_player_match_ids(
            player_puuid=player_puuid,
            match_ids=match_ids,
        )

        missing_match_ids = [
            match_id for match_id in match_ids if match_id not in existing_matches_raw
        ]
        backfill_match_ids = [
            match_id
            for match_id in match_ids
            if match_id in existing_matches_raw and match_id not in existing_player_match_ids
        ]

        new_batch = await self._collect_missing_matches(
            player_puuid=player_puuid,
            missing_match_ids=missing_match_ids,
        )
        backfill_batch = self._collect_backfill_matches(
            player_puuid=player_puuid,
            backfill_match_ids=backfill_match_ids,
            existing_matches_raw=existing_matches_raw,
        )

        failed_match_ids = [
            *fetch_failed_ids,
            *new_batch.failed_match_ids,
            *backfill_batch.failed_match_ids,
        ]
        player_match_records = [
            *new_batch.player_match_records,
            *backfill_batch.player_match_records,
        ]

        return _MatchSyncResult(
            summary=MatchSyncSummary(
                queue=self._match_sync_queue,
                requested_count=self._match_sync_count,
                match_ids_received=len(match_ids),
                new_matches_saved=len(new_batch.match_records),
                existing_matches_skipped=len(existing_matches_raw),
                player_matches_upserted=len(player_match_records),
                backfilled_from_raw=len(backfill_batch.player_match_records),
                failed_matches=len(failed_match_ids),
                failed_match_ids=failed_match_ids,
            ),
            match_records=new_batch.match_records,
            player_match_records=player_match_records,
        )

    async def _fetch_match_ids(self, *, player_puuid: str) -> tuple[list[str], list[str]]:
        try:
            match_ids = await self._riot_client.get_match_ids_by_puuid(
                player_puuid,
                count=self._match_sync_count,
                queue=self._match_sync_queue,
            )
        except RiotClientError:
            return [], ["match-ids-fetch"]

        unique_match_ids: list[str] = []
        seen_match_ids: set[str] = set()
        for match_id in match_ids:
            if match_id in seen_match_ids:
                continue
            seen_match_ids.add(match_id)
            unique_match_ids.append(match_id)
        return unique_match_ids, []

    async def _collect_missing_matches(
        self,
        *,
        player_puuid: str,
        missing_match_ids: list[str],
    ) -> _MatchRecordsBatch:
        match_records: list[dict[str, object]] = []
        player_match_records: list[dict[str, object]] = []
        failed_match_ids: list[str] = []

        for match_id in missing_match_ids:
            try:
                riot_match = await self._riot_client.get_match(match_id)
            except RiotClientError:
                failed_match_ids.append(match_id)
                continue

            participant = extract_player_participant(riot_match, player_puuid)
            if participant is None:
                failed_match_ids.append(match_id)
                continue

            try:
                match_record = build_match_record(riot_match)
            except ValueError:
                failed_match_ids.append(match_id)
                continue

            match_records.append(match_record)
            player_match_records.append(
                build_player_match_record(
                    player_puuid=player_puuid,
                    match_id=match_id,
                    participant=participant,
                )
            )

        return _MatchRecordsBatch(
            match_records=match_records,
            player_match_records=player_match_records,
            failed_match_ids=failed_match_ids,
        )

    def _collect_backfill_matches(
        self,
        *,
        player_puuid: str,
        backfill_match_ids: list[str],
        existing_matches_raw: dict[str, dict[str, Any]],
    ) -> _MatchRecordsBatch:
        player_match_records: list[dict[str, object]] = []
        failed_match_ids: list[str] = []

        for match_id in backfill_match_ids:
            raw_json = existing_matches_raw.get(match_id)
            if raw_json is None:
                failed_match_ids.append(match_id)
                continue

            try:
                riot_match = parse_match_from_raw(raw_json)
            except Exception:
                failed_match_ids.append(match_id)
                continue

            participant = extract_player_participant(riot_match, player_puuid)
            if participant is None:
                failed_match_ids.append(match_id)
                continue

            player_match_records.append(
                build_player_match_record(
                    player_puuid=player_puuid,
                    match_id=match_id,
                    participant=participant,
                )
            )

        return _MatchRecordsBatch(
            match_records=[],
            player_match_records=player_match_records,
            failed_match_ids=failed_match_ids,
        )


class PlayerRefreshService:
    def __init__(
        self,
        *,
        session: AsyncSession,
        riot_client: RiotClient,
        platform: str,
        match_sync_count: int = 30,
        match_sync_queue: int = 420,
    ) -> None:
        self._session = session
        self._riot_client = riot_client
        self._repository = PlayerRefreshRepository(session=session, platform=platform)
        self._platform = platform.strip().lower()
        self._match_sync = _MatchSyncCollector(
            riot_client=riot_client,
            repository=self._repository,
            match_sync_count=match_sync_count,
            match_sync_queue=match_sync_queue,
        )

    async def refresh_player(self, *, game_name: str, tag_line: str) -> PlayerRefreshResult:
        account = await self._riot_client.get_account_by_riot_id(
            game_name=game_name,
            tag_line=tag_line,
        )

        summoner: RiotSummoner | None = None
        try:
            summoner = await self._riot_client.get_summoner_by_puuid(account.puuid)
            riot_ranked_entries = await self._riot_client.get_ranked_entries_by_puuid(account.puuid)
        except RiotClientError as exc:
            await self._persist_failed_refresh(
                account=account,
                summoner=summoner,
                refreshed_at=datetime.now(UTC),
                error_message=normalize_error_message(exc),
            )
            raise

        refreshed_at = datetime.now(UTC)
        ranked_entries = normalize_ranked_entries(riot_ranked_entries)
        match_sync = await self._match_sync.collect(player_puuid=account.puuid)
        refresh_status = "partial_success" if match_sync.summary.failed_matches > 0 else "success"
        refresh_error = (
            normalize_match_sync_error(match_sync.summary.failed_match_ids)
            if match_sync.summary.failed_matches > 0
            else None
        )

        await self._reset_session_transaction()
        async with self._session.begin():
            await self._repository.upsert_player(
                account=account,
                summoner=summoner,
                refreshed_at=refreshed_at,
                refresh_status=refresh_status,
                refresh_error=refresh_error,
                update_profile_fields=True,
            )
            await self._repository.sync_ranked_entries(
                player_puuid=account.puuid,
                ranked_entries=ranked_entries,
                refreshed_at=refreshed_at,
            )
            await self._repository.upsert_matches(match_sync.match_records)
            await self._repository.upsert_player_matches(match_sync.player_match_records)

        return build_refresh_result(
            account=account,
            summoner=summoner,
            platform=self._platform,
            refreshed_at=refreshed_at,
            refresh_status=refresh_status,
            refresh_error=refresh_error,
            ranked_entries=ranked_entries,
            match_sync=match_sync.summary,
        )

    async def _persist_failed_refresh(
        self,
        *,
        account: RiotAccount,
        summoner: RiotSummoner | None,
        refreshed_at: datetime,
        error_message: str,
    ) -> None:
        await self._reset_session_transaction()
        async with self._session.begin():
            await self._repository.upsert_player(
                account=account,
                summoner=summoner,
                refreshed_at=refreshed_at,
                refresh_status="failed",
                refresh_error=error_message,
                update_profile_fields=summoner is not None,
            )

    async def _reset_session_transaction(self) -> None:
        if self._session.in_transaction():
            await self._session.rollback()
