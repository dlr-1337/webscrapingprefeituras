from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

from src.coletar_paginas import PaginaColetada
from src.utils import load_yaml, normalize_for_search, project_path, strip_accents


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
    "acessar o conteudo",
    "prefeito secretarias",
    "secretarias autarquias",
    "orgaos municipais",
    "gestao administrativa",
    "cidade autarquias",
    "gabinete militar",
    "municipal de educacao",
    "ultimas noticias",
    "endereco",
    "contatos",
}

NOME_TOKEN_EXCLUDE = {
    "acessar",
    "administrativa",
    "autarquias",
    "cidade",
    "contato",
    "contatos",
    "conteudo",
    "diario",
    "educacao",
    "email",
    "endereco",
    "estado",
    "gabinete",
    "gestao",
    "municipais",
    "municipal",
    "orgaos",
    "portal",
    "prefeita",
    "prefeito",
    "secretaria",
    "secretarias",
    "secretario",
    "telefone",
    "transparencia",
}

NOME_PREFIXOS_INVALIDOS = {
    "casado",
    "cirurgiao",
    "foi",
    "servidor",
    "vereadora",
    "vereador",
}

CARGOS_EXECUTIVOS = {"Prefeito", "Vice-prefeito", "Chefe de gabinete"}

SECOES_RUIDOSAS = {
    "ultimas noticias",
    "ultimas notícias",
    "noticias recentes",
    "notícias recentes",
    "veja tambem",
    "veja também",
    "leia tambem",
    "leia também",
}

COL_ORGAO = "\u00d3rg\u00e3o/Secretaria"
COL_CARGO_AREA = "Cargo/\u00c1rea"
COL_CARGO_ORGAO = "Cargo/\u00d3rg\u00e3o"
COL_URL_ESPECIFICA = "URL espec\u00edfica"
COL_OBSERVACOES = "Observa\u00e7\u00f5es"
PROFILE_BLANK_LINE = "__PROFILE_BLANK_LINE__"
CONTATO_CONTINUACAO_PREFIXOS = (
    "contatos",
    "contato",
    "e-mail",
    "email",
    "telefone",
    "telefones",
    "fone",
    "celular",
    "whatsapp",
)


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


def _termo_cargo_presente(haystack: str, needle: str) -> bool:
    if not needle:
        return False

    candidates = {needle, needle.replace(" ", "-")}
    for candidate in candidates:
        escaped = re.escape(candidate)
        if candidate in {"prefeito", "prefeita"}:
            pattern = rf"(?<!vice-)(?<!vice )(?<![\w-]){escaped}(?![\w-])"
        else:
            pattern = rf"(?<![\w-]){escaped}(?![\w-])"
        if re.search(pattern, haystack):
            return True
    return False


def detectar_cargos(texto: str, cargos_config: dict[str, list[str]]) -> list[str]:
    haystack = normalize_for_search(texto)
    encontrados: list[str] = []
    for cargo_key, variacoes in cargos_config.items():
        for variacao in variacoes:
            needle = normalize_for_search(variacao)
            if _termo_cargo_presente(haystack, needle):
                encontrados.append(CARGO_LABELS.get(cargo_key, cargo_key.replace("_", " ").title()))
                break
    return list(dict.fromkeys(encontrados))


def _nome_valido(nome: str) -> bool:
    nome = str(nome or "").strip(" \t\n\r:-|,.;")
    if not nome or re.search(r"[@\d]", nome):
        return False
    normalized = normalize_for_search(nome)
    if any(term in normalized for term in NOME_EXCLUDE):
        return False
    if any(normalized.startswith(prefix) for prefix in NOME_PREFIXOS_INVALIDOS):
        return False
    normalized_parts = [
        normalize_for_search(part).strip(".,:;")
        for part in nome.split()
        if normalize_for_search(part).strip(".,:;") not in {"de", "da", "do", "dos", "das", "e"}
    ]
    if any(part in NOME_TOKEN_EXCLUDE for part in normalized_parts):
        return False
    return 2 <= len(normalized_parts) <= 6


