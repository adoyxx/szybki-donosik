from __future__ import annotations

import sys
from pathlib import Path

import folium
import streamlit as st
from streamlit_folium import st_folium
from streamlit_js_eval import get_geolocation

sys.path.insert(0, str(Path(__file__).parent / "src"))

from image_utils import compress_for_upload  # noqa: E402
from llm import PhotoAnalysis, analyze_photo  # noqa: E402
from location import reverse_geocode, wgs84_to_epsg2177  # noqa: E402
from profile_storage import Profile, load_profile, save_profile  # noqa: E402
from violations import LABELS, build_body, build_subject, sm_category_for  # noqa: E402

st.set_page_config(
    page_title="Szybki Donosik", page_icon="🅿️", layout="centered"
)
st.title("🅿️ Szybki Donosik")
st.caption("Zgłoś szybko i wygodnie patoparkowanie do Straży Miejskiej w Poznaniu")

# ---- session state ----
ss = st.session_state
ss.setdefault("image_bytes", None)
ss.setdefault("photo_id", None)
ss.setdefault("photo_raw_size", 0)
ss.setdefault("analysis", None)
ss.setdefault("address", "")
ss.setdefault("lat", None)
ss.setdefault("lon", None)
ss.setdefault("gps_accuracy", None)
ss.setdefault("gps_asked", False)
ss.setdefault("last_gps_lat", None)
ss.setdefault("last_gps_lon", None)
ss.setdefault("subject", None)
ss.setdefault("body", None)
ss.setdefault("template_fingerprint", None)

# ---- Profile (persisted in cookies) ----
saved = load_profile()
with st.expander(
    "👤 Twoje dane (zapamiętane w przeglądarce)", expanded=not saved.email
):
    email = st.text_input(
        "E-mail (wymagany przez SM)", value=saved.email, placeholder="ty@example.com"
    )
    full_name = st.text_input("Imię i nazwisko (opcjonalnie)", value=saved.full_name)
    if st.button("💾 Zapisz w ciasteczkach"):
        save_profile(Profile(email=email.strip(), full_name=full_name.strip()))
        st.success(
            "Zapisane. Przy kolejnej wizycie pola będą wypełnione automatycznie."
        )
ss.email = email
ss.full_name = full_name


# ---- 1. Photo ----
st.header("1. Zdjęcie")
photo = st.camera_input("Zrób zdjęcie") or st.file_uploader(
    "…lub wgraj z galerii", type=["jpg", "jpeg", "png"]
)
if photo is not None and getattr(photo, "file_id", None) != ss.photo_id:
    ss.photo_id = photo.file_id
    raw = photo.getvalue()
    ss.photo_raw_size = len(raw)
    with st.spinner("Kompresuję zdjęcie…"):
        ss.image_bytes = compress_for_upload(raw)
    ss.analysis = None

if ss.image_bytes:
    st.caption(
        f"Zdjęcie: {ss.photo_raw_size / 1024:.0f} KB → {len(ss.image_bytes) / 1024:.0f} KB po kompresji"
    )

if ss.image_bytes:
    st.image(ss.image_bytes, caption="Wybrane zdjęcie", width="stretch")


# ---- 2. Violation ----
st.header("2. Wykroczenie")

if ss.analysis is None:
    ss.analysis = PhotoAnalysis(violation="other")

if st.button(
    "🤖 Przeanalizuj z AI",
    type="primary",
    width="stretch",
    disabled=ss.image_bytes is None,
):
    with st.spinner("Model analizuje zdjęcie…"):
        ss.analysis = analyze_photo(ss.image_bytes)

a: PhotoAnalysis = ss.analysis
col1, col2 = st.columns(2)
a.license_plate = col1.text_input("Numer rejestracyjny", value=a.license_plate or "")
a.make = col2.text_input("Marka", value=a.make or "")
a.color = col1.text_input("Kolor (informacyjnie)", value=a.color or "")
violation_keys = list(LABELS.keys())
a.violation = col2.selectbox(  # type: ignore[assignment]
    "Typ naruszenia",
    options=violation_keys,
    index=violation_keys.index(a.violation),
    format_func=lambda v: LABELS[v],
)


# ---- 3. Location ----
st.header("3. Lokalizacja")
if st.button("📍 Pobierz lokalizację", width="stretch"):
    ss.gps_asked = True

