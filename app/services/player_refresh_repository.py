from datetime import datetime

from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.player import Player
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
        refreshed_at: datetime,
    ) -> None:
        async with self._session.begin():
            await self._upsert_player(
                account=account,
                summoner=summoner,
                refreshed_at=refreshed_at,
                refresh_status="success",
                refresh_error=None,
                update_profile_fields=True,
            )
            await self._sync_ranked_entries(
                player_puuid=account.puuid,
                ranked_entries=ranked_entries,
                refreshed_at=refreshed_at,
            )

    async def persist_failed(
        self,
        *,
        account: RiotAccount,
        summoner: RiotSummoner | None,
        refreshed_at: datetime,
        error_message: str,
    ) -> None:
        async with self._session.begin():
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
