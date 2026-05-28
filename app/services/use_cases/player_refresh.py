from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.contracts.player_refresh import (
    MatchSyncSummary,
    PlayerRefreshResult,
    RefreshedPlayer,
    RefreshedRankedEntry,
)
from app.services.integrations.riot import RiotClient, RiotClientError
from app.services.integrations.riot.models import RiotAccount, RiotSummoner
from app.services.mappers.player_refresh import (
    build_refresh_result,
    normalize_error_message,
    normalize_match_sync_error,
    normalize_ranked_entries,
)
from app.services.repositories.player_refresh import PlayerRefreshRepository
from app.services.sync.player_refresh_match_sync import (
    MatchSyncCollection,
    PlayerMatchSyncCollector,
)

__all__ = (
    "MatchSyncSummary",
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
        match_sync_count: int = 30,
        match_sync_queue: int = 420,
    ) -> None:
        self._session = session
        self._riot_client = riot_client
        self._repository = PlayerRefreshRepository(session=session, platform=platform)
        self._platform = platform.strip().lower()
        self._match_sync = PlayerMatchSyncCollector(
            riot_client=riot_client,
            repository=self._repository,
            match_sync_count=match_sync_count,
            match_sync_queue=match_sync_queue,
        )

    async def refresh_player_by_riot_id(
        self,
        *,
        game_name: str,
        tag_line: str,
    ) -> PlayerRefreshResult:
        account = await self._riot_client.get_account_by_riot_id(
            game_name=game_name,
            tag_line=tag_line,
        )
        return await self._refresh_account(account=account)

    async def refresh_player_by_puuid(self, *, puuid: str) -> PlayerRefreshResult:
        account = await self._riot_client.get_account_by_puuid(puuid=puuid)
        return await self._refresh_account(account=account)

    async def _refresh_account(self, *, account: RiotAccount) -> PlayerRefreshResult:
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
        assert summoner is not None
        ranked_entries = normalize_ranked_entries(riot_ranked_entries)
        match_sync = await self._match_sync.collect(player_puuid=account.puuid)
        refresh_status, refresh_error = self._refresh_outcome(
            failed_match_ids=match_sync.summary.failed_match_ids,
        )
        await self._persist_successful_refresh(
            account=account,
            summoner=summoner,
            refreshed_at=refreshed_at,
            refresh_status=refresh_status,
            refresh_error=refresh_error,
            ranked_entries=ranked_entries,
            match_sync=match_sync,
        )
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

    async def _persist_successful_refresh(
        self,
        *,
        account: RiotAccount,
        summoner: RiotSummoner,
        refreshed_at: datetime,
        refresh_status: str,
        refresh_error: str | None,
        ranked_entries: list[RefreshedRankedEntry],
        match_sync: MatchSyncCollection,
    ) -> None:
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

    @staticmethod
    def _refresh_outcome(*, failed_match_ids: list[str]) -> tuple[str, str | None]:
        if failed_match_ids:
            return "partial_success", normalize_match_sync_error(failed_match_ids)
        return "success", None

    async def _reset_session_transaction(self) -> None:
        if self._session.in_transaction():
            await self._session.rollback()
