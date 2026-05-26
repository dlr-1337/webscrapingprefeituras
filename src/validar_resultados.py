from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

import pandas as pd

from src.carregar_municipios import carregar_municipios
from src.escopo_categorias import labels_categorias_obrigatorias
from src.filtrar_municipios import filtrar_municipios
from src.normalizar_dados import STATUS_PERMITIDOS


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audita a planilha final contra o escopo e regras de completude.")
    parser.add_argument("excel", help="Caminho da planilha final .xlsx.")
    parser.add_argument("--input", dest="input_path", help="Base de municípios usada para derivar o escopo esperado.")
    parser.add_argument("--output", dest="output_path", help="Caminho opcional para salvar o relatório de auditoria em XLSX.")
    return parser.parse_args()


COLUNAS_RESULTADO = [
    "UF",
    "Estado",
    "Município/Capital",
    "Município",
    "População",
    "Critério de inclusão",
    "Esfera",
    "Site oficial",
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
]

COLUNAS_MUNICIPIOS = [
    "UF",
    "Estado",
    "Município/Capital",
    "Município",
    "População",
    "Critério de inclusão",
    "Esfera",
    "Site oficial",
    "Status geral",
    "Observações",
]

COLUNAS_PENDENCIAS = [
    "UF",
    "Esfera",
    "Município/Capital",
    "Município",
    "Tipo de pendência",
    "Descrição",
    "URL, se houver",
    "Status",
    "Observações",
]

COLUNAS_FONTES_LOG = [
    "UF",
    "Estado",
    "Município/Capital",
    "Município",
    "Esfera",
    "Site oficial",
    "URL consultada",
    "URL final",
    "Status",
    "HTTP",
    "Método",
    "Gerou texto",
    "Data/hora",
    "Observações",
]

ABAS_OBRIGATORIAS = ["Dados", "Resumo", "Fontes e Log", "Configuração"]
ABAS_APOIO = ["Municípios pesquisados", "Pendências"]

STATUS_COM_OBSERVACAO_OBRIGATORIA = {
    "Parcial",
    "Não encontrado",
    "Não publicado",
    "Site fora do ar",
    "Site não localizado",
    "Página sem informação pública",
    "Bloqueio técnico",
    "Necessita validação manual",
}


def garantir_colunas(df: pd.DataFrame, colunas: Iterable[str]) -> pd.DataFrame:
    result = df.copy()
    for column in colunas:
        if column not in result.columns:
            result[column] = ""
    return result[list(colunas)]


def criar_pendencia(
    uf: str,
    municipio: str,
    tipo: str,
    descricao: str,
    status: str,
    url: str = "",
    observacoes: str = "",
    esfera: str = "Municipal",
    municipio_capital: str = "",
) -> dict[str, str]:
    return {
        "UF": uf,
        "Esfera": esfera,
        "Município/Capital": municipio_capital or municipio,
        "Município": municipio,
        "Tipo de pendência": tipo,
        "Descrição": descricao,
        "URL, se houver": url,
        "Status": status,
        "Observações": observacoes,
    }


def validar_resultados(df: pd.DataFrame, municipios_df: pd.DataFrame | None = None) -> list[dict[str, str]]:
    pendencias: list[dict[str, str]] = []
    for index, row in df.iterrows():
        status = str(row.get("Status", ""))
        if status not in STATUS_PERMITIDOS:
            pendencias.append(
                criar_pendencia(
                    str(row.get("UF", "")),
                    str(row.get("Município", "")),
                    "Status inválido",
                    f"Linha {index + 2} possui status fora da lista permitida.",
                    "Necessita validação manual",
                    str(row.get("URL específica", "")),
                    status,
                )
            )
        tem_url_origem = bool(str(row.get("URL específica", "")).strip() or str(row.get("URL da fonte", "")).strip())
        if status in {"Encontrado", "Parcial"} and not tem_url_origem:
            pendencias.append(
                criar_pendencia(
                    str(row.get("UF", "")),
                    str(row.get("Município", "")),
                    "URL ausente",
                    f"Linha {index + 2} possui dado encontrado/parcial sem URL específica.",
                    "Necessita validação manual",
                    "",
                    "Todo dado encontrado deve ter URL de origem.",
                    str(row.get("Esfera", "Municipal")),
                    str(row.get("Município/Capital", "")),
                )
            )
    if municipios_df is not None:
        pendencias.extend(validar_cobertura_categorias(df, municipios_df))
    return pendencias


