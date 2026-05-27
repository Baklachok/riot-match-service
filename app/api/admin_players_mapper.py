from app.schemas.player_refresh import (
    PlayerProfileResponse,
    PlayerRefreshResponse,
    RankedEntryResponse,
)
from app.services.player_refresh import PlayerRefreshResult


def to_player_refresh_response(result: PlayerRefreshResult) -> PlayerRefreshResponse:
    return PlayerRefreshResponse(
        player=PlayerProfileResponse(
            puuid=result.player.puuid,
            game_name=result.player.game_name,
            tag_line=result.player.tag_line,
            platform=result.player.platform,
            profile_icon_id=result.player.profile_icon_id,
            summoner_level=result.player.summoner_level,
            last_refreshed_at=result.player.last_refreshed_at,
            refresh_status=result.player.refresh_status,
            refresh_error=result.player.refresh_error,
        ),
        ranked_entries=[
            RankedEntryResponse(
                queue_type=entry.queue_type,
                tier=entry.tier,
                rank=entry.rank,
                league_points=entry.league_points,
                wins=entry.wins,
                losses=entry.losses,
            )
            for entry in result.ranked_entries
        ],
    )
