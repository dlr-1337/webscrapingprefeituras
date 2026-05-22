from __future__ import annotations

from typing import Iterable

import pandas as pd

from src.normalizar_dados import STATUS_PERMITIDOS


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


def validar_resultados(df: pd.DataFrame) -> list[dict[str, str]]:
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
    return pendencias
