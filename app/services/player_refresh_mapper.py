from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal

from app.services.player_refresh_models import (
    MatchSyncSummary,
    PlayerRefreshResult,
    RefreshedPlayer,
    RefreshedRankedEntry,
)
from app.services.riot.schemas import (
    RiotAccount,
    RiotLeagueEntry,
    RiotMatch,
    RiotParticipant,
    RiotSummoner,
)


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
    refresh_status: str,
    refresh_error: str | None,
    ranked_entries: list[RefreshedRankedEntry],
    match_sync: MatchSyncSummary,
) -> PlayerRefreshResult:
    player = RefreshedPlayer(
        puuid=account.puuid,
        game_name=account.game_name,
        tag_line=account.tag_line,
        platform=platform,
        profile_icon_id=summoner.profile_icon_id,
        summoner_level=summoner.summoner_level,
        last_refreshed_at=refreshed_at,
        refresh_status=refresh_status,
        refresh_error=refresh_error,
    )
    return PlayerRefreshResult(
        player=player,
        ranked_entries=ranked_entries,
        match_sync=match_sync,
    )


def normalize_error_message(exc: Exception) -> str:
    message = str(exc).strip()
    if not message:
        message = exc.__class__.__name__
    return message[:500]


def extract_player_participant(match: RiotMatch, player_puuid: str) -> RiotParticipant | None:
    for participant in match.info.participants:
        if participant.puuid == player_puuid:
            return participant
    return None


def build_match_record(match: RiotMatch) -> dict[str, object]:
    game_start_timestamp = match.info.game_start_timestamp or match.info.game_creation
    if game_start_timestamp is None:
        raise ValueError("Match start timestamp is missing")

    return {
        "match_id": match.metadata.match_id,
        "platform": match_platform(match.metadata.match_id),
        "queue_id": match.info.queue_id,
        "game_start": datetime.fromtimestamp(game_start_timestamp / 1000, tz=UTC),
        "duration_seconds": match.info.game_duration,
        "patch": normalize_patch(match.info.game_version),
        "raw_json": match.raw_json,
    }


def build_player_match_record(
    *,
    player_puuid: str,
    match_id: str,
    participant: RiotParticipant,
) -> dict[str, object]:
    deaths = max(participant.deaths, 1)
    kda = (Decimal(participant.kills + participant.assists) / Decimal(deaths)).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )

    return {
        "player_puuid": player_puuid,
        "match_id": match_id,
        "champion_id": participant.champion_id,
        "champion_name": participant.champion_name,
        "team_position": normalize_team_position(participant.team_position),
        "win": participant.win,
        "kills": participant.kills,
        "deaths": participant.deaths,
        "assists": participant.assists,
        "kda": kda,
        "gold_earned": participant.gold_earned,
        "total_minions_killed": participant.total_minions_killed,
        "neutral_minions_killed": participant.neutral_minions_killed,
        "vision_score": participant.vision_score,
        "total_damage_dealt_to_champions": participant.total_damage_dealt_to_champions,
        "summoner_spell_1_id": participant.summoner_spell_1_id,
        "summoner_spell_2_id": participant.summoner_spell_2_id,
        "item0": participant.item0,
        "item1": participant.item1,
        "item2": participant.item2,
        "item3": participant.item3,
        "item4": participant.item4,
        "item5": participant.item5,
        "item6": participant.item6,
    }


def normalize_patch(game_version: str) -> str | None:
    parts = [part for part in game_version.split(".") if part]
    if len(parts) >= 2:
        return f"{parts[0]}.{parts[1]}"
    if len(parts) == 1:
        return parts[0]
    return None


def normalize_team_position(team_position: str | None) -> str | None:
    if team_position is None:
        return None
    normalized = team_position.strip().upper()
    if normalized in {"", "NONE"}:
        return None
    return normalized


def match_platform(match_id: str) -> str:
    if "_" not in match_id:
        return "unknown"
    return match_id.split("_", 1)[0].lower()


def normalize_match_sync_error(failed_match_ids: list[str]) -> str:
    if not failed_match_ids:
        return ""
    preview = ", ".join(failed_match_ids[:5])
    suffix = " ..." if len(failed_match_ids) > 5 else ""
    return f"Failed to sync {len(failed_match_ids)} match(es): {preview}{suffix}"[:500]
