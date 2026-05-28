from datetime import datetime
from decimal import Decimal
from typing import Any, TypeAlias
from typing import cast as type_cast

from sqlalchemy import Integer, Numeric, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from app.models.match import Match
from app.models.player import Player
from app.models.player_match import PlayerMatch
from app.models.ranked_entry import RankedEntry
from app.services.contracts.player_read import (
    ReadChampionStats,
    ReadPlayer,
    ReadPlayerMatch,
    ReadRankedEntry,
)

_DecimalLike: TypeAlias = Decimal | float
_PlayerRow: TypeAlias = tuple[
    str,
    str,
    str,
    str,
    int | None,
    int | None,
    datetime | None,
    str | None,
    str | None,
]
_RankedEntryRow: TypeAlias = tuple[str, str | None, str | None, int, int, int]
_PlayerMatchRow: TypeAlias = tuple[
    str,
    int,
    str,
    str | None,
    bool,
    int,
    int,
    int,
    _DecimalLike,
    int,
    datetime,
    int,
    str | None,
]
_ChampionStatsRow: TypeAlias = tuple[int, str, int, int, int, _DecimalLike, _DecimalLike]


class PlayerReadRepository:
    def __init__(self, *, session: AsyncSession) -> None:
        self._session = session

    async def find_player_by_riot_id(
        self,
        *,
        game_name: str,
        tag_line: str,
    ) -> ReadPlayer | None:
        return await self._fetch_player(
            self._build_player_by_riot_id_statement(
                game_name=game_name,
                tag_line=tag_line,
            )
        )

    async def get_player_by_puuid(self, *, puuid: str) -> ReadPlayer | None:
        return await self._fetch_player(
            self._build_player_by_puuid_statement(puuid=puuid),
        )

    async def get_ranked_entries(self, *, player_puuid: str) -> list[ReadRankedEntry]:
        rows = await self._session.execute(
            self._build_ranked_entries_statement(player_puuid=player_puuid),
        )
        return [
            self._map_ranked_entry(
                (
                    queue_type,
                    tier,
                    rank,
                    league_points,
                    wins,
                    losses,
                )
            )
            for queue_type, tier, rank, league_points, wins, losses in rows
        ]

    async def get_matches(self, *, player_puuid: str, limit: int) -> list[ReadPlayerMatch]:
        rows = await self._session.execute(
            self._build_matches_statement(player_puuid=player_puuid, limit=limit),
        )
        return [
            self._map_player_match(
                (
                    match_id,
                    champion_id,
                    champion_name,
                    lane,
                    win,
                    kills,
                    deaths,
                    assists,
                    kda,
                    queue_id,
                    game_start,
                    duration_seconds,
                    patch,
                )
            )
            for (
                match_id,
                champion_id,
                champion_name,
                lane,
                win,
                kills,
                deaths,
                assists,
                kda,
                queue_id,
                game_start,
                duration_seconds,
                patch,
            ) in rows
        ]

    async def get_champion_stats(
        self,
        *,
        player_puuid: str,
        queue_id: int,
        limit: int,
    ) -> list[ReadChampionStats]:
        rows = await self._session.execute(
            self._build_champion_stats_statement(
                player_puuid=player_puuid,
                queue_id=queue_id,
                limit=limit,
            )
        )
        return [
            self._map_champion_stats(
                (
                    champion_id,
                    champion_name,
                    games,
                    wins,
                    losses,
                    win_rate_percent,
                    kda,
                )
            )
            for champion_id, champion_name, games, wins, losses, win_rate_percent, kda in rows
        ]

    def _build_player_by_riot_id_statement(
        self,
        *,
        game_name: str,
        tag_line: str,
    ) -> Select[_PlayerRow]:
        return self._player_select_statement().where(
            func.lower(Player.game_name) == game_name.lower(),
            func.lower(Player.tag_line) == tag_line.lower(),
        )

    def _build_player_by_puuid_statement(self, *, puuid: str) -> Select[_PlayerRow]:
        return self._player_select_statement().where(Player.puuid == puuid)

    def _build_ranked_entries_statement(self, *, player_puuid: str) -> Select[_RankedEntryRow]:
        return (
            select(
                RankedEntry.queue_type,
                RankedEntry.tier,
                RankedEntry.rank,
                RankedEntry.league_points,
                RankedEntry.wins,
                RankedEntry.losses,
            )
            .where(RankedEntry.player_puuid == player_puuid)
            .order_by(RankedEntry.queue_type.asc())
        )

    def _build_matches_statement(self, *, player_puuid: str, limit: int) -> Select[_PlayerMatchRow]:
        return (
            select(
                PlayerMatch.match_id,
                PlayerMatch.champion_id,
                PlayerMatch.champion_name,
                PlayerMatch.team_position,
                PlayerMatch.win,
                PlayerMatch.kills,
                PlayerMatch.deaths,
                PlayerMatch.assists,
                PlayerMatch.kda,
                Match.queue_id,
                Match.game_start,
                Match.duration_seconds,
                Match.patch,
            )
            .join(Match, Match.match_id == PlayerMatch.match_id)
            .where(PlayerMatch.player_puuid == player_puuid)
            .order_by(Match.game_start.desc(), PlayerMatch.match_id.desc())
            .limit(limit)
        )

    def _build_champion_stats_statement(
        self,
        *,
        player_puuid: str,
        queue_id: int,
        limit: int,
    ) -> Select[_ChampionStatsRow]:
        games, wins, losses, win_rate_percent, kda = self._build_champion_aggregates()
        return (
            select(
                PlayerMatch.champion_id,
                PlayerMatch.champion_name,
                games,
                wins,
                losses,
                win_rate_percent,
                kda,
            )
            .join(Match, Match.match_id == PlayerMatch.match_id)
            .where(
                PlayerMatch.player_puuid == player_puuid,
                Match.queue_id == queue_id,
            )
            .group_by(PlayerMatch.champion_id, PlayerMatch.champion_name)
            .order_by(
                games.desc(),
                win_rate_percent.desc(),
                kda.desc(),
                PlayerMatch.champion_name.asc(),
            )
            .limit(limit)
        )

    def _build_champion_aggregates(self) -> tuple[Any, Any, Any, Any, Any]:
        games = func.count(PlayerMatch.id).label("games")
        wins = func.sum(cast(PlayerMatch.win, Integer)).label("wins")
        losses = (games - wins).label("losses")
        win_rate_percent = func.round(
            (cast(wins, Numeric(12, 2)) * 100)
            / cast(func.greatest(games, 1), Numeric(12, 2)),
            2,
        ).label("win_rate_percent")
        kda = func.round(
            cast(func.sum(PlayerMatch.kills + PlayerMatch.assists), Numeric(12, 2))
            / cast(func.greatest(func.sum(PlayerMatch.deaths), 1), Numeric(12, 2)),
            2,
        ).label("kda")
        return games, wins, losses, win_rate_percent, kda

    def _player_select_statement(self) -> Select[_PlayerRow]:
        return select(
            Player.puuid,
            Player.game_name,
            Player.tag_line,
            Player.platform,
            Player.profile_icon_id,
            Player.summoner_level,
            Player.last_refreshed_at,
            Player.refresh_status,
            Player.refresh_error,
        )

    async def _fetch_player(self, statement: Select[_PlayerRow]) -> ReadPlayer | None:
        row = (await self._session.execute(statement)).one_or_none()
        if row is None:
            return None
        return self._map_player(type_cast(_PlayerRow, tuple(row)))

    @staticmethod
    def _map_player(row: _PlayerRow) -> ReadPlayer:
        (
            puuid,
            game_name,
            tag_line,
            platform,
            profile_icon_id,
            summoner_level,
            last_refreshed_at,
            refresh_status,
            refresh_error,
        ) = row
        return ReadPlayer(
            puuid=puuid,
            game_name=game_name,
            tag_line=tag_line,
            platform=platform,
            profile_icon_id=profile_icon_id,
            summoner_level=summoner_level,
            last_refreshed_at=last_refreshed_at,
            refresh_status=refresh_status,
            refresh_error=refresh_error,
        )

    @staticmethod
    def _map_ranked_entry(row: _RankedEntryRow) -> ReadRankedEntry:
        queue_type, tier, rank, league_points, wins, losses = row
        return ReadRankedEntry(
            queue_type=queue_type,
            tier=tier,
            rank=rank,
            league_points=league_points,
            wins=wins,
            losses=losses,
        )

    @staticmethod
    def _map_player_match(row: _PlayerMatchRow) -> ReadPlayerMatch:
        (
            match_id,
            champion_id,
            champion_name,
            lane,
            win,
            kills,
            deaths,
            assists,
            kda,
            queue_id,
            game_start,
            duration_seconds,
            patch,
        ) = row
        return ReadPlayerMatch(
            match_id=match_id,
            champion_id=champion_id,
            champion_name=champion_name,
            lane=lane,
            win=win,
            kills=kills,
            deaths=deaths,
            assists=assists,
            kda=_to_float(kda),
            queue_id=queue_id,
            game_start=game_start,
            duration_seconds=duration_seconds,
            patch=patch,
        )

    @staticmethod
    def _map_champion_stats(row: _ChampionStatsRow) -> ReadChampionStats:
        champion_id, champion_name, games, wins, losses, win_rate_percent, kda = row
        return ReadChampionStats(
            champion_id=champion_id,
            champion_name=champion_name,
            games=games,
            wins=wins,
            losses=losses,
            win_rate_percent=_to_float(win_rate_percent),
            kda=_to_float(kda),
        )


def _to_float(value: _DecimalLike) -> float:
    if isinstance(value, float):
        return value
    return float(value)
