from app.schemas.player_refresh import (
    MatchSyncResponse,
    PlayerProfileResponse,
    PlayerRefreshResponse,
    RankedEntryResponse,
    RefreshSummaryResponse,
)
from app.services import PlayerRefreshResult


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
        match_sync=MatchSyncResponse(
            queue=result.match_sync.queue,
            requested_count=result.match_sync.requested_count,
            match_ids_received=result.match_sync.match_ids_received,
            new_matches_saved=result.match_sync.new_matches_saved,
            existing_matches_skipped=result.match_sync.existing_matches_skipped,
            player_matches_upserted=result.match_sync.player_matches_upserted,
            backfilled_from_raw=result.match_sync.backfilled_from_raw,
            failed_matches=result.match_sync.failed_matches,
            failed_match_ids=result.match_sync.failed_match_ids,
        ),
        summary=RefreshSummaryResponse(
            matches_found=result.match_sync.match_ids_received,
            new_matches_saved=result.match_sync.new_matches_saved,
            refreshed_at=result.player.last_refreshed_at,
        ),
    )
