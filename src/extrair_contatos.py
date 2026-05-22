from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

from src.coletar_paginas import PaginaColetada
from src.utils import load_yaml, normalize_for_search, project_path


EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PHONE_PATTERN = re.compile(
    r"(?<!\d)(?:\+?55\s*)?(?:\(?([1-9]{2})\)?\s*)?(9?\d{4})[\s.\-]?(\d{4})(?!\d)"
)
NAME_PATTERN = re.compile(
    r"\b([A-ZÁÀÂÃÉÈÊÍÌÓÒÔÕÚÙÇ][a-záàâãéèêíìóòôõúùç']+"
    r"(?:\s+(?:de|da|do|dos|das|e))?"
    r"(?:\s+[A-ZÁÀÂÃÉÈÊÍÌÓÒÔÕÚÙÇ][a-záàâãéèêíìóòôõúùç']+){1,5})\b"
)

CARGO_LABELS = {
    "prefeito": "Prefeito",
    "vice_prefeito": "Vice-prefeito",
    "chefe_gabinete": "Chefe de gabinete",
    "desenvolvimento_economico": "Secretaria de Desenvolvimento Econômico",
    "desenvolvimento": "Secretaria de Desenvolvimento",
    "financas_fazenda": "Secretaria de Finanças/Fazenda",
    "planejamento": "Secretaria de Planejamento",
    "agencia_desenvolvimento": "Agência/Sala de Desenvolvimento",
}

NOME_EXCLUDE = {
    "prefeitura municipal",
    "secretaria municipal",
    "desenvolvimento economico",
    "sala do empreendedor",
    "fale conosco",
    "portal da transparencia",
    "diario oficial",
}


def carregar_cargos(path: str | Path | None = None) -> dict[str, list[str]]:
    config_path = Path(path) if path else project_path("config", "cargos.yml")
    data = load_yaml(config_path)
    return {str(key): [str(item) for item in value or []] for key, value in data.items()}


def extrair_emails(texto: str) -> list[str]:
    emails = [email.lower() for email in EMAIL_PATTERN.findall(texto or "")]
    return list(dict.fromkeys(emails))


def extrair_telefones(texto: str) -> list[str]:
    telefones: list[str] = []
    for match in PHONE_PATTERN.finditer(texto or ""):
        telefones.append(match.group(0).strip())
    return list(dict.fromkeys(telefones))


def _digits(value: str) -> str:
    digits = re.sub(r"\D", "", value or "")
    if digits.startswith("55") and len(digits) in {12, 13}:
        digits = digits[2:]
    return digits


def telefone_eh_celular(value: str) -> bool:
    digits = _digits(value)
    if len(digits) == 11:
        return digits[2] == "9"
    if len(digits) == 9:
        return digits[0] == "9"
    return False


def extrair_celulares(texto: str) -> list[str]:
    return [phone for phone in extrair_telefones(texto) if telefone_eh_celular(phone)]


def dividir_blocos(texto: str) -> list[str]:
    text = re.sub(r"\r\n?", "\n", texto or "")
    raw_blocks = re.split(r"\n{2,}", text)
    blocks: list[str] = []
    for raw in raw_blocks:
        lines = [line.strip() for line in raw.splitlines() if line.strip()]
        if not lines:
            continue
        if len(" ".join(lines)) > 1200:
            blocks.extend(" ".join(lines[i : i + 8]) for i in range(0, len(lines), 8))
        else:
            blocks.append(" ".join(lines))
    return blocks or [text]


def detectar_cargos(texto: str, cargos_config: dict[str, list[str]]) -> list[str]:
    haystack = normalize_for_search(texto)
    encontrados: list[str] = []
    for cargo_key, variacoes in cargos_config.items():
        for variacao in variacoes:
            needle = normalize_for_search(variacao)
            if needle and needle in haystack:
                encontrados.append(CARGO_LABELS.get(cargo_key, cargo_key.replace("_", " ").title()))
                break
    return list(dict.fromkeys(encontrados))


def _nome_valido(nome: str) -> bool:
    normalized = normalize_for_search(nome)
    if any(term in normalized for term in NOME_EXCLUDE):
        return False
    parts = [part for part in nome.split() if normalize_for_search(part) not in {"de", "da", "do", "dos", "das", "e"}]
    return len(parts) >= 2