def validar_cobertura_categorias(df: pd.DataFrame, municipios_df: pd.DataFrame) -> list[dict[str, str]]:
    pendencias: list[dict[str, str]] = []
    if municipios_df.empty:
        return pendencias

    resultado = df.copy()
    for column in ("UF", "Município/Capital", "Município", "Esfera", "Cargo/Área"):
        if column not in resultado.columns:
            resultado[column] = ""

    for _, alvo in municipios_df.iterrows():
        uf = str(alvo.get("UF", ""))
        municipio_capital = str(alvo.get("Município/Capital", alvo.get("Município", "")))
        municipio = str(alvo.get("Município", municipio_capital))
        esfera = str(alvo.get("Esfera", "Municipal") or "Municipal")

        subset = resultado[
            (resultado["UF"].astype(str) == uf)
            & (resultado["Município/Capital"].astype(str) == municipio_capital)
            & (resultado["Esfera"].astype(str) == esfera)
        ]
        categorias_presentes = set(subset["Cargo/Área"].astype(str))
        for categoria in labels_categorias_obrigatorias():
            if categoria in categorias_presentes:
                continue
            pendencias.append(
                criar_pendencia(
                    uf,
                    municipio,
                    "Cobertura de categoria",
                    f"Categoria obrigatória ausente na aba Dados: {categoria}.",
                    "Necessita validação manual",
                    str(alvo.get("Site oficial", "")),
                    "Cada município/capital deve ter dado ou status por categoria do escopo.",
                    esfera,
                    municipio_capital,
                )
            )

    return pendencias


def carregar_municipios_esperados(input_path: str | Path) -> pd.DataFrame:
    filtrados = filtrar_municipios(carregar_municipios(input_path))
    result = filtrados.copy()
    result["Esfera"] = "Municipal"
    result["Município/Capital"] = result["Município"]
    return result[["UF", "Município/Capital", "Município", "Esfera"]].drop_duplicates().reset_index(drop=True)


def auditar_planilha_final(excel_path: str | Path, input_path: str | Path | None = None) -> pd.DataFrame:
    excel_file = Path(excel_path)
    if not excel_file.exists():
        return pd.DataFrame(
            [
                {
                    "Tipo": "Arquivo",
                    "Severidade": "Erro",
                    "Descrição": f"Planilha final não encontrada: {excel_file}",
                    "UF": "",
                    "Município/Capital": "",
                    "Categoria": "",
                    "Linha": "",
                }
            ]
        )

    workbook = pd.ExcelFile(excel_file)
    issues: list[dict[str, object]] = []
    for sheet in [*ABAS_OBRIGATORIAS, *ABAS_APOIO]:
        if sheet not in workbook.sheet_names:
            issues.append(_issue("Aba", "Erro", f"Aba ausente: {sheet}"))

    dados = pd.read_excel(excel_file, sheet_name="Dados") if "Dados" in workbook.sheet_names else pd.DataFrame()
    municipios = (
        pd.read_excel(excel_file, sheet_name="Municípios pesquisados")
        if "Municípios pesquisados" in workbook.sheet_names
        else pd.DataFrame()
    )

    dados = garantir_colunas(dados, COLUNAS_RESULTADO)
    municipios = garantir_colunas(municipios, COLUNAS_MUNICIPIOS)

    issues.extend(_auditar_linhas_dados(dados))
    issues.extend(_auditar_cobertura_workbook(dados, municipios))
    if input_path:
        issues.extend(_auditar_escopo_processado(dados, municipios, carregar_municipios_esperados(input_path)))

    return pd.DataFrame(
        issues,
        columns=["Tipo", "Severidade", "Descrição", "UF", "Município/Capital", "Categoria", "Linha"],
    )


