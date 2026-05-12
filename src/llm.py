from __future__ import annotations

import base64
import os
from functools import lru_cache

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from violations import ViolationType

load_dotenv()


@lru_cache(maxsize=1)
def get_model() -> BaseChatModel:
    provider = os.getenv("LLM_PROVIDER", "mistralai")
    model = os.getenv("LLM_MODEL", "mistral-medium-latest")
    return init_chat_model(model=model, model_provider=provider, temperature=0.2)


class PhotoAnalysis(BaseModel):
    license_plate: str | None = Field(
        default=None,
        description="Numer rejestracyjny pojazdu odczytany ze zdjęcia, bez spacji. None jeśli nieczytelny.",
    )
    make: str | None = Field(
        default=None, description="Marka pojazdu, np. 'Toyota'. None jeśli nieznana."
    )
    color: str | None = Field(
        default=None,
        description="Kolor pojazdu po polsku, np. 'srebrny'. None jeśli niejasny.",
    )
    violation: ViolationType = Field(
        description="Typ naruszenia. 'other' jeśli żaden z konkretnych nie pasuje."
    )


_ANALYZE_SYSTEM = (
    "Jesteś klasyfikatorem zdjęć nieprawidłowo zaparkowanych pojazdów. "
    "Zwracasz wyłącznie ustrukturyzowane dane: markę, numer rejestracyjny, kolor i typ naruszenia. "
    "Jeśli czegoś nie widać wyraźnie — użyj wartości null zamiast zgadywać. Nie pisz prozy."
)


def _image_to_data_url(image_bytes: bytes, mime: str = "image/jpeg") -> str:
    b64 = base64.b64encode(image_bytes).decode("ascii")
    return f"data:{mime};base64,{b64}"


def analyze_photo(image_bytes: bytes, mime: str = "image/jpeg") -> PhotoAnalysis:
    """Vision call — returns structured analysis of the parking violation in the photo."""
    model = get_model().with_structured_output(PhotoAnalysis)
    message = HumanMessage(
        content=[
            {
                "type": "text",
                "text": "Przeanalizuj to zdjęcie nieprawidłowego parkowania.",
            },
            {
                "type": "image_url",
                "image_url": {"url": _image_to_data_url(image_bytes, mime)},
            },
        ]
    )
    return model.invoke([SystemMessage(content=_ANALYZE_SYSTEM), message])  # type: ignore[return-value]
