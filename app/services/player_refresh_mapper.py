from datetime import datetime

from app.services.player_refresh_models import (
    PlayerRefreshResult,
    RefreshedPlayer,
    RefreshedRankedEntry,
)
from app.services.riot.schemas import RiotAccount, RiotLeagueEntry, RiotSummoner


def normalize_ranked_entries(entries: list[RiotLeagueEntry]) -> list[RefreshedRankedEntry]:
    deduplicated: dict[str, RefreshedRankedEntry] = {}
    for entry in entries:
        deduplicated[entry.queue_type] = RefreshedRankedEntry(
            queue_type=entry.queue_type,
            tier=entry.tier,
            rank=entry.rank,
            league_points=entry.league_points,
            wins=entry.wins,
            losses=entry.losses,
        )

    return sorted(deduplicated.values(), key=lambda item: item.queue_type)


def build_refresh_result(
    *,
    account: RiotAccount,
    summoner: RiotSummoner,
    platform: str,
    refreshed_at: datetime,
    ranked_entries: list[RefreshedRankedEntry],
) -> PlayerRefreshResult:
    player = RefreshedPlayer(
        puuid=account.puuid,
        game_name=account.game_name,
        tag_line=account.tag_line,
        platform=platform,
        profile_icon_id=summoner.profile_icon_id,
        summoner_level=summoner.summoner_level,
        last_refreshed_at=refreshed_at,
        refresh_status="success",
        refresh_error=None,
    )
    return PlayerRefreshResult(player=player, ranked_entries=ranked_entries)


def normalize_error_message(exc: Exception) -> str:
    message = str(exc).strip()
    if not message:
        message = exc.__class__.__name__
    return message[:500]