if ss.gps_asked:
    loc = get_geolocation(component_key="konfident_gps")
    if loc and isinstance(loc, dict) and loc.get("coords"):
        coords = loc["coords"]
        gps_lat = float(coords["latitude"])
        gps_lon = float(coords["longitude"])
        # Only apply a GPS reading once. Otherwise it would overwrite manual
        # map clicks on every rerun (the JS component keeps returning the
        # same cached reading until the user re-clicks the GPS button).
        if ss.last_gps_lat != gps_lat or ss.last_gps_lon != gps_lon:
            ss.last_gps_lat, ss.last_gps_lon = gps_lat, gps_lon
            ss.lat, ss.lon = gps_lat, gps_lon
            ss.gps_accuracy = coords.get("accuracy")
            addr = reverse_geocode(round(gps_lat, 6), round(gps_lon, 6))
            if addr and addr.display:
                ss.address = addr.display
    elif loc is None:
        st.caption("Czekam na zgodę przeglądarki…")

# Interactive OSM map — click anywhere to drop / move the pin.
# Default center = Poznań Old Market if no location set yet.
st.caption("Kliknij w mapę, żeby ustawić pinezkę precyzyjnie.")
map_center = [ss.lat or 52.4064, ss.lon or 16.9252]
fmap = folium.Map(
    location=map_center, zoom_start=17 if ss.lat else 13, tiles="OpenStreetMap"
)
if ss.lat is not None and ss.lon is not None:
    # CircleMarker doesn't swallow clicks the way default Marker does.
    folium.CircleMarker(
        [ss.lat, ss.lon],
        radius=8,
        color="red",
        fill=True,
        fill_opacity=0.9,
        tooltip="Zgłaszane miejsce",
    ).add_to(fmap)
map_result = st_folium(
    fmap,
    height=380,
    width="stretch",
    key="location_picker",
)

clicked = (map_result or {}).get("last_clicked")
if clicked and clicked.get("lat") is not None:
    new_lat, new_lon = float(clicked["lat"]), float(clicked["lng"])
    if ss.lat != new_lat or ss.lon != new_lon:
        ss.lat, ss.lon = new_lat, new_lon
        ss.gps_accuracy = None
        addr = reverse_geocode(round(new_lat, 6), round(new_lon, 6))
        if addr and addr.display:
            ss.address = addr.display
        st.rerun()

if ss.lat is not None and ss.lon is not None:
    x, y = wgs84_to_epsg2177(ss.lat, ss.lon)
    acc_str = f", dokładność ≈ {ss.gps_accuracy:.0f} m" if ss.gps_accuracy else ""
    st.caption(
        f"GPS: {ss.lat:.6f}, {ss.lon:.6f}{acc_str}  →  EPSG:2177 x={x:.0f}, y={y:.0f}"
    )
    sm_url = f"https://www.poznan.pl/mim/public/plan/plan.html?&srs=EPSG:2177&lat={y}&lon={x}"
    st.markdown(f"🔍 [Sprawdź na planie Poznania (jak widzi SM)]({sm_url})")

ss.address = st.text_input(
    "Adres / opis lokalizacji (edytowalny)",
    value=ss.address,
    placeholder="np. ul. Św. Marcin 24, Poznań",
)


# ---- 4. Preview ----
st.header("4. Podgląd zgłoszenia (nic nie jest wysyłane)")

# Refresh template whenever any upstream field changes. Manual edits between
# changes persist; the moment marka / tablica / typ / kolor / adres changes,
# subject and body are recomputed from the template.
fingerprint = (
    a.violation,
    a.make or "",
    a.license_plate or "",
    a.color or "",
    ss.address or "",
)
if ss.template_fingerprint != fingerprint:
    ss.template_fingerprint = fingerprint
    ss.subject = build_subject(a.violation)
    ss.body = build_body(
        a.violation,
        a.make or None,
        a.license_plate or None,
        a.color or None,
        ss.address or None,
    )

cat = sm_category_for(a.violation)
ss.subject = st.text_input("Temat", value=ss.subject)
ss.body = st.text_area("Treść", value=ss.body, height=140)

st.markdown(
    f"""
**Kategoria SM:** `{cat}` ({"niszczenie zieleni" if cat == "17402" else "ruch drogowy - parkowanie"})

**E-mail:** {ss.email or "_(nie podano)_"}

**Imię i nazwisko:** {ss.full_name or "_(nie podano)_"}

**Załącznik:** {"1 zdjęcie" if ss.image_bytes else "brak"}
"""
)
st.info("Integracja z formularzem SM nie jest jeszcze włączona.")
