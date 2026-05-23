from __future__ import annotations

import argparse
import random
import re
from datetime import datetime
from pathlib import Path
from typing import Callable

import pandas as pd

from src.coletar_paginas import _baixar, _baixar_com_navegador, criar_sessao, html_para_texto
from src.escopo_categorias import CATEGORIA_IDENTIFICACAO
from src.extrair_contatos import _nome_valido
from src.utils import normalize_for_search


CAMPOS_CONFERENCIA = ("Nome", "E-mail", "Telefone", "Celular/WhatsApp")
STATUS_CONFERENCIA = {"Encontrado", "Parcial"}


def _row_get(row: pd.Series, *names: str) -> object:
    for name in names:
        if name in row:
            return row.get(name, "")
    normalized = {normalize_for_search(str(key)): key for key in row.index}
    for name in names:
        key = normalized.get(normalize_for_search(name))
        if key is not None:
            return row.get(key, "")
    return ""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Valida registros da planilha contra URLs oficiais usando navegador.")
    parser.add_argument("excel", help="Caminho da planilha final .xlsx.")
    parser.add_argument("--output", dest="output_path", help="Relatório XLSX de validação.")
    parser.add_argument("--max-linhas", type=int, default=40, help="Quantidade máxima de linhas a validar. Use 0 para validar todas.")
    parser.add_argument("--seed", type=int, default=42, help="Semente da amostragem reprodutível.")
    parser.add_argument("--timeout", type=int, default=25, help="Timeout por URL no Playwright.")
    parser.add_argument("--somente-status", nargs="*", default=sorted(STATUS_CONFERENCIA), help="Status a validar.")
    return parser.parse_args()


def _split_multi(value: object) -> list[str]:
    if pd.isna(value):
        return []
    return [part.strip() for part in str(value).split(";") if part.strip()]


def _digits(value: object) -> str:
    digits = re.sub(r"\D", "", str(value or ""))
    if digits.startswith("55") and len(digits) in {12, 13}:
        digits = digits[2:]
    return digits


def _raw_digits(value: object) -> str:
    return re.sub(r"\D", "", str(value or ""))


def _texto_contem_valor(texto: str, campo: str, valor: str) -> bool:
    if not valor:
        return True
    if campo in {"Telefone", "Celular/WhatsApp"}:
        needle = _digits(valor)
        raw_needle = _raw_digits(valor)
        haystack = _raw_digits(texto)
        return bool((needle and needle in haystack) or (raw_needle and raw_needle in haystack))
    if campo == "E-mail":
        return valor.lower() in texto.lower()
    return normalize_for_search(valor) in normalize_for_search(texto)


def _linhas_nao_vazias(texto: str) -> list[str]:
    return [line.strip() for line in re.sub(r"\r\n?", "\n", texto or "").split("\n") if line.strip()]


def _termos_categoria(row: pd.Series) -> list[str]:
    cargo = str(_row_get(row, "Cargo/Área", "Cargo/Area", "Cargo/Ãrea") or "")
    orgao = str(_row_get(row, "Órgão/Secretaria", "Orgao/Secretaria", "Ã“rgÃ£o/Secretaria") or "")
    hay = normalize_for_search(f"{cargo} {orgao}")
    termos: list[str] = []
    if "vice" in hay:
        termos.extend(["vice prefeito", "vice prefeita", "vice-prefeito", "vice-prefeita"])
    elif "prefeito" in hay or "prefeita" in hay:
        termos.extend(["prefeito", "prefeita", "gabinete"])
    if "chefe de gabinete" in hay:
        termos.extend(["chefe de gabinete", "gabinete"])
    if "desenvolvimento economico" in hay:
        termos.extend(["desenvolvimento economico"])
    elif "desenvolvimento" in hay:
        termos.extend(["desenvolvimento"])
    if "financas" in hay or "fazenda" in hay:
        termos.extend(["financas", "fazenda"])
    if "planejamento" in hay:
        termos.extend(["planejamento"])
    if "agencia" in hay or "sala" in hay:
        termos.extend(["agencia de desenvolvimento", "sala do empreendedor", "casa do empreendedor", "banco do povo"])
    termos.extend(part for part in (normalize_for_search(cargo), normalize_for_search(orgao)) if part)
    return list(dict.fromkeys(termos))