def inferir_orgao_secretaria(cargo: str) -> str:
    lowered = normalize_for_search(cargo)
    if lowered.startswith(("secretaria", "agencia", "sala")):
        return cargo
    if cargo in {"Prefeito", "Vice-prefeito", "Chefe de gabinete"}:
        return "Gabinete/Prefeitura"
    if cargo == "Contato geral":
        return "Contato geral"
    return cargo


def _montar_resultado(
    cargo: str,
    nome: str,
    emails: list[str],
    fixos: list[str],
    celulares: list[str],
    url: str,
    status: str,
    observacoes: str = "",
) -> dict[str, str]:
    return {
        COL_ORGAO: inferir_orgao_secretaria(cargo),
        COL_CARGO_AREA: cargo,
        COL_CARGO_ORGAO: cargo,
        "Nome": nome,
        "E-mail": "; ".join(emails),
        "Telefone": "; ".join(fixos),
        "Celular/WhatsApp": "; ".join(celulares),
        "Celular": "; ".join(celulares),
        "URL da fonte": url,
        COL_URL_ESPECIFICA: url,
        "Status": status,
        COL_OBSERVACOES: observacoes,
    }


def _linhas_perfil(texto: str) -> list[str]:
    linhas: list[str] = []
    for raw_line in re.sub(r"\r\n?", "\n", texto or "").split("\n"):
        line = raw_line.strip()
        if line:
            linhas.append(line)
        elif linhas and linhas[-1] != PROFILE_BLANK_LINE:
            linhas.append(PROFILE_BLANK_LINE)
    while linhas and linhas[-1] == PROFILE_BLANK_LINE:
        linhas.pop()
    return linhas


def _trecho_perfil(lines: list[str], start: int, end: int) -> str:
    return "\n".join(line for line in lines[start:end] if line != PROFILE_BLANK_LINE)


def _proxima_linha_perfil(lines: list[str], start: int) -> str:
    for line in lines[start + 1 :]:
        if line != PROFILE_BLANK_LINE:
            return line
    return ""


def _linha_anterior_perfil(lines: list[str], start: int) -> str:
    for line in reversed(lines[:start]):
        if line != PROFILE_BLANK_LINE:
            return line
    return ""


def _linha_continua_contato(line: str) -> bool:
    normalized = normalize_for_search(line).strip()
    for prefix in CONTATO_CONTINUACAO_PREFIXOS:
        if normalized == prefix:
            return True
        match = re.match(rf"^{re.escape(prefix)}\s*[:\-\u2013\u2014]\s*(.*)$", normalized)
        if match:
            suffix = match.group(1).strip()
            return not suffix or bool(extrair_emails(suffix) or extrair_telefones(suffix))
    return False


def _linha_continua_biografia(line: str, nome: str) -> bool:
    normalized_line = normalize_for_search(line)
    normalized_nome = normalize_for_search(nome)
    return bool(normalized_nome and normalized_nome in normalized_line)


def _cargo_por_linha_curta(line: str, cargos_config: dict[str, list[str]]) -> str:
    text = str(line or "").strip(" \t:-\u2013\u2014")
    if not text or len(text) > 90 or re.search(r"[@\d.,;]", text):
        return ""

    normalized = normalize_for_search(text)
    normalized = re.sub(r"^(o|a)\s+", "", normalized)
    normalized_plain = normalized.replace("-", " ")

    for cargo_key, variacoes in cargos_config.items():
        label = CARGO_LABELS.get(cargo_key, cargo_key.replace("_", " ").title())
        candidates = {normalize_for_search(label).replace("-", " ")}
        candidates.update(normalize_for_search(variacao).replace("-", " ") for variacao in variacoes)
        if normalized_plain in candidates:
            return label
    return ""


