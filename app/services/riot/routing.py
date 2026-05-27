from urllib.parse import quote

from app.services.riot.endpoints import HostKind


class RiotRouting:
    def __init__(self, platform: str, region: str) -> None:
        self._platform = platform.strip().lower()
        self._region = region.strip().lower()

    def build_url(self, host_kind: HostKind, path: str) -> str:
        host = self._platform if host_kind is HostKind.PLATFORM else self._region
        return f"https://{host}.api.riotgames.com{path}"

    def render_path(self, template: str, **parts: str) -> str:
        encoded_parts = {key: quote(value, safe="") for key, value in parts.items()}
        return template.format(**encoded_parts)