def _valor_associado_a_categoria(texto: str, valor: str, row: pd.Series) -> bool:
    valor_norm = normalize_for_search(valor)
    valor_digits = _digits(valor)
    valor_raw_digits = _raw_digits(valor)
    if not valor_norm:
        return True
    termos = [term for term in _termos_categoria(row) if term]
    if not termos:
        return True
    linhas = _linhas_nao_vazias(texto)
    for index, line in enumerate(linhas):
        line_norm = normalize_for_search(line)
        line_digits = _raw_digits(line)
        valor_na_linha = valor_norm in line_norm or bool(
            (valor_digits and valor_digits in line_digits) or (valor_raw_digits and valor_raw_digits in line_digits)
        )
        if not valor_na_linha:
            continue
        janela = "\n".join(linhas[max(0, index - 12) : min(len(linhas), index + 13)])
        janela_norm = normalize_for_search(janela)
        if any(term in janela_norm for term in termos):
            return True
    return False


def _categoria_exige_nome_pessoa(cargo_area: str) -> bool:
    normalized = normalize_for_search(cargo_area)
    return normalized not in {"municipio/capital e uf", "agencias municipais de desenvolvimento"}


def baixar_texto_playwright(url: str, timeout: int = 25) -> tuple[str, str, str]:
    html, status, observacoes, final_url, _status_http, _content_type, _metodo = _baixar_com_navegador(url, timeout, "auto")
    texto = html_para_texto(html)
    if status == "Encontrado" and not texto:
        session = criar_sessao("Robo de validacao institucional", 1)
        html_req, status_req, obs_req, final_req, *_rest = _baixar(session, final_url or url, timeout)
        texto_req = html_para_texto(html_req)
        if texto_req:
            return texto_req, status_req, f"Playwright sem texto; fallback requests em {final_req}. {obs_req}".strip()
    return texto, status, observacoes or final_url


def selecionar_linhas_para_validacao(
    dados: pd.DataFrame,
    max_linhas: int = 40,
    seed: int = 42,
    status_alvo: set[str] | None = None,
) -> pd.DataFrame:
    status_alvo = status_alvo or STATUS_CONFERENCIA
    work = dados[dados["Status"].astype(str).isin(status_alvo)].copy()
    if "Cargo/Área" in work.columns:
        work = work[work["Cargo/Área"].astype(str) != CATEGORIA_IDENTIFICACAO.label]
    if work.empty:
        return work

    tem_campo = pd.Series(False, index=work.index)
    for campo in CAMPOS_CONFERENCIA:
        if campo in work.columns:
            tem_campo = tem_campo | work[campo].fillna("").astype(str).str.strip().ne("")
    work = work[tem_campo]
    if len(work) <= max_linhas:
        return work
    if max_linhas <= 0:
        return work

    por_uf = work.groupby("UF", group_keys=False).head(1)
    restante = work.drop(index=por_uf.index)
    slots = max(max_linhas - len(por_uf), 0)
    if slots <= 0:
        return por_uf.head(max_linhas)
    amostra = restante.sample(n=min(slots, len(restante)), random_state=seed)
    return pd.concat([por_uf, amostra]).sort_index()