def _issue(
    tipo: str,
    severidade: str,
    descricao: str,
    uf: str = "",
    municipio_capital: str = "",
    categoria: str = "",
    linha: int | str = "",
) -> dict[str, object]:
    return {
        "Tipo": tipo,
        "Severidade": severidade,
        "Descrição": descricao,
        "UF": uf,
        "Município/Capital": municipio_capital,
        "Categoria": categoria,
        "Linha": linha,
    }


def _blank(value: object) -> bool:
    if pd.isna(value):
        return True
    return str(value).strip() == ""


def _auditar_linhas_dados(dados: pd.DataFrame) -> list[dict[str, object]]:
    issues: list[dict[str, object]] = []
    for index, row in dados.iterrows():
        linha_excel = index + 2
        status = str(row.get("Status", "")).strip()
        categoria = str(row.get("Cargo/Área", "")).strip()
        uf = str(row.get("UF", "")).strip()
        municipio_capital = str(row.get("Município/Capital", "")).strip()

        if status not in STATUS_PERMITIDOS:
            issues.append(_issue("Status", "Erro", f"Status inválido ou ausente: {status}", uf, municipio_capital, categoria, linha_excel))
        if _blank(row.get("URL da fonte")) and _blank(row.get("URL específica")):
            issues.append(_issue("Fonte", "Erro", "Linha sem URL de fonte.", uf, municipio_capital, categoria, linha_excel))
        if _blank(row.get("Data da coleta")):
            issues.append(_issue("Data", "Erro", "Linha sem data de coleta.", uf, municipio_capital, categoria, linha_excel))
        if status in STATUS_COM_OBSERVACAO_OBRIGATORIA and _blank(row.get("Observações")):
            issues.append(_issue("Observação", "Erro", "Status de ausência/parcial sem observação.", uf, municipio_capital, categoria, linha_excel))
    return issues


def _auditar_cobertura_workbook(dados: pd.DataFrame, municipios: pd.DataFrame) -> list[dict[str, object]]:
    issues: list[dict[str, object]] = []
    for pendencia in validar_cobertura_categorias(dados, municipios):
        issues.append(
            _issue(
                "Cobertura",
                "Erro",
                pendencia["Descrição"],
                pendencia["UF"],
                pendencia["Município/Capital"],
                pendencia["Descrição"].rsplit(": ", 1)[-1].rstrip("."),
            )
        )
    return issues


def _auditar_escopo_processado(
    dados: pd.DataFrame,
    municipios: pd.DataFrame,
    esperados: pd.DataFrame,
) -> list[dict[str, object]]:
    issues: list[dict[str, object]] = []
    for source_name, source in (("Municípios pesquisados", municipios), ("Dados", dados)):
        presentes = {
            (str(row["UF"]), str(row["Município/Capital"]), str(row["Esfera"]))
            for _, row in source.iterrows()
            if str(row.get("Esfera", "Municipal")) == "Municipal"
        }
        fora_do_escopo = {
            (str(row["UF"]), str(row["Município/Capital"]), str(row["Esfera"]))
            for _, row in source.iterrows()
            if str(row.get("Esfera", "Municipal")) != "Municipal"
        }
        for uf, municipio_capital, esfera in sorted(fora_do_escopo):
            issues.append(
                _issue(
                    "Escopo",
                    "Erro",
                    f"Alvo fora do escopo municipal em {source_name}: Esfera={esfera}.",
                    uf,
                    municipio_capital,
                )
            )
        for _, esperado in esperados.iterrows():
            key = (str(esperado["UF"]), str(esperado["Município/Capital"]), "Municipal")
            if key not in presentes:
                issues.append(
                    _issue(
                        "Escopo",
                        "Erro",
                        f"Município/capital esperado ausente em {source_name}.",
                        key[0],
                        key[1],
                    )
                )
    return issues


def main() -> None:
    args = parse_args()
    issues = auditar_planilha_final(args.excel, args.input_path)
    if args.output_path:
        output = Path(args.output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        issues.to_excel(output, index=False)
    if issues.empty:
        print("Auditoria aprovada: nenhuma divergência encontrada.")
        return
    print(f"Auditoria encontrou {len(issues)} divergência(s).")
    print(issues.head(50).to_string(index=False))
    raise SystemExit(1)


if __name__ == "__main__":
    main()
