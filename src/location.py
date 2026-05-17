from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import requests
from pyproj import Transformer

_NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"
_USER_AGENT = "konfident.ai (parking-report assistant; contact: adam.luczka@tuta.io)"

_WGS84_TO_PL1992 = Transformer.from_crs("EPSG:4326", "EPSG:2177", always_xy=True)


@dataclass(frozen=True)
class Address:
    display: str  # short human-readable, e.g. "Św. Marcin 24, Poznań"
    street_lookup: str  # value for the SM map "street" search field, e.g. "Św. Marcin"


def wgs84_to_epsg2177(lat: float, lon: float) -> tuple[float, float]:
    """WGS84 (degrees) -> EPSG:2177 (meters). Returns (x, y)."""
    x, y = _WGS84_TO_PL1992.transform(lon, lat)
    return x, y


@lru_cache(maxsize=128)
def reverse_geocode(lat: float, lon: float) -> Address | None:
    """Look up a postal address for the given WGS84 coords. Returns None on failure."""
    try:
        r = requests.get(
            _NOMINATIM_URL,
            params={
                "lat": lat,
                "lon": lon,
                "format": "jsonv2",
                "accept-language": "pl",
                "zoom": 18,
            },
            headers={"User-Agent": _USER_AGENT},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
    except (requests.RequestException, ValueError):
        return None

    addr = data.get("address", {})
    street = addr.get("road") or addr.get("pedestrian") or addr.get("footway") or ""
    house = addr.get("house_number", "")
    city = (
        addr.get("city")
        or addr.get("town")
        or addr.get("village")
        or addr.get("municipality")
        or ""
    )

    parts: list[str] = []
    if street:
        parts.append(f"{street} {house}".strip())
    if city:
        parts.append(city)
    display = ", ".join(parts) if parts else data.get("display_name", "")

    return Address(display=display, street_lookup=street)
