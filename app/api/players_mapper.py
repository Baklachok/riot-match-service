from app.schemas.player_read import (
    ReadChampionStatsResponse,
    ReadPlayerChampionsResponse,
    ReadPlayerMatchesResponse,
    ReadPlayerMatchResponse,
    ReadPlayerProfileResponse,
    ReadPlayerResponse,
    ReadRankedEntryResponse,
)
from app.services.player_read_models import (
    ReadChampionStats,
    ReadPlayer,
    ReadPlayerMatch,
    ReadPlayerProfile,
    ReadRankedEntry,
)


def to_read_player_response(player: ReadPlayer) -> ReadPlayerResponse:
    return ReadPlayerResponse(
        puuid=player.puuid,
        game_name=player.game_name,
        tag_line=player.tag_line,
        platform=player.platform,
        profile_icon_id=player.profile_icon_id,
        summoner_level=player.summoner_level,
        last_refreshed_at=player.last_refreshed_at,
        refresh_status=player.refresh_status,
        refresh_error=player.refresh_error,
    )


def to_read_player_profile_response(profile: ReadPlayerProfile) -> ReadPlayerProfileResponse:
    return ReadPlayerProfileResponse(
        player=to_read_player_response(profile.player),
        ranked_entries=[to_read_ranked_entry_response(entry) for entry in profile.ranked_entries],
    )


def to_read_player_matches_response(
    *,
    matches: list[ReadPlayerMatch],
    limit: int,
) -> ReadPlayerMatchesResponse:
    return ReadPlayerMatchesResponse(
        limit=limit,
        items=[to_read_player_match_response(match) for match in matches],
    )


def to_read_player_champions_response(
    *,
    champions: list[ReadChampionStats],
    queue_id: int,
    limit: int,
) -> ReadPlayerChampionsResponse:
    return ReadPlayerChampionsResponse(
        queue_id=queue_id,
        limit=limit,
        items=[to_read_champion_stats_response(champion) for champion in champions],
    )


def to_read_ranked_entry_response(entry: ReadRankedEntry) -> ReadRankedEntryResponse:
    return ReadRankedEntryResponse(
        queue_type=entry.queue_type,
        tier=entry.tier,
        rank=entry.rank,
        league_points=entry.league_points,
        wins=entry.wins,
        losses=entry.losses,
    )


def to_read_player_match_response(match: ReadPlayerMatch) -> ReadPlayerMatchResponse:
    return ReadPlayerMatchResponse(
        match_id=match.match_id,
        champion_id=match.champion_id,
        champion_name=match.champion_name,
        lane=match.lane,
        win=match.win,
        kills=match.kills,
        deaths=match.deaths,
        assists=match.assists,
        kda=match.kda,
        queue_id=match.queue_id,
        game_start=match.game_start,
        duration_seconds=match.duration_seconds,
        patch=match.patch,
    )


def to_read_champion_stats_response(champion: ReadChampionStats) -> ReadChampionStatsResponse:
    return ReadChampionStatsResponse(
        champion_id=champion.champion_id,
        champion_name=champion.champion_name,
        games=champion.games,
        wins=champion.wins,
        losses=champion.losses,
        win_rate_percent=champion.win_rate_percent,
        kda=champion.kda,
    )