def inferir_orgao_secretaria(cargo: str) -> str:
    lowered = normalize_for_search(cargo)
    if lowered.startswith(("secretaria", "agencia", "sala")):
        return cargo
    if cargo in {"Prefeito", "Vice-prefeito", "Chefe de gabinete"}:
        return "Gabinete/Prefeitura"
    if cargo == "Contato geral":
        return "Contato geral"
    return cargo


def extrair_nome_proximo(texto: str, cargos_config: dict[str, list[str]]) -> str:
    block = texto or ""

    nome_match = re.search(r"\bnome\s*[:\-]\s*([A-ZÁÀÂÃÉÈÊÍÌÓÒÔÕÚÙÇ][^\n|;,.]{4,80})", block)
    if nome_match:
        candidate = nome_match.group(1).strip()
        found = NAME_PATTERN.search(candidate)
        if found and _nome_valido(found.group(1)):
            return found.group(1)

    normalized_block = normalize_for_search(block)
    for variacoes in cargos_config.values():
        for variacao in variacoes:
            normalized_variacao = normalize_for_search(variacao)
            index = normalized_block.find(normalized_variacao)
            if index < 0:
                continue
            window = block[index : index + 260]
            colon_match = re.search(r"[:\-]\s*([A-ZÁÀÂÃÉÈÊÍÌÓÒÔÕÚÙÇ][^\n|;,.]{4,80})", window)
            if colon_match:
                found = NAME_PATTERN.search(colon_match.group(1))
                if found and _nome_valido(found.group(1)):
                    return found.group(1)
            for found in NAME_PATTERN.finditer(window):
                candidate = found.group(1)
                if _nome_valido(candidate):
                    return candidate

    for found in NAME_PATTERN.finditer(block[:300]):
        candidate = found.group(1)
        if _nome_valido(candidate):
            return candidate
    return ""


def extrair_contatos_de_texto(
    texto: str,
    cargos_config: dict[str, list[str]] | None = None,
    url: str = "",
) -> list[dict[str, str]]:
    cargos_config = cargos_config or carregar_cargos()
    resultados: list[dict[str, str]] = []

    for bloco in dividir_blocos(texto):
        emails = extrair_emails(bloco)
        telefones = extrair_telefones(bloco)
        celulares = [phone for phone in telefones if telefone_eh_celular(phone)]
        fixos = [phone for phone in telefones if phone not in celulares]
        cargos = detectar_cargos(bloco, cargos_config)
        nome = extrair_nome_proximo(bloco, cargos_config) if cargos else ""

        if not cargos and (emails or telefones):
            cargos = ["Contato geral"]

        if not cargos:
            continue

        tem_contato = bool(emails or fixos or celulares)
        if not tem_contato and not nome:
            continue

        for cargo in cargos:
            contato_geral = cargo == "Contato geral"
            status = "Encontrado" if tem_contato and not contato_geral else "Parcial"
            observacoes = ""
            if contato_geral:
                observacoes = "Contato geral sem associação clara a cargo específico."
            elif not tem_contato:
                observacoes = "Cargo ou nome identificado, mas sem contato direto no mesmo bloco."

            resultados.append(
                {
                    "Órgão/Secretaria": inferir_orgao_secretaria(cargo),
                    "Cargo/Área": cargo,
                    "Cargo/Órgão": cargo,
                    "Nome": nome,
                    "E-mail": "; ".join(emails),
                    "Telefone": "; ".join(fixos),
                    "Celular/WhatsApp": "; ".join(celulares),
                    "Celular": "; ".join(celulares),
                    "URL da fonte": url,
                    "URL específica": url,
                    "Status": status,
                    "Observações": observacoes,
                }
            )

    return resultados


def extrair_contatos_paginas(
    paginas: Iterable[PaginaColetada],
    cargos_config: dict[str, list[str]] | None = None,
) -> list[dict[str, str]]:
    cargos_config = cargos_config or carregar_cargos()
    resultados: list[dict[str, str]] = []
    for pagina in paginas:
        resultados.extend(extrair_contatos_de_texto(pagina.texto, cargos_config, pagina.url))
    return resultados
