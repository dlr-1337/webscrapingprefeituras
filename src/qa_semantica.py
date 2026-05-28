from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd

from src.extrair_contatos import _nome_valido
from src.gerar_excel import gerar_excel, preparar_resultado_excel
from src.utils import normalize_for_search, project_path


TERMOS_NOME_SUSPEITO = (
    "concordar e fechar",
    "aceitar cookies",
    "preferencias de cookies",
    "politica de privacidade",
    "selo ouro",
    "analise de uso",
    "olhe preco",
    "sub menus",
    "accessibility toolbar",
    "legislatura periodo",
    "marketing e jornalismo",
    "polo de bebidas",
    "amargosa top",
    "partido socialista brasileiro",
    "movimento democratico brasileiro",
    "composicao da coligacao",
    "insatisfeito regular",
    "satisfeito muito",
    "quadra poliesportiva",
    "atividades ludicas",
    "censo escolar",
)

EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)


def _read_sheet(path: Path, sheet_name: str, fallback: str | None = None) -> pd.DataFrame:
    workbook = pd.ExcelFile(path)
    if sheet_name in workbook.sheet_names:
        return pd.read_excel(path, sheet_name=sheet_name)
    if fallback and fallback in workbook.sheet_names:
        return pd.read_excel(path, sheet_name=fallback)
    wanted = {normalize_for_search(sheet_name)}
    if fallback:
        wanted.add(normalize_for_search(fallback))
    for available in workbook.sheet_names:
        if normalize_for_search(available) in wanted:
            return pd.read_excel(path, sheet_name=available)
    return pd.DataFrame()


def _texto(value: object) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def _coluna_por_tokens(df: pd.DataFrame, *tokens: str) -> str:
    for column in df.columns:
        normalized = normalize_for_search(column).replace("/", " ")
        if all(token in normalized for token in tokens):
            return str(column)
    return ""


def _colunas_resultado(df: pd.DataFrame) -> dict[str, str]:
    return {
        "uf": _coluna_por_tokens(df, "uf"),
        "municipio_capital": _coluna_por_tokens(df, "municipio", "capital"),
        "esfera": _coluna_por_tokens(df, "esfera"),
        "cargo_area": _coluna_por_tokens(df, "cargo", "area"),
        "nome": _coluna_por_tokens(df, "nome"),
        "email": _coluna_por_tokens(df, "mail"),
        "telefone": _coluna_por_tokens(df, "telefone"),
        "url_fonte": _coluna_por_tokens(df, "url", "fonte"),
        "status": _coluna_por_tokens(df, "status"),
    }


def nome_suspeito(nome: object) -> bool:
    text = _texto(nome)
    if not text:
        return False
    normalized = normalize_for_search(text)
    return any(term in normalized for term in TERMOS_NOME_SUSPEITO) or not _nome_valido(text)


def _tem_contato(row: pd.Series) -> bool:
    return any(_texto(row.get(column)) for column in ("E-mail", "Telefone", "Celular/WhatsApp", "Celular"))


def _emails(df: pd.DataFrame) -> list[str]:
    if "E-mail" not in df.columns:
        return []
    emails: list[str] = []
    for value in df["E-mail"].fillna("").astype(str):
        emails.extend(email.lower() for email in EMAIL_PATTERN.findall(value))
    return emails


def _metricas(dados: pd.DataFrame, label: str) -> list[dict[str, object]]:
    if dados.empty:
        return [{"Versao": label, "Indicador": "Linhas", "Valor": 0}]
    emails = _emails(dados)
    contato_mask = pd.Series(False, index=dados.index)
    for column in ("E-mail", "Telefone", "Celular/WhatsApp", "Celular"):
        if column in dados.columns:
            contato_mask = contato_mask | dados[column].fillna("").astype(str).str.strip().ne("")
    return [
        {"Versao": label, "Indicador": "Linhas", "Valor": len(dados)},
        {"Versao": label, "Indicador": "Linhas com e-mail", "Valor": int(dados.get("E-mail", pd.Series(dtype=str)).fillna("").astype(str).str.strip().ne("").sum())},
        {"Versao": label, "Indicador": "Enderecos de e-mail", "Valor": len(emails)},
        {"Versao": label, "Indicador": "E-mails unicos", "Valor": len(set(emails))},
        {"Versao": label, "Indicador": "Linhas com algum contato", "Valor": int(contato_mask.sum())},
    ]


