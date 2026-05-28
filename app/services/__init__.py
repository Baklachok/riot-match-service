"""Service layer public API."""

from app.services.contracts import (
    MatchSyncSummary,
    PlayerRefreshResult,
    ReadChampionStats,
    ReadPlayer,
    ReadPlayerMatch,
    ReadPlayerProfile,
    ReadRankedEntry,
    RefreshedPlayer,
    RefreshedRankedEntry,
)
from app.services.errors import PlayerReadServiceError, PlayerRefreshServiceError, ServiceError
from app.services.integrations import (
    RiotApiError,
    RiotClient,
    RiotClientError,
    RiotConfigurationError,
)
from app.services.use_cases import PlayerReadService, PlayerRefreshService

__all__ = (
    "MatchSyncSummary",
    "PlayerReadService",
    "PlayerReadServiceError",
    "PlayerRefreshResult",
    "PlayerRefreshService",
    "PlayerRefreshServiceError",
    "ReadChampionStats",
    "ReadPlayer",
    "ReadPlayerMatch",
    "ReadPlayerProfile",
    "ReadRankedEntry",
    "RefreshedPlayer",
    "RefreshedRankedEntry",
    "RiotApiError",
    "RiotClient",
    "RiotClientError",
    "RiotConfigurationError",
    "ServiceError",
)
