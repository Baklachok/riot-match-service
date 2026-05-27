from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.player import Player
from app.models.ranked_entry import RankedEntry
from app.services.riot.client import RiotClient
from app.services.riot.errors import RiotClientError
from app.services.riot.schemas import RiotAccount, RiotLeagueEntry, RiotSummoner


@dataclass(frozen=True)
class RefreshedPlayer:
    puuid: str
    game_name: str
    tag_line: str
    platform: str
    profile_icon_id: int | None
    summoner_level: int | None
    last_refreshed_at: datetime
    refresh_status: str
    refresh_error: str | None


@dataclass(frozen=True)
class RefreshedRankedEntry:
    queue_type: str
    tier: str | None
    rank: str | None
    league_points: int
    wins: int
    losses: int


@dataclass(frozen=True)
class PlayerRefreshResult:
    player: RefreshedPlayer
    ranked_entries: list[RefreshedRankedEntry]


class PlayerRefreshService:
    def __init__(
        self,
        *,
        session: AsyncSession,
        riot_client: RiotClient,
        platform: str,
    ) -> None:
        self._session = session
        self._riot_client = riot_client
        self._platform = platform.strip().lower()

    async def refresh_player(self, *, game_name: str, tag_line: str) -> PlayerRefreshResult:
        account = await self._riot_client.get_account_by_riot_id(
            game_name=game_name,
            tag_line=tag_line,
        )

        summoner: RiotSummoner | None = None
        try:
            summoner = await self._riot_client.get_summoner_by_puuid(account.puuid)
            ranked_entries = await self._riot_client.get_ranked_entries_by_puuid(account.puuid)
        except RiotClientError as exc:
            await self._persist_failed_refresh(
                account=account,
                summoner=summoner,
                error_message=self._error_message(exc),
            )
            raise

        refreshed_at = datetime.now(UTC)
        normalized_ranked_entries = self._normalize_ranked_entries(ranked_entries)
        await self._persist_success_refresh(
            account=account,
            summoner=summoner,
            ranked_entries=normalized_ranked_entries,
            refreshed_at=refreshed_at,
        )

        return PlayerRefreshResult(
            player=RefreshedPlayer(
                puuid=account.puuid,
                game_name=account.game_name,
                tag_line=account.tag_line,
                platform=self._platform,
                profile_icon_id=summoner.profile_icon_id,
                summoner_level=summoner.summoner_level,
                last_refreshed_at=refreshed_at,
                refresh_status="success",
                refresh_error=None,
            ),
            ranked_entries=normalized_ranked_entries,
        )

    async def _persist_success_refresh(
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

    async def _persist_failed_refresh(
        self,
        *,
        account: RiotAccount,
        summoner: RiotSummoner | None,
        error_message: str,
    ) -> None:
        refreshed_at = datetime.now(UTC)
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
        player_values = {
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
        insert_stmt = insert(Player).values(**player_values)

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

        statement = insert_stmt.on_conflict_do_update(
            index_elements=[Player.puuid],
            set_=update_values,
        )
        await self._session.execute(statement)

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

    def _normalize_ranked_entries(
        self,
        ranked_entries: list[RiotLeagueEntry],
    ) -> list[RefreshedRankedEntry]:
        deduplicated: dict[str, RefreshedRankedEntry] = {}
        for entry in ranked_entries:
            deduplicated[entry.queue_type] = RefreshedRankedEntry(
                queue_type=entry.queue_type,
                tier=entry.tier,
                rank=entry.rank,
                league_points=entry.league_points,
                wins=entry.wins,
                losses=entry.losses,
            )

        return sorted(deduplicated.values(), key=lambda item: item.queue_type)

    def _error_message(self, exc: Exception) -> str:
        message = str(exc).strip()
        if not message:
            message = exc.__class__.__name__
        return message[:500]
