from __future__ import annotations

from typing import Literal

ViolationType = Literal[
    "sidewalk",
    "crosswalk",
    "disabled_spot",
    "bus_stop",
    "lawn",
    "no_parking_sign",
    "bike_lane",
    "intersection",
    "other",
]

# Short PL label, used in subject and as user-facing dropdown text.
LABELS: dict[ViolationType, str] = {
    "sidewalk": "parkowanie na chodniku",
    "crosswalk": "parkowanie na przejściu dla pieszych",
    "disabled_spot": "parkowanie na kopercie dla osób niepełnosprawnych",
    "bus_stop": "parkowanie na przystanku",
    "lawn": "parkowanie na trawniku",
    "no_parking_sign": "parkowanie w miejscu z zakazem postoju",
    "bike_lane": "parkowanie na drodze dla rowerów",
    "intersection": "parkowanie na skrzyżowaniu",
    "other": "nieprawidłowe parkowanie",
}

# Verb phrase that completes: "Pojazd marki X o numerze rej. Y <ACTION>."
ACTIONS: dict[ViolationType, str] = {
    "sidewalk": "jest zaparkowany na chodniku, ograniczając przejście pieszym",
    "crosswalk": "jest zaparkowany na przejściu dla pieszych",
    "disabled_spot": "zajmuje miejsce parkingowe dla osób z niepełnosprawnościami",
    "bus_stop": "jest zaparkowany na przystanku komunikacji miejskiej",
    "lawn": "niszczy zieleń, parkując na trawniku",
    "no_parking_sign": "jest zaparkowany w miejscu objętym zakazem postoju",
    "bike_lane": "jest zaparkowany na drodze dla rowerów",
    "intersection": "jest zaparkowany na skrzyżowaniu",
    "other": "jest zaparkowany w sposób nieprawidłowy",
}


def sm_category_for(violation: ViolationType) -> str:
    """Returns the SM form uz_kategoria id for the given violation type."""
    return "17402" if violation == "lawn" else "86808"


def build_subject(violation: ViolationType) -> str:
    return f"Nieprawidłowe parkowanie - {LABELS[violation]}"


def build_body(
    violation: ViolationType,
    make: str | None,
    plate: str | None,
    color: str | None = None,
    address: str | None = None,
) -> str:
    """Compose the standardized report body. Handles missing fields gracefully."""
    parts = ["Pojazd"]
    if make:
        parts.append(f"marki {make}")
        if color:
            parts.append(f"lakier {color}")
    if plate:
        parts.append(f"o numerze rejestracyjnym {plate}")
    vehicle = " ".join(parts)

    body = f"{vehicle} {ACTIONS[violation]}."
    if address:
        body += f" Lokalizacja: {address}."
    return body