def criar_relatorio_qa(dados_original: pd.DataFrame, dados_limpos: pd.DataFrame) -> pd.DataFrame:
    original_cols = _colunas_resultado(dados_original)
    limpo_cols = _colunas_resultado(dados_limpos)
    if dados_original.empty or not original_cols["nome"]:
        return pd.DataFrame()

    rows: list[dict[str, object]] = []
    nomes_limpos = set()
    original_key_columns = [
        original_cols["uf"],
        original_cols["municipio_capital"],
        original_cols["esfera"],
        original_cols["cargo_area"],
        original_cols["url_fonte"],
        original_cols["nome"],
    ]
    limpo_key_columns = [
        limpo_cols["uf"],
        limpo_cols["municipio_capital"],
        limpo_cols["esfera"],
        limpo_cols["cargo_area"],
        limpo_cols["url_fonte"],
        limpo_cols["nome"],
    ]
    if all(limpo_key_columns):
        for _, row in dados_limpos[limpo_key_columns].fillna("").astype(str).iterrows():
            nomes_limpos.add(tuple(row[column] for column in limpo_key_columns))

    for index, row in dados_original.iterrows():
        nome = _texto(row.get(original_cols["nome"]))
        cargo_norm = normalize_for_search(row.get(original_cols["cargo_area"], "")).replace("/", " ")
        if "municipio capital e uf" in cargo_norm:
            continue
        if not nome_suspeito(nome):
            continue
        key = tuple(_texto(row.get(column)) for column in original_key_columns)
        removida = key not in nomes_limpos
        rows.append(
            {
                "Linha original": index + 2,
                "UF": row.get(original_cols["uf"], ""),
                "Municipio/Capital": row.get(original_cols["municipio_capital"], ""),
                "Esfera": row.get(original_cols["esfera"], ""),
                "Cargo/Area": row.get(original_cols["cargo_area"], ""),
                "Nome original": nome,
                "E-mail": row.get(original_cols["email"], ""),
                "Telefone": row.get(original_cols["telefone"], ""),
                "URL da fonte": row.get(original_cols["url_fonte"], ""),
                "Status original": row.get(original_cols["status"], ""),
                "Tem contato": "Sim" if _tem_contato(row) else "Nao",
                "Acao aplicada": "Linha removida da v2" if removida else "Nome limpo/linha reclassificada na v2",
            }
        )

    return pd.DataFrame(rows)


def gerar_entrega_v2(input_path: str | Path, output_path: str | Path, qa_output_path: str | Path) -> tuple[Path, Path]:
    input_file = Path(input_path)
    output_file = Path(output_path)
    qa_file = Path(qa_output_path)

    dados = _read_sheet(input_file, "Dados", "Resultado consolidado")
    municipios = _read_sheet(input_file, "MunicÃ­pios pesquisados")
    pendencias = _read_sheet(input_file, "PendÃªncias")
    fontes = _read_sheet(input_file, "Fontes e Log")
    configuracao = _read_sheet(input_file, "ConfiguraÃ§Ã£o")

    dados_limpos = preparar_resultado_excel(dados)
    qa = criar_relatorio_qa(dados, dados_limpos)
    metricas = pd.DataFrame([*_metricas(dados, "Original"), *_metricas(dados_limpos, "V2")])

    qa_file.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(qa_file, engine="openpyxl") as writer:
        qa.to_excel(writer, sheet_name="Linhas suspeitas", index=False)
        metricas.to_excel(writer, sheet_name="Metricas", index=False)

    output = gerar_excel(dados_limpos, municipios, pendencias, output_file, fontes, configuracao)
    return output, qa_file


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Gera entrega v2 com limpeza semantica e relatorio de QA.")
    parser.add_argument(
        "--input",
        default=str(project_path("data", "output", "resultado_final_revalidado_visualmente.xlsx")),
        help="Planilha final original.",
    )
    parser.add_argument(
        "--output",
        default=str(project_path("data", "output", "resultado_final_revalidado_visualmente_v2.xlsx")),
        help="Planilha v2 limpa.",
    )
    parser.add_argument(
        "--qa-output",
        default=str(project_path("data", "output", "qa_semantica_revalidado_v2.xlsx")),
        help="Relatorio auxiliar de QA semantica.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output, qa = gerar_entrega_v2(args.input, args.output, args.qa_output)
    print(f"Planilha v2 gerada: {output}")
    print(f"QA semantica gerada: {qa}")


if __name__ == "__main__":
    main()
