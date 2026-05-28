from fastapi import Request

from app.services.riot import RiotClient


def get_riot_client(request: Request) -> RiotClient:
    client = getattr(request.app.state, "riot_client", None)
    if not isinstance(client, RiotClient):
        raise RuntimeError("Riot client is not initialized")
    return client