def _cargo_pattern(candidate: str) -> str:
    tokens = [re.escape(token) for token in re.split(r"[\s-]+", candidate) if token]
    return r"[\s-]+".join(tokens)


def _cargo_no_inicio_info(line: str, cargos_config: dict[str, list[str]]) -> tuple[str, str]:
    cargo = _cargo_por_linha_curta(line, cargos_config)
    if cargo:
        return cargo, ""

    original = str(line or "").strip()
    normalized = strip_accents(original).lower()
    article_match = re.match(r"^(o|a)\s+", normalized)
    offset = article_match.end() if article_match else 0
    normalized = normalized[offset:]
    for cargo_key, variacoes in cargos_config.items():
        label = CARGO_LABELS.get(cargo_key, cargo_key.replace("_", " ").title())
        candidates = {normalize_for_search(label)}
        candidates.update(normalize_for_search(variacao) for variacao in variacoes)
        for candidate in candidates:
            candidate_pattern = _cargo_pattern(candidate)
            if not candidate_pattern:
                continue
            match = re.match(rf"^{candidate_pattern}\s*[:\-\u2013\u2014]\s*(.+)$", normalized)
            if match:
                tail = original[offset + match.start(1) :].strip(" \t:-\u2013\u2014")
                return label, tail
            match = re.match(rf"^{candidate_pattern}\s+(.+)$", normalized)
            if match:
                tail = original[offset + match.start(1) :].strip(" \t:-\u2013\u2014")
                if _nome_da_linha(tail):
                    return label, tail
    return "", ""


def _cargo_no_inicio_da_linha(line: str, cargos_config: dict[str, list[str]]) -> str:
    cargo, _ = _cargo_no_inicio_info(line, cargos_config)
    return cargo


def _nome_no_trecho(value: str) -> str:
    candidate = str(value or "").strip(" \t:-\u2013\u2014")
    for found in NAME_PATTERN.finditer(candidate):
        nome = found.group(1)
        if _nome_valido(nome):
            return nome
    return ""


def _nome_da_linha(line: str) -> str:
    candidate = str(line or "").strip(" \t:-\u2013\u2014")
    if not _nome_valido(candidate):
        return ""
    found = NAME_PATTERN.fullmatch(candidate)
    return found.group(1) if found else ""


def _fim_janela_perfil(
    lines: list[str],
    start: int,
    nome_index: int,
    nome_atual: str,
    cargo_atual: str,
    cargos_config: dict[str, list[str]],
) -> int:
    end = min(len(lines), start + 80)
    for index in range(nome_index + 1, end):
        if lines[index] == PROFILE_BLANK_LINE:
            proxima_linha = _proxima_linha_perfil(lines, index)
            if _linha_continua_contato(proxima_linha):
                continue

            trecho = _trecho_perfil(lines, start, index)
            if extrair_emails(trecho) or extrair_telefones(trecho):
                return index

            linha_anterior = _linha_anterior_perfil(lines, index)
            cargo_anterior = _cargo_no_inicio_da_linha(linha_anterior, cargos_config)
            if cargo_anterior == cargo_atual and _linha_continua_biografia(proxima_linha, nome_atual):
                continue

            return index

        normalized = normalize_for_search(lines[index])
        if any(normalized.startswith(section) for section in SECOES_RUIDOSAS):
            return index
        proximo_cargo = _cargo_no_inicio_da_linha(lines[index], cargos_config)
        if proximo_cargo and proximo_cargo != cargo_atual:
            return index
        if proximo_cargo and index > start + 4:
            trecho = _trecho_perfil(lines, start, index)
            if extrair_emails(trecho) or extrair_telefones(trecho):
                return index
    return end


