from sqlalchemy.ext.asyncio import AsyncSession

from app.services.contracts.player_read import (
    ReadChampionStats,
    ReadPlayer,
    ReadPlayerMatch,
    ReadPlayerProfile,
)
from app.services.repositories.player_read import PlayerReadRepository


class PlayerReadService:
    def __init__(self, *, session: AsyncSession) -> None:
        self._repository = PlayerReadRepository(session=session)

    async def search_player_by_riot_id(
        self,
        *,
        game_name: str,
        tag_line: str,
    ) -> ReadPlayer | None:
        return await self._repository.find_player_by_riot_id(
            game_name=game_name,
            tag_line=tag_line,
        )

    async def get_player_profile(self, *, puuid: str) -> ReadPlayerProfile | None:
        player = await self._repository.get_player_by_puuid(puuid=puuid)
        if player is None:
            return None
        ranked_entries = await self._repository.get_ranked_entries(player_puuid=puuid)
        return ReadPlayerProfile(
            player=player,
            ranked_entries=ranked_entries,
        )

    async def get_player_matches(self, *, puuid: str, limit: int) -> list[ReadPlayerMatch] | None:
        player = await self._repository.get_player_by_puuid(puuid=puuid)
        if player is None:
            return None
        return await self._repository.get_matches(
            player_puuid=puuid,
            limit=limit,
        )

    async def get_player_champions(
        self,
        *,
        puuid: str,
        queue_id: int,
        limit: int,
    ) -> list[ReadChampionStats] | None:
        player = await self._repository.get_player_by_puuid(puuid=puuid)
        if player is None:
            return None
        return await self._repository.get_champion_stats(
            player_puuid=puuid,
            queue_id=queue_id,
            limit=limit,
        )
