from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.player_refresh_mapper import (
    build_refresh_result,
    normalize_error_message,
    normalize_ranked_entries,
)
from app.services.player_refresh_models import (
    PlayerRefreshResult,
    RefreshedPlayer,
    RefreshedRankedEntry,
)
from app.services.player_refresh_repository import PlayerRefreshRepository
from app.services.riot.client import RiotClient
from app.services.riot.errors import RiotClientError
from app.services.riot.schemas import RiotSummoner

__all__ = (
    "PlayerRefreshResult",
    "PlayerRefreshService",
    "RefreshedPlayer",
    "RefreshedRankedEntry",
)


class PlayerRefreshService:
    def __init__(
        self,
        *,
        session: AsyncSession,
        riot_client: RiotClient,
        platform: str,
    ) -> None:
        self._riot_client = riot_client
        self._repository = PlayerRefreshRepository(session=session, platform=platform)
        self._platform = platform.strip().lower()

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
            await self._repository.persist_failed(
                account=account,
                summoner=summoner,
                refreshed_at=datetime.now(UTC),
                error_message=normalize_error_message(exc),
            )
            raise

        refreshed_at = datetime.now(UTC)
        ranked_entries = normalize_ranked_entries(riot_ranked_entries)
        await self._repository.persist_success(
            account=account,
            summoner=summoner,
            ranked_entries=ranked_entries,
            refreshed_at=refreshed_at,
        )

        return build_refresh_result(
            account=account,
            summoner=summoner,
            platform=self._platform,
            refreshed_at=refreshed_at,
            ranked_entries=ranked_entries,
        )
