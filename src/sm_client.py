"""
HTTP client for the Poznań Straż Miejska report form.

  1. GET
  2. POST step1   (data) + goto_step1_1   — render map, save form data
  3. POST step1_1 (coords) + goto_step1   — save coords, back to step1
  4. POST step1   (data) + goto_step1_2   — render attachments screen
  5. POST step1_2 (file upload)           — attach file to in-progress ticket
  6. POST step1_2 + goto_step1            — back to step1
  7. POST step1   (data) + goto_summary   — render summary
  8. POST summary + action=save + goto_thanks — commit

State held server-side via JSESSIONID (requests.Session handles it).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import requests
from pyproj import Transformer

FORM_URL = "https://www.poznan.pl/mim/forms/sm_zgloszenia.html"

# Pre-built transformer: WGS84 (lat, lon in degrees) -> PL-1992 (x, y in meters).
# always_xy=True forces (lon, lat) input order and (x, y) output order.
_WGS84_TO_PL1992 = Transformer.from_crs("EPSG:4326", "EPSG:2177", always_xy=True)


@dataclass
class Report:
    category: (
        str  # dropdown id, e.g. "86808" (Traffic - parking), "17402" (greenery damage)
    )
    subject: str
    body: str
    email: str
    full_name: str
    mailing_address: str
    lat: float  # WGS84 from device GPS, e.g. 52.4082
    lon: float  # WGS84 from device GPS, e.g. 16.9335
    photos: list[Path] = field(default_factory=list)
    street_lookup: str = ""  # optional: street name typed into the map search field
    wants_reply: bool = True


def wgs84_to_epsg2177(lat: float, lon: float) -> tuple[float, float]:
    """WGS84 (degrees) -> EPSG:2177 (meters, PL-1992 zone 6, Poznań). Returns (x, y)."""
    x, y = _WGS84_TO_PL1992.transform(lon, lat)
    return x, y


def submit(report: Report, *, dry_run: bool = True, debug: bool = False) -> dict:
    """
    Submit a report. With dry_run=True only the first 3 POSTs are sent (no final
    SAVE) — useful for testing without creating a real ticket in the SM system.

    Returns dict with: x, y (EPSG:2177), responses (list of (step, status, body_len)),
    submitted (bool).
    """
    x, y = wgs84_to_epsg2177(report.lat, report.lon)

    session = requests.Session()
    session.headers["User-Agent"] = (
        "Mozilla/5.0 (X11; Linux x86_64; rv:149.0) Gecko/20100101 Firefox/149.0"
    )
    responses: list[tuple[str, int, int]] = []

    def _log(label: str, r: requests.Response) -> None:
        responses.append((label, r.status_code, len(r.content)))
        if debug:
            print(
                f"[{label}] {r.status_code}  body={len(r.content)}B  cookies={dict(session.cookies)}"
            )
            safe = (
                label.replace(" ", "_")
                .replace("/", "_")
                .replace("(", "")
                .replace(")", "")
            )
            out = Path("/tmp") / f"sm_{len(responses):02d}_{safe}.html"
            out.write_bytes(r.content)

    # 0. GET — initializes JSESSIONID
    r = session.get(FORM_URL)
    r.raise_for_status()
    _log("GET", r)

    # Common step1 form fields — reused across multiple transitions.
    step1_fields = {
        "lhs": "eurzad",
        "source": "sm_zgloszenia_step1",
        "instance": "poznan_sm",
        "srs": "EPSG:2177",
        "uz_process_personal_data_agreement": "Y",
        "uz_kategoria": report.category,
        "uz_temat": report.subject,
        "uz_tresc": report.body,
        "uz_email": report.email,
        "uz_imie_nazwisko": report.full_name,
        "uz_adres": report.mailing_address,
    }
    if report.wants_reply:
        step1_fields["uz_odpowiedz"] = "tak"

    def _post_multipart(fields: dict) -> requests.Response:
        return session.post(FORM_URL, files={k: (None, v) for k, v in fields.items()})

    # 1. step1 → goto_step1_1 — save data, render map screen
    r = _post_multipart({**step1_fields, "goto_sm_zgloszenia_step1_1": ""})
    r.raise_for_status()
    _log("POST step1 → map", r)

    # 2. step1_1 → goto_step1 — save coordinates, back to step1
    step1_1_fields = {
        "lhs": "eurzad",
        "source": "sm_zgloszenia_step1_1",
        "instance": "poznan_sm",
        "x": f"{x}",
        "y": f"{y}",
        "lon": f"{x}",  # in the HAR lon=x and lat=y (server does not convert to WGS84)
        "lat": f"{y}",
        "srs": "EPSG:2177",
        "srs_id": "EPSG:2177",
        "id_ulica_city": "Poznań",
        "id_ulica_street_lookup": report.street_lookup,
        "goto_sm_zgloszenia_step1": "",
    }
    r = _post_multipart(step1_1_fields)
    r.raise_for_status()
    _log("POST step1_1 (map)", r)

    # 3. step1 → goto_step1_2 — render attachments screen (required before upload)
    r = _post_multipart({**step1_fields, "goto_sm_zgloszenia_step1_2": ""})
    r.raise_for_status()
    _log("POST step1 → attachments", r)

    # 4. step1_2 — upload (one POST per file). goto_step1_2 = "confirm attachment, stay on screen".
    #    Without this directive the file is uploaded but not committed to the ticket.
    for path in report.photos:
        with open(path, "rb") as fh:
            files = {
                "lhs": (None, "eurzad"),
                "source": (None, "sm_zgloszenia_step1_2"),
                "instance": (None, "poznan_sm"),
                "uz_file": (path.name, fh, "image/jpeg"),
                "goto_sm_zgloszenia_step1_2": (None, ""),
            }
            r = session.post(FORM_URL, files=files)
            r.raise_for_status()
            _log(f"POST step1_2 upload ({path.name})", r)

    # 5. step1_2 → goto_step1 — back to step1 (matches HAR navigation)
    r = session.post(
        FORM_URL,
        data={
            "lhs": "eurzad",
            "source": "sm_zgloszenia_step1_2",
            "instance": "poznan_sm",
            "goto_sm_zgloszenia_step1": "",
        },
    )
    r.raise_for_status()
    _log("POST step1_2 → step1", r)

    # 6. step1 → goto_summary — render summary screen, session ready to commit
    r = _post_multipart({**step1_fields, "goto_summary": ""})
    r.raise_for_status()
    _log("POST step1 → summary", r)

    if dry_run:
        responses.append(("DRY_RUN (stopped before SAVE)", 0, 0))
        return {"x": x, "y": y, "responses": responses, "submitted": False}

    # 7. summary — final commit
    summary_fields = {
        "action": "save",
        "source": "summary",
        "instance": "poznan_sm",
        "x": f"{x}",
        "y": f"{y}",
        "lon": f"{x}",
        "lat": f"{y}",
        "srs": "EPSG:2177",
        "goto_thanks": "",
    }
    r = session.post(
        FORM_URL, data=summary_fields
    )  # this step was application/x-www-form-urlencoded in the HAR
    r.raise_for_status()
    _log("POST summary (SAVE)", r)

    return {"x": x, "y": y, "responses": responses, "submitted": True}
