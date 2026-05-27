from datetime import datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.match import Match
from app.models.player import Player
from app.models.player_match import PlayerMatch
from app.models.ranked_entry import RankedEntry
from app.services.player_refresh_models import RefreshedRankedEntry
from app.services.riot.schemas import RiotAccount, RiotSummoner


class PlayerRefreshRepository:
    def __init__(self, *, session: AsyncSession, platform: str) -> None:
        self._session = session
        self._platform = platform.strip().lower()

    async def persist_success(
        self,
        *,
        account: RiotAccount,
        summoner: RiotSummoner,
        ranked_entries: list[RefreshedRankedEntry],
        match_records: list[dict[str, object]],
        player_match_records: list[dict[str, object]],
        refreshed_at: datetime,
        refresh_status: str,
        refresh_error: str | None,
    ) -> None:
        if self._session.in_transaction():
            try:
                await self._persist_success_operations(
                    account=account,
                    summoner=summoner,
                    ranked_entries=ranked_entries,
                    match_records=match_records,
                    player_match_records=player_match_records,
                    refreshed_at=refreshed_at,
                    refresh_status=refresh_status,
                    refresh_error=refresh_error,
                )
                await self._session.commit()
            except Exception:
                await self._session.rollback()
                raise
            return

        async with self._session.begin():
            await self._persist_success_operations(
                account=account,
                summoner=summoner,
                ranked_entries=ranked_entries,
                match_records=match_records,
                player_match_records=player_match_records,
                refreshed_at=refreshed_at,
                refresh_status=refresh_status,
                refresh_error=refresh_error,
            )

    async def persist_failed(
        self,
        *,
        account: RiotAccount,
        summoner: RiotSummoner | None,
        refreshed_at: datetime,
        error_message: str,
    ) -> None:
        if self._session.in_transaction():
            try:
                await self._persist_failed_operations(
                    account=account,
                    summoner=summoner,
                    refreshed_at=refreshed_at,
                    error_message=error_message,
                )
                await self._session.commit()
            except Exception:
                await self._session.rollback()
                raise
            return

        async with self._session.begin():
            await self._persist_failed_operations(
                account=account,
                summoner=summoner,
                refreshed_at=refreshed_at,
                error_message=error_message,
            )

    async def _persist_success_operations(
        self,
        *,
        account: RiotAccount,
        summoner: RiotSummoner,
        ranked_entries: list[RefreshedRankedEntry],
        match_records: list[dict[str, object]],
        player_match_records: list[dict[str, object]],
        refreshed_at: datetime,
        refresh_status: str,
        refresh_error: str | None,
    ) -> None:
        await self._upsert_player(
            account=account,
            summoner=summoner,
            refreshed_at=refreshed_at,
            refresh_status=refresh_status,
            refresh_error=refresh_error,
            update_profile_fields=True,
        )
        await self._sync_ranked_entries(
            player_puuid=account.puuid,
            ranked_entries=ranked_entries,
            refreshed_at=refreshed_at,
        )
        await self._upsert_matches(match_records)
        await self._upsert_player_matches(player_match_records)

    async def _persist_failed_operations(
        self,
        *,
        account: RiotAccount,
        summoner: RiotSummoner | None,
        refreshed_at: datetime,
        error_message: str,
    ) -> None:
        await self._upsert_player(
            account=account,
            summoner=summoner,
            refreshed_at=refreshed_at,
            refresh_status="failed",
            refresh_error=error_message,
            update_profile_fields=summoner is not None,
        )

    async def _upsert_player(
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
        update_values = self._build_player_update_values(
            player_values=player_values,
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

    def _build_player_update_values(
        self,
        *,
        player_values: dict[str, object],
        update_profile_fields: bool,
    ) -> dict[str, object]:
        update_values: dict[str, object] = {
            "game_name": player_values["game_name"],
            "tag_line": player_values["tag_line"],
            "platform": player_values["platform"],
            "last_refreshed_at": player_values["last_refreshed_at"],
            "refresh_status": player_values["refresh_status"],
            "refresh_error": player_values["refresh_error"],
            "updated_at": player_values["updated_at"],
        }
        if update_profile_fields:
            update_values["profile_icon_id"] = player_values["profile_icon_id"]
            update_values["summoner_level"] = player_values["summoner_level"]
        return update_values

    async def _sync_ranked_entries(
        self,
        *,
        player_puuid: str,
        ranked_entries: list[RefreshedRankedEntry],
        refreshed_at: datetime,
    ) -> None:
        for entry in ranked_entries:
            entry_values = {
                "player_puuid": player_puuid,
                "queue_type": entry.queue_type,
                "tier": entry.tier,
                "rank": entry.rank,
                "league_points": entry.league_points,
                "wins": entry.wins,
                "losses": entry.losses,
                "updated_at": refreshed_at,
            }
            statement = insert(RankedEntry).values(**entry_values).on_conflict_do_update(
                constraint="uq_ranked_entries_player_queue",
                set_={
                    "tier": entry_values["tier"],
                    "rank": entry_values["rank"],
                    "league_points": entry_values["league_points"],
                    "wins": entry_values["wins"],
                    "losses": entry_values["losses"],
                    "updated_at": entry_values["updated_at"],
                },
            )
            await self._session.execute(statement)

        if ranked_entries:
            queue_types = [entry.queue_type for entry in ranked_entries]
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

    async def _upsert_matches(self, match_records: list[dict[str, object]]) -> None:
        for match_record in match_records:
            statement = insert(Match).values(**match_record).on_conflict_do_update(
                index_elements=[Match.match_id],
                set_={
                    "platform": match_record["platform"],
                    "queue_id": match_record["queue_id"],
                    "game_start": match_record["game_start"],
                    "duration_seconds": match_record["duration_seconds"],
                    "patch": match_record["patch"],
                    "raw_json": match_record["raw_json"],
                },
            )
            await self._session.execute(statement)

    async def _upsert_player_matches(self, player_match_records: list[dict[str, object]]) -> None:
        for player_match_record in player_match_records:
            statement = insert(PlayerMatch).values(**player_match_record).on_conflict_do_update(
                constraint="uq_player_matches_player_match",
                set_={
                    "champion_id": player_match_record["champion_id"],
                    "champion_name": player_match_record["champion_name"],
                    "team_position": player_match_record["team_position"],
                    "win": player_match_record["win"],
                    "kills": player_match_record["kills"],
                    "deaths": player_match_record["deaths"],
                    "assists": player_match_record["assists"],
                    "gold_earned": player_match_record["gold_earned"],
                    "total_minions_killed": player_match_record["total_minions_killed"],
                    "neutral_minions_killed": player_match_record["neutral_minions_killed"],
                    "vision_score": player_match_record["vision_score"],
                    "total_damage_dealt_to_champions": player_match_record[
                        "total_damage_dealt_to_champions"
                    ],
                    "summoner_spell_1_id": player_match_record["summoner_spell_1_id"],
                    "summoner_spell_2_id": player_match_record["summoner_spell_2_id"],
                    "item0": player_match_record["item0"],
                    "item1": player_match_record["item1"],
                    "item2": player_match_record["item2"],
                    "item3": player_match_record["item3"],
                    "item4": player_match_record["item4"],
                    "item5": player_match_record["item5"],
                    "item6": player_match_record["item6"],
                },
            )
            await self._session.execute(statement)
