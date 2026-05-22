from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, urlunparse

import yaml


ROOT_DIR = Path(__file__).resolve().parent.parent

UF_TO_ESTADO: dict[str, str] = {
    "AC": "Acre",
    "AL": "Alagoas",
    "AP": "Amapá",
    "AM": "Amazonas",
    "BA": "Bahia",
    "CE": "Ceará",
    "DF": "Distrito Federal",
    "ES": "Espírito Santo",
    "GO": "Goiás",
    "MA": "Maranhão",
    "MT": "Mato Grosso",
    "MS": "Mato Grosso do Sul",
    "MG": "Minas Gerais",
    "PA": "Pará",
    "PB": "Paraíba",
    "PR": "Paraná",
    "PE": "Pernambuco",
    "PI": "Piauí",
    "RJ": "Rio de Janeiro",
    "RN": "Rio Grande do Norte",
    "RS": "Rio Grande do Sul",
    "RO": "Rondônia",
    "RR": "Roraima",
    "SC": "Santa Catarina",
    "SP": "São Paulo",
    "SE": "Sergipe",
    "TO": "Tocantins",
}

ESTADO_TO_UF: dict[str, str] = {
    unicodedata.normalize("NFKD", estado).encode("ascii", "ignore").decode("ascii").lower(): uf
    for uf, estado in UF_TO_ESTADO.items()
}

CAPITAIS: dict[str, str] = {
    "AC": "Rio Branco",
    "AL": "Maceió",
    "AP": "Macapá",
    "AM": "Manaus",
    "BA": "Salvador",
    "CE": "Fortaleza",
    "DF": "Brasília",
    "ES": "Vitória",
    "GO": "Goiânia",
    "MA": "São Luís",
    "MT": "Cuiabá",
    "MS": "Campo Grande",
    "MG": "Belo Horizonte",
    "PA": "Belém",
    "PB": "João Pessoa",
    "PR": "Curitiba",
    "PE": "Recife",
    "PI": "Teresina",
    "RJ": "Rio de Janeiro",
    "RN": "Natal",
    "RS": "Porto Alegre",
    "RO": "Porto Velho",
    "RR": "Boa Vista",
    "SC": "Florianópolis",
    "SP": "São Paulo",
    "SE": "Aracaju",
    "TO": "Palmas",
}


def project_path(*parts: str) -> Path:
    return ROOT_DIR.joinpath(*parts)


def ensure_project_dirs() -> None:
    for relative in ("data/input", "data/output", "data/temp", "config", "logs", "src", "tests"):
        project_path(relative).mkdir(parents=True, exist_ok=True)


def load_yaml(path: str | Path) -> Any:
    with Path(path).open("r", encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


def strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(value))
    return "".join(char for char in normalized if not unicodedata.combining(char))


def normalize_key(value: str) -> str:
    value = strip_accents(str(value)).lower().strip()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return value.strip("_")


def normalize_for_search(value: str) -> str:
    value = strip_accents(str(value)).lower()
    return re.sub(r"\s+", " ", value).strip()


def parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    text = normalize_for_search(str(value))
    return text in {"1", "s", "sim", "true", "t", "yes", "y", "capital"}


def parse_int(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    digits = re.sub(r"[^0-9]", "", str(value))
    return int(digits) if digits else 0


def uf_from_estado(value: str) -> str:
    text = str(value).strip().upper()
    if text in UF_TO_ESTADO:
        return text
    return ESTADO_TO_UF.get(normalize_for_search(text), "")


def estado_from_uf(uf: str) -> str:
    return UF_TO_ESTADO.get(str(uf).strip().upper(), "")


def is_capital(municipio: str, uf: str) -> bool:
    capital = CAPITAIS.get(str(uf).strip().upper())
    return bool(capital and normalize_for_search(capital) == normalize_for_search(municipio))


def slugify_municipio(value: str) -> str:
    text = normalize_for_search(value)
    text = re.sub(r"[^a-z0-9]+", "", text)
    return text


def clean_url(value: Any) -> str:
    if value is None:
        return ""
    url = str(value).strip()
    if not url or url.lower() in {"nan", "none"}:
        return ""
    url = re.sub(r"\s+", "", url)
    if not re.match(r"^https?://", url, flags=re.IGNORECASE):
        url = f"https://{url}"
    parsed = urlparse(url)
    if not parsed.netloc:
        return ""
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    path = parsed.path or "/"
    return urlunparse((scheme, netloc, path, "", parsed.query, ""))


def same_domain(url: str, base_url: str) -> bool:
    url_host = urlparse(url).netloc.lower().removeprefix("www.")
    base_host = urlparse(base_url).netloc.lower().removeprefix("www.")
    return bool(url_host and base_host and (url_host == base_host or url_host.endswith(f".{base_host}")))