def extrair_perfis_institucionais(
    texto: str,
    cargos_config: dict[str, list[str]],
    url: str,
) -> list[dict[str, str]]:
    linhas = _linhas_perfil(texto)
    resultados: list[dict[str, str]] = []

    for index, line in enumerate(linhas):
        if line == PROFILE_BLANK_LINE:
            continue

        cargo, nome_inline = _cargo_no_inicio_info(line, cargos_config)
        if not cargo:
            continue

        nome = _nome_no_trecho(nome_inline)
        nome_index = index
        if not nome:
            for candidate_index, candidate_line in enumerate(linhas[index + 1 : index + 5], start=index + 1):
                if candidate_line == PROFILE_BLANK_LINE:
                    continue

                proximo_cargo, proximo_nome_inline = _cargo_no_inicio_info(candidate_line, cargos_config)
                if proximo_cargo:
                    if proximo_cargo != cargo:
                        break
                    nome = _nome_no_trecho(proximo_nome_inline)
                    if nome:
                        nome_index = candidate_index
                        break
                    continue

                nome = _nome_da_linha(candidate_line)
                if nome:
                    nome_index = candidate_index
                    break
        if not nome:
            continue

        end = _fim_janela_perfil(linhas, index, nome_index, nome, cargo, cargos_config)
        trecho = _trecho_perfil(linhas, index, end)
        emails = extrair_emails(trecho)
        telefones = extrair_telefones(trecho)
        celulares = [phone for phone in telefones if telefone_eh_celular(phone)]
        fixos = [phone for phone in telefones if phone not in celulares]
        tem_contato = bool(emails or fixos or celulares)
        status = "Encontrado" if tem_contato else "Parcial"
        observacoes = "" if tem_contato else "Cargo ou nome identificado, mas sem contato direto no mesmo bloco."
        resultados.append(_montar_resultado(cargo, nome, emails, fixos, celulares, url, status, observacoes))

    return _deduplicar_resultados(resultados)


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


def _tem_contato_resultado(item: dict[str, str]) -> bool:
    return bool(item.get("E-mail") or item.get("Telefone") or item.get("Celular/WhatsApp") or item.get("Celular"))


def _registro_forte(item: dict[str, str]) -> bool:
    return item.get("Status") == "Encontrado" and bool(item.get("Nome")) and _tem_contato_resultado(item)


def _split_contatos(value: str) -> set[str]:
    return {part.strip().lower() for part in str(value or "").split(";") if part.strip()}


def _telefones_do_resultado(item: dict[str, str]) -> set[str]:
    telefones = set()
    for column in ("Telefone", "Celular/WhatsApp", "Celular"):
        telefones.update(_split_contatos(item.get(column, "")))
    return {digits for digits in (_digits(phone) for phone in telefones) if digits}


def _resultado_compartilha_contato(item: dict[str, str], emails: list[str], telefones: list[str]) -> bool:
    emails_bloco = {email.lower() for email in emails}
    if emails_bloco & _split_contatos(item.get("E-mail", "")):
        return True

    telefones_bloco = {digits for digits in (_digits(phone) for phone in telefones) if digits}
    return bool(telefones_bloco & _telefones_do_resultado(item))


def _resultado_cobre_todos_contatos(item: dict[str, str], emails: list[str], telefones: list[str]) -> bool:
    emails_bloco = {email.lower() for email in emails}
    telefones_bloco = {digits for digits in (_digits(phone) for phone in telefones) if digits}
    if not emails_bloco and not telefones_bloco:
        return False
    return emails_bloco <= _split_contatos(item.get("E-mail", "")) and telefones_bloco <= _telefones_do_resultado(item)


def _bloco_executivo_parece_manchete(bloco: str, cargo: str) -> bool:
    cargo_pattern = _cargo_pattern(normalize_for_search(cargo))
    original = str(bloco or "").strip()
    normalized = strip_accents(original).lower()
    match = re.match(rf"^{cargo_pattern}\s+(.+)$", normalized)
    if not match:
        return False
    tail = original[match.start(1) :].strip()
    found = NAME_PATTERN.match(tail)
    if not found or not _nome_valido(found.group(1)):
        return False
    return not bool(_nome_da_linha(tail))


