from dataclasses import dataclass
from typing import Any

from app.services.player_refresh_mapper import (
    build_match_record,
    build_player_match_record,
    extract_player_participant,
)
from app.services.player_refresh_models import MatchSyncSummary
from app.services.player_refresh_repository import PlayerRefreshRepository
from app.services.riot import RiotClient, RiotClientError
from app.services.riot.models import RiotMatch

_MATCH_IDS_FETCH_FAILED_MARKER = "match-ids-fetch"


@dataclass(frozen=True)
class MatchSyncCollection:
    summary: MatchSyncSummary
    match_records: list[dict[str, object]]
    player_match_records: list[dict[str, object]]


@dataclass(frozen=True)
class _MatchSyncPlan:
    match_ids: list[str]
    existing_matches_raw: dict[str, dict[str, Any]]
    missing_match_ids: list[str]
    backfill_match_ids: list[str]


@dataclass(frozen=True)
class _CollectedRecords:
    match_records: list[dict[str, object]]
    player_match_records: list[dict[str, object]]
    failed_match_ids: list[str]
    backfilled_from_raw: int


@dataclass(frozen=True)
class _RecordsBatch:
    match_records: list[dict[str, object]]
    player_match_records: list[dict[str, object]]
    failed_match_ids: list[str]


class PlayerMatchSyncCollector:
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

    async def collect(self, *, player_puuid: str) -> MatchSyncCollection:
        match_ids, fetch_failed_ids = await self._fetch_match_ids(player_puuid=player_puuid)
        if not match_ids:
            return self._empty_collection(fetch_failed_ids)

        plan = await self._build_sync_plan(
            player_puuid=player_puuid,
            match_ids=match_ids,
        )
        records = await self._collect_records(player_puuid=player_puuid, plan=plan)
        failed_match_ids = [*fetch_failed_ids, *records.failed_match_ids]
        summary = self._build_summary(
            plan=plan,
            records=records,
            failed_match_ids=failed_match_ids,
        )
        return MatchSyncCollection(
            summary=summary,
            match_records=records.match_records,
            player_match_records=records.player_match_records,
        )

    async def _build_sync_plan(
        self,
        *,
        player_puuid: str,
        match_ids: list[str],
    ) -> _MatchSyncPlan:
        existing_matches_raw = await self._repository.get_existing_matches_raw(match_ids)
        existing_player_match_ids = await self._repository.get_existing_player_match_ids(
            player_puuid=player_puuid,
            match_ids=match_ids,
        )
        missing_match_ids, backfill_match_ids = self._partition_match_ids(
            match_ids=match_ids,
            existing_matches_raw=existing_matches_raw,
            existing_player_match_ids=existing_player_match_ids,
        )
        return _MatchSyncPlan(
            match_ids=match_ids,
            existing_matches_raw=existing_matches_raw,
            missing_match_ids=missing_match_ids,
            backfill_match_ids=backfill_match_ids,
        )

    async def _collect_records(
        self,
        *,
        player_puuid: str,
        plan: _MatchSyncPlan,
    ) -> _CollectedRecords:
        missing_batch = await self._collect_missing_match_records(
            player_puuid=player_puuid,
            missing_match_ids=plan.missing_match_ids,
        )
        backfill_batch = self._collect_backfilled_player_matches(
            player_puuid=player_puuid,
            backfill_match_ids=plan.backfill_match_ids,
            existing_matches_raw=plan.existing_matches_raw,
        )
        player_match_records = [
            *missing_batch.player_match_records,
            *backfill_batch.player_match_records,
        ]
        failed_match_ids = [*missing_batch.failed_match_ids, *backfill_batch.failed_match_ids]
        return _CollectedRecords(
            match_records=missing_batch.match_records,
            player_match_records=player_match_records,
            failed_match_ids=failed_match_ids,
            backfilled_from_raw=len(backfill_batch.player_match_records),
        )

    async def _fetch_match_ids(self, *, player_puuid: str) -> tuple[list[str], list[str]]:
        try:
            match_ids = await self._riot_client.get_match_ids_by_puuid(
                player_puuid,
                count=self._match_sync_count,
                queue=self._match_sync_queue,
            )
        except RiotClientError:
            return [], [_MATCH_IDS_FETCH_FAILED_MARKER]
        return self._unique_match_ids(match_ids), []

    async def _collect_missing_match_records(
        self,
        *,
        player_puuid: str,
        missing_match_ids: list[str],
    ) -> _RecordsBatch:
        match_records: list[dict[str, object]] = []
        player_match_records: list[dict[str, object]] = []
        failed_match_ids: list[str] = []

        for match_id in missing_match_ids:
            riot_match = await self._fetch_match(match_id=match_id)
            if riot_match is None:
                failed_match_ids.append(match_id)
                continue

            try:
                match_record = build_match_record(riot_match)
            except ValueError:
                failed_match_ids.append(match_id)
                continue

            player_match_record = self._build_player_match_record(
                riot_match=riot_match,
                player_puuid=player_puuid,
                match_id=match_id,
            )
            if player_match_record is None:
                failed_match_ids.append(match_id)
                continue

            match_records.append(match_record)
            player_match_records.append(player_match_record)
        return _RecordsBatch(
            match_records=match_records,
            player_match_records=player_match_records,
            failed_match_ids=failed_match_ids,
        )

    def _collect_backfilled_player_matches(
        self,
        *,
        player_puuid: str,
        backfill_match_ids: list[str],
        existing_matches_raw: dict[str, dict[str, Any]],
    ) -> _RecordsBatch:
        player_match_records: list[dict[str, object]] = []
        failed_match_ids: list[str] = []

        for match_id in backfill_match_ids:
            riot_match = self._parse_backfill_match(
                match_id=match_id,
                existing_matches_raw=existing_matches_raw,
            )
            if riot_match is None:
                failed_match_ids.append(match_id)
                continue

            player_match_record = self._build_player_match_record(
                riot_match=riot_match,
                player_puuid=player_puuid,
                match_id=match_id,
            )
            if player_match_record is None:
                failed_match_ids.append(match_id)
                continue

            player_match_records.append(player_match_record)
        return _RecordsBatch(
            match_records=[],
            player_match_records=player_match_records,
            failed_match_ids=failed_match_ids,
        )

    async def _fetch_match(self, *, match_id: str) -> RiotMatch | None:
        try:
            return await self._riot_client.get_match(match_id)
        except RiotClientError:
            return None

    def _parse_backfill_match(
        self,
        *,
        match_id: str,
        existing_matches_raw: dict[str, dict[str, Any]],
    ) -> RiotMatch | None:
        raw_json = existing_matches_raw.get(match_id)
        if raw_json is None:
            return None
        try:
            return RiotMatch.from_payload(raw_json)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _build_player_match_record(
        *,
        riot_match: RiotMatch,
        player_puuid: str,
        match_id: str,
    ) -> dict[str, object] | None:
        participant = extract_player_participant(riot_match, player_puuid)
        if participant is None:
            return None
        return build_player_match_record(
            player_puuid=player_puuid,
            match_id=match_id,
            participant=participant,
        )

    @staticmethod
    def _unique_match_ids(match_ids: list[str]) -> list[str]:
        return list(dict.fromkeys(match_ids))

    @staticmethod
    def _partition_match_ids(
        *,
        match_ids: list[str],
        existing_matches_raw: dict[str, dict[str, Any]],
        existing_player_match_ids: set[str],
    ) -> tuple[list[str], list[str]]:
        missing_match_ids: list[str] = []
        backfill_match_ids: list[str] = []
        for match_id in match_ids:
            if match_id not in existing_matches_raw:
                missing_match_ids.append(match_id)
                continue
            if match_id not in existing_player_match_ids:
                backfill_match_ids.append(match_id)
        return missing_match_ids, backfill_match_ids

    def _build_summary(
        self,
        *,
        plan: _MatchSyncPlan,
        records: _CollectedRecords,
        failed_match_ids: list[str],
    ) -> MatchSyncSummary:
        return MatchSyncSummary(
            queue=self._match_sync_queue,
            requested_count=self._match_sync_count,
            match_ids_received=len(plan.match_ids),
            new_matches_saved=len(records.match_records),
            existing_matches_skipped=len(plan.existing_matches_raw),
            player_matches_upserted=len(records.player_match_records),
            backfilled_from_raw=records.backfilled_from_raw,
            failed_matches=len(failed_match_ids),
            failed_match_ids=failed_match_ids,
        )

    def _empty_collection(self, fetch_failed_ids: list[str]) -> MatchSyncCollection:
        return MatchSyncCollection(
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
