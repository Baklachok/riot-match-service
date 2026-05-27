from datetime import datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import Insert, insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.match import Match
from app.models.player import Player
from app.models.player_match import PlayerMatch
from app.models.ranked_entry import RankedEntry
from app.services.player_refresh_models import RefreshedRankedEntry
from app.services.riot.schemas import RiotAccount, RiotSummoner


class PlayerRefreshRepository:
    _PLAYER_BASE_UPDATE_FIELDS = (
        "game_name",
        "tag_line",
        "platform",
        "last_refreshed_at",
        "refresh_status",
        "refresh_error",
        "updated_at",
    )
    _PLAYER_PROFILE_UPDATE_FIELDS = (
        "profile_icon_id",
        "summoner_level",
    )
    _RANKED_ENTRY_UPDATE_FIELDS = (
        "tier",
        "rank",
        "league_points",
        "wins",
        "losses",
        "updated_at",
    )
    _MATCH_UPDATE_FIELDS = (
        "platform",
        "queue_id",
        "game_start",
        "duration_seconds",
        "patch",
        "raw_json",
    )
    _PLAYER_MATCH_UPDATE_FIELDS = (
        "champion_id",
        "champion_name",
        "team_position",
        "win",
        "kills",
        "deaths",
        "assists",
        "kda",
        "gold_earned",
        "total_minions_killed",
        "neutral_minions_killed",
        "vision_score",
        "total_damage_dealt_to_champions",
        "summoner_spell_1_id",
        "summoner_spell_2_id",
        "item0",
        "item1",
        "item2",
        "item3",
        "item4",
        "item5",
        "item6",
    )

    def __init__(self, *, session: AsyncSession, platform: str) -> None:
        self._session = session
        self._platform = platform.strip().lower()

    async def upsert_player(
        self,
        *,
        account: RiotAccount,
        summoner: RiotSummoner | None,
        refreshed_at: datetime,
        refresh_status: str,
        refresh_error: str | None,
        update_profile_fields: bool,
    ) -> None:
        player_values = self._build_player_values(
            account=account,
            summoner=summoner,
            refreshed_at=refreshed_at,
            refresh_status=refresh_status,
            refresh_error=refresh_error,
        )
        insert_stmt = insert(Player).values(**player_values)
        update_values = self._player_update_values(
            insert_stmt=insert_stmt,
            update_profile_fields=update_profile_fields,
        )

        statement = insert_stmt.on_conflict_do_update(
            index_elements=[Player.puuid],
            set_=update_values,
        )
        await self._session.execute(statement)

    def _build_player_values(
        self,
        *,
        account: RiotAccount,
        summoner: RiotSummoner | None,
        refreshed_at: datetime,
        refresh_status: str,
        refresh_error: str | None,
    ) -> dict[str, object]:
        return {
            "puuid": account.puuid,
            "game_name": account.game_name,
            "tag_line": account.tag_line,
            "platform": self._platform,
            "profile_icon_id": summoner.profile_icon_id if summoner is not None else None,
            "summoner_level": summoner.summoner_level if summoner is not None else None,
            "last_refreshed_at": refreshed_at,
            "refresh_status": refresh_status,
            "refresh_error": refresh_error,
            "updated_at": refreshed_at,
        }

    def _player_update_values(
        self,
        *,
        insert_stmt: Insert,
        update_profile_fields: bool,
    ) -> dict[str, object]:
        update_fields: tuple[str, ...] = self._PLAYER_BASE_UPDATE_FIELDS
        if update_profile_fields:
            update_fields = (*update_fields, *self._PLAYER_PROFILE_UPDATE_FIELDS)
        return self._excluded_fields(
            insert_stmt=insert_stmt,
            fields=update_fields,
        )

    async def sync_ranked_entries(
        self,
        *,
        player_puuid: str,
        ranked_entries: list[RefreshedRankedEntry],
        refreshed_at: datetime,
    ) -> None:
        deduplicated_entries: dict[str, RefreshedRankedEntry] = {}
        for entry in ranked_entries:
            deduplicated_entries[entry.queue_type] = entry

        if deduplicated_entries:
            values = [
                {
                    "player_puuid": player_puuid,
                    "queue_type": entry.queue_type,
                    "tier": entry.tier,
                    "rank": entry.rank,
                    "league_points": entry.league_points,
                    "wins": entry.wins,
                    "losses": entry.losses,
                    "updated_at": refreshed_at,
                }
                for entry in deduplicated_entries.values()
            ]
            insert_stmt = insert(RankedEntry).values(values)
            statement = insert_stmt.on_conflict_do_update(
                constraint="uq_ranked_entries_player_queue",
                set_=self._excluded_fields(
                    insert_stmt=insert_stmt,
                    fields=self._RANKED_ENTRY_UPDATE_FIELDS,
                ),
            )
            await self._session.execute(statement)

            queue_types = list(deduplicated_entries)
            delete_stmt = delete(RankedEntry).where(
                RankedEntry.player_puuid == player_puuid,
                RankedEntry.queue_type.not_in(queue_types),
            )
        else:
            delete_stmt = delete(RankedEntry).where(RankedEntry.player_puuid == player_puuid)
        await self._session.execute(delete_stmt)

    async def get_existing_matches_raw(
        self,
        match_ids: list[str],
    ) -> dict[str, dict[str, Any]]:
        if not match_ids:
            return {}

        statement = select(Match.match_id, Match.raw_json).where(Match.match_id.in_(match_ids))
        rows = await self._session.execute(statement)
        return {match_id: raw_json for match_id, raw_json in rows}

    async def get_existing_player_match_ids(
        self,
        *,
        player_puuid: str,
        match_ids: list[str],
    ) -> set[str]:
        if not match_ids:
            return set()

        statement = select(PlayerMatch.match_id).where(
            PlayerMatch.player_puuid == player_puuid,
            PlayerMatch.match_id.in_(match_ids),
        )
        rows = await self._session.execute(statement)
        return set(rows.scalars().all())

    async def upsert_matches(self, match_records: list[dict[str, object]]) -> None:
        if not match_records:
            return
        deduplicated_records = self._deduplicate_records(
            records=match_records,
            key_fields=("match_id",),
        )
        insert_stmt = insert(Match).values(deduplicated_records)
        statement = insert_stmt.on_conflict_do_update(
            index_elements=[Match.match_id],
            set_=self._excluded_fields(
                insert_stmt=insert_stmt,
                fields=self._MATCH_UPDATE_FIELDS,
            ),
        )
        await self._session.execute(statement)

    async def upsert_player_matches(self, player_match_records: list[dict[str, object]]) -> None:
        if not player_match_records:
            return
        deduplicated_records = self._deduplicate_records(
            records=player_match_records,
            key_fields=("player_puuid", "match_id"),
        )
        insert_stmt = insert(PlayerMatch).values(deduplicated_records)
        statement = insert_stmt.on_conflict_do_update(
            constraint="uq_player_matches_player_match",
            set_=self._excluded_fields(
                insert_stmt=insert_stmt,
                fields=self._PLAYER_MATCH_UPDATE_FIELDS,
            ),
        )
        await self._session.execute(statement)

    def _excluded_fields(
        self,
        *,
        insert_stmt: Insert,
        fields: tuple[str, ...],
    ) -> dict[str, object]:
        return {field: getattr(insert_stmt.excluded, field) for field in fields}

    def _deduplicate_records(
        self,
        *,
        records: list[dict[str, object]],
        key_fields: tuple[str, ...],
    ) -> list[dict[str, object]]:
        deduplicated: dict[tuple[object, ...], dict[str, object]] = {}
        for record in records:
            key = tuple(record[field] for field in key_fields)
            deduplicated[key] = record
        return list(deduplicated.values())
