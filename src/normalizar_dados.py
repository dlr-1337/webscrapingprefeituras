from __future__ import annotations

import re
from typing import Iterable

import pandas as pd

from src.utils import clean_url


STATUS_PERMITIDOS = {
    "Encontrado",
    "Parcial",
    "Não encontrado",
    "Site fora do ar",
    "Site não localizado",
    "Página sem informação pública",
    "Bloqueio técnico",
    "Necessita validação manual",
    "Não publicado",
}

STATUS_ASCII_MAP = {
    "nao encontrado": "Não encontrado",
    "site nao localizado": "Site não localizado",
    "pagina sem informacao publica": "Página sem informação pública",
    "bloqueio tecnico": "Bloqueio técnico",
    "necessita validacao manual": "Necessita validação manual",
    "nao publicado": "Não publicado",
}

PARTICULAS_NOME = {"da", "de", "do", "das", "dos", "e"}


def normalizar_uf(value: object) -> str:
    return str(value or "").strip().upper()


def normalizar_municipio(value: object) -> str:
    words = str(value or "").strip().lower().split()
    normalized: list[str] = []
    for index, word in enumerate(words):
        if index > 0 and word in PARTICULAS_NOME:
            normalized.append(word)
        else:
            normalized.append("-".join(part.capitalize() for part in word.split("-")))
    return " ".join(normalized)


def normalizar_email(value: object) -> str:
    parts = [part.strip().lower() for part in str(value or "").split(";") if part.strip()]
    return "; ".join(dict.fromkeys(parts))


def normalizar_telefone(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if ";" in text:
        return "; ".join(dict.fromkeys(normalizar_telefone(part) for part in text.split(";") if part.strip()))

    digits = re.sub(r"\D", "", text)
    if digits.startswith("55") and len(digits) in {12, 13}:
        digits = digits[2:]

    if len(digits) == 11:
        return f"({digits[:2]}) {digits[2:7]}-{digits[7:]}"
    if len(digits) == 10:
        return f"({digits[:2]}) {digits[2:6]}-{digits[6:]}"
    if len(digits) == 9:
        return f"{digits[:5]}-{digits[5:]}"
    if len(digits) == 8:
        return f"{digits[:4]}-{digits[4:]}"
    return text


def normalizar_status(value: object) -> str:
    text = str(value or "").strip()
    if text in STATUS_PERMITIDOS:
        return text
    ascii_key = (
        text.lower()
        .replace("ã", "a")
        .replace("á", "a")
        .replace("â", "a")
        .replace("ç", "c")
        .replace("é", "e")
        .replace("ê", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("õ", "o")
        .replace("ú", "u")
    )
    return STATUS_ASCII_MAP.get(ascii_key, "Necessita validação manual")


def normalizar_cargo(value: object) -> str:
    text = str(value or "").strip()
    return text or "Contato geral"


def _inferir_orgao_secretaria(value: object) -> str:
    cargo = normalizar_cargo(value)
    lowered = cargo.lower()
    if lowered.startswith(("secretaria", "agência", "agencia", "sala")):
        return cargo
    if cargo in {"Prefeito", "Vice-prefeito", "Chefe de gabinete"}:
        return "Gabinete/Prefeitura"
    if cargo == "Contato geral":
        return "Contato geral"
    return cargo


def normalizar_resultados(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    for column in ("UF", "Estado", "Município", "Município/Capital", "População", "Critério de inclusão", "Esfera", "Site oficial"):
        if column not in result.columns:
            result[column] = ""
    for column in (
        "Órgão/Secretaria",
        "Cargo/Área",
        "Cargo/Órgão",
        "Nome",
        "E-mail",
        "Telefone",
        "Celular/WhatsApp",
        "Celular",
        "URL da fonte",
        "URL específica",
        "Data da coleta",
        "Status",
        "Observações",
    ):
        if column not in result.columns:
            result[column] = ""

    result["UF"] = result["UF"].apply(normalizar_uf)
    result["Município"] = result["Município"].apply(normalizar_municipio)
    result["Município/Capital"] = result["Município/Capital"].where(
        result["Município/Capital"].astype(str).str.strip().ne(""),
        result["Município"],
    )
    result["Esfera"] = result["Esfera"].where(result["Esfera"].astype(str).str.strip().ne(""), "Municipal")
    result["E-mail"] = result["E-mail"].apply(normalizar_email)
    result["Telefone"] = result["Telefone"].apply(normalizar_telefone)
    result["Celular"] = result["Celular"].apply(normalizar_telefone)
    result["Celular/WhatsApp"] = result["Celular/WhatsApp"].where(
        result["Celular/WhatsApp"].astype(str).str.strip().ne(""),
        result["Celular"],
    )
    result["Celular/WhatsApp"] = result["Celular/WhatsApp"].apply(normalizar_telefone)
    result["Cargo/Órgão"] = result["Cargo/Órgão"].apply(normalizar_cargo)
    result["Cargo/Área"] = result["Cargo/Área"].where(
        result["Cargo/Área"].astype(str).str.strip().ne(""),
        result["Cargo/Órgão"],
    )
    result["Cargo/Área"] = result["Cargo/Área"].apply(normalizar_cargo)
    result["Órgão/Secretaria"] = result["Órgão/Secretaria"].where(
        result["Órgão/Secretaria"].astype(str).str.strip().ne(""),
        result["Cargo/Área"].apply(_inferir_orgao_secretaria),
    )
    result["URL específica"] = result["URL específica"].apply(clean_url)
    result["URL da fonte"] = result["URL da fonte"].where(
        result["URL da fonte"].astype(str).str.strip().ne(""),
        result["URL específica"],
    )
    result["URL da fonte"] = result["URL da fonte"].apply(clean_url)
    result["Site oficial"] = result["Site oficial"].apply(clean_url)
    result["Status"] = result["Status"].apply(normalizar_status)
    return deduplicar_contatos(result)


def deduplicar_contatos(df: pd.DataFrame) -> pd.DataFrame:
    subset = ["UF", "Município/Capital", "Esfera", "Cargo/Área", "Nome", "E-mail", "Telefone", "Celular/WhatsApp", "URL da fonte"]
    available = [column for column in subset if column in df.columns]
    return df.drop_duplicates(subset=available, keep="first").reset_index(drop=True)