def _deduplicar_resultados(resultados: list[dict[str, str]]) -> list[dict[str, str]]:
    strong_keys = {
        (item.get("URL da fonte", ""), item.get(COL_CARGO_ORGAO, ""))
        for item in resultados
        if _registro_forte(item)
    }

    deduplicados: list[dict[str, str]] = []
    vistos: set[tuple[str, ...]] = set()
    for item in resultados:
        key = (item.get("URL da fonte", ""), item.get(COL_CARGO_ORGAO, ""))
        if key in strong_keys and not _registro_forte(item):
            continue

        item_key = (
            item.get(COL_CARGO_ORGAO, ""),
            item.get("Nome", ""),
            item.get("E-mail", ""),
            item.get("Telefone", ""),
            item.get("Celular/WhatsApp", ""),
            item.get("URL da fonte", ""),
            item.get("Status", ""),
        )
        if item_key in vistos:
            continue
        vistos.add(item_key)
        deduplicados.append(item)
    return deduplicados


def extrair_contatos_de_texto(
    texto: str,
    cargos_config: dict[str, list[str]] | None = None,
    url: str = "",
) -> list[dict[str, str]]:
    cargos_config = cargos_config or carregar_cargos()
    estruturados = extrair_perfis_institucionais(texto, cargos_config, url)
    estruturados_fortes = [item for item in estruturados if _registro_forte(item)]
    executivos_fortes = [
        item
        for item in estruturados_fortes
        if item.get(COL_CARGO_ORGAO) in CARGOS_EXECUTIVOS
    ]
    cargos_executivos_fortes = {item.get(COL_CARGO_ORGAO, "") for item in executivos_fortes}
    resultados: list[dict[str, str]] = list(estruturados)

    for bloco in dividir_blocos(texto):
        emails = extrair_emails(bloco)
        telefones = extrair_telefones(bloco)
        celulares = [phone for phone in telefones if telefone_eh_celular(phone)]
        fixos = [phone for phone in telefones if phone not in celulares]
        cargos_detectados = detectar_cargos(bloco, cargos_config)
        bloco_duplica_estruturado_forte = any(
            _resultado_cobre_todos_contatos(item, emails, telefones)
            for item in estruturados_fortes
        )
        bloco_duplica_executivo_forte = any(
            _resultado_cobre_todos_contatos(item, emails, telefones)
            for item in executivos_fortes
        )
        cargos = [
            cargo
            for cargo in cargos_detectados
            if not (
                cargo in CARGOS_EXECUTIVOS
                and (cargo in cargos_executivos_fortes or bloco_duplica_executivo_forte)
            )
        ]
        nome = extrair_nome_proximo(bloco, cargos_config) if cargos else ""
        if cargos:
            cargos_validos = [
                cargo
                for cargo in cargos
                if not (
                    cargo in CARGOS_EXECUTIVOS
                    and not nome
                    and _bloco_executivo_parece_manchete(bloco, cargo)
                )
            ]
            if cargos and not cargos_validos:
                cargos_detectados = []
            cargos = cargos_validos

        if cargos_detectados and not cargos:
            continue
        if not cargos and not cargos_detectados and (emails or telefones):
            if bloco_duplica_estruturado_forte:
                continue
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

            resultados.append(_montar_resultado(cargo, nome, emails, fixos, celulares, url, status, observacoes))

    return _deduplicar_resultados(resultados)


def extrair_contatos_paginas(
    paginas: Iterable[PaginaColetada],
    cargos_config: dict[str, list[str]] | None = None,
) -> list[dict[str, str]]:
    cargos_config = cargos_config or carregar_cargos()
    resultados: list[dict[str, str]] = []
    for pagina in paginas:
        resultados.extend(extrair_contatos_de_texto(pagina.texto, cargos_config, pagina.url))
    return resultados