def validar_registros(
    dados: pd.DataFrame,
    fetcher: Callable[[str], tuple[str, str, str]],
    max_linhas: int = 40,
    seed: int = 42,
    status_alvo: set[str] | None = None,
) -> pd.DataFrame:
    linhas = selecionar_linhas_para_validacao(dados, max_linhas=max_linhas, seed=seed, status_alvo=status_alvo)
    cache: dict[str, tuple[str, str, str]] = {}
    resultados: list[dict[str, object]] = []

    for index, row in linhas.iterrows():
        url = str(row.get("URL da fonte") or row.get("URL específica") or "").strip()
        if not url:
            resultados.append(_resultado(row, index, "", "Divergente", "Linha sem URL de fonte."))
            continue

        if url not in cache:
            try:
                cache[url] = fetcher(url)
            except Exception as exc:
                cache[url] = "", "Necessita validação manual", f"Erro ao abrir fonte no navegador: {exc}"
        texto, status_fonte, obs_fonte = cache[url]
        if status_fonte not in {"Encontrado", "Parcial"}:
            resultados.append(_resultado(row, index, url, "Não validado", f"Fonte não validável no momento: {status_fonte}. {obs_fonte}"))
            continue
        if not texto:
            resultados.append(_resultado(row, index, url, "Não validado", f"Fonte não gerou texto: {status_fonte}. {obs_fonte}"))
            continue

        divergencias: list[str] = []
        campos_conferidos = 0
        cargo_area = str(_row_get(row, "Cargo/Área", "Cargo/Area", "Cargo/Ãrea") or "")
        nome_raw = row.get("Nome", "")
        nome = "" if pd.isna(nome_raw) else str(nome_raw).strip()
        if nome and cargo_area != CATEGORIA_IDENTIFICACAO.label and _categoria_exige_nome_pessoa(cargo_area):
            if not _nome_valido(nome):
                divergencias.append(f"Nome não parece pessoa publicada: {nome}")
            elif not _valor_associado_a_categoria(texto, nome, row):
                divergencias.append(f"Nome sem associação visual/estrutural com a categoria: {nome}")
        for campo in CAMPOS_CONFERENCIA:
            for valor in _split_multi(row.get(campo, "")):
                campos_conferidos += 1
                if not _texto_contem_valor(texto, campo, valor):
                    divergencias.append(f"{campo} não localizado na fonte: {valor}")
                elif campo in {"E-mail", "Telefone", "Celular/WhatsApp"} and not _valor_associado_a_categoria(texto, valor, row):
                    divergencias.append(f"{campo} sem associação visual/estrutural com a categoria: {valor}")

        if divergencias:
            resultados.append(_resultado(row, index, url, "Divergente", " | ".join(divergencias), campos_conferidos))
        else:
            resultados.append(_resultado(row, index, url, "Validado", "", campos_conferidos))

    return pd.DataFrame(resultados)


def _resultado(
    row: pd.Series,
    index: int,
    url: str,
    status_validacao: str,
    observacoes: str,
    campos_conferidos: int = 0,
) -> dict[str, object]:
    return {
        "Linha Dados": index + 2,
        "UF": row.get("UF", ""),
        "Município/Capital": row.get("Município/Capital", ""),
        "Cargo/Área": row.get("Cargo/Área", ""),
        "Status coleta": row.get("Status", ""),
        "Nome": row.get("Nome", ""),
        "E-mail": row.get("E-mail", ""),
        "Telefone": row.get("Telefone", ""),
        "Celular/WhatsApp": row.get("Celular/WhatsApp", ""),
        "URL da fonte": url,
        "Status validação": status_validacao,
        "Campos conferidos": campos_conferidos,
        "Observações": observacoes,
        "Data/hora validação": datetime.now().isoformat(timespec="seconds"),
    }


def validar_planilha(
    excel_path: str | Path,
    max_linhas: int = 40,
    seed: int = 42,
    timeout: int = 25,
    status_alvo: set[str] | None = None,
) -> pd.DataFrame:
    dados = pd.read_excel(excel_path, sheet_name="Dados")

    def fetcher(url: str) -> tuple[str, str, str]:
        return baixar_texto_playwright(url, timeout=timeout)

    return validar_registros(dados, fetcher, max_linhas=max_linhas, seed=seed, status_alvo=status_alvo)


def main() -> None:
    args = parse_args()
    status_alvo = set(args.somente_status or STATUS_CONFERENCIA)
    result = validar_planilha(args.excel, args.max_linhas, args.seed, args.timeout, status_alvo)
    output_path = Path(args.output_path) if args.output_path else Path(args.excel).with_name("validacao_fontes_oficiais.xlsx")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.to_excel(output_path, index=False)
    divergencias = result[result["Status validação"] == "Divergente"]
    print(f"Validação salva em: {output_path}")
    print(f"Linhas validadas: {len(result)}")
    print(f"Divergências: {len(divergencias)}")
    if not divergencias.empty:
        print(divergencias.head(20).to_string(index=False))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
