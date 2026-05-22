from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.utils import load_yaml, normalize_for_search, project_path


UF_POP_15000 = {"MG", "SC", "PR", "RS", "RJ", "GO", "ES", "BA", "SE"}


def carregar_criterios(path: str | Path | None = None) -> dict:
    config_path = Path(path) if path else project_path("config", "estados.yml")
    return load_yaml(config_path)


def _avaliar_linha(row: pd.Series, criterios: dict) -> tuple[bool, str]:
    uf = str(row.get("UF", "")).upper()
    populacao = int(row.get("População", 0) or 0)
    capital = bool(row.get("Capital", False))
    regra = criterios.get(uf, criterios.get("default", {"apenas_capital": True}))

    if regra.get("apenas_capital"):
        if capital:
            return True, "Capital dos demais estados/DF"
        return False, ""

    minimo = int(regra.get("populacao_minima", 0) or 0)
    if populacao > minimo:
        return True, f"{uf} acima de {minimo:,} habitantes".replace(",", ".")
    if capital and regra.get("incluir_capital", False):
        return True, "Capital incluída pela regra da UF"
    return False, ""


def filtrar_municipios(df: pd.DataFrame, criterios: dict | None = None) -> pd.DataFrame:
    criterios = criterios or carregar_criterios()
    rows: list[pd.Series] = []
    criterios_inclusao: list[str] = []

    for _, row in df.iterrows():
        incluir, criterio = _avaliar_linha(row, criterios)
        if incluir:
            rows.append(row)
            criterios_inclusao.append(criterio)

    if not rows:
        result = df.iloc[0:0].copy()
        result["Critério de inclusão"] = []
        return result

    result = pd.DataFrame(rows).reset_index(drop=True)
    result["Critério de inclusão"] = criterios_inclusao
    return result


def aplicar_filtros_cli(
    df: pd.DataFrame,
    uf: str | None = None,
    municipio: str | None = None,
    limite: int | None = None,
) -> pd.DataFrame:
    result = df.copy()
    if uf:
        result = result[result["UF"].astype(str).str.upper() == uf.upper()]
    if municipio:
        alvo = normalize_for_search(municipio)
        result = result[result["Município"].apply(lambda value: normalize_for_search(value) == alvo)]
    if limite:
        result = result.head(limite)
    return result.reset_index(drop=True)


def salvar_municipios_filtrados(
    df: pd.DataFrame,
    caminho: str | Path | None = None,
) -> Path:
    output_path = Path(caminho) if caminho else project_path("data", "output", "municipios_filtrados.xlsx")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(output_path, index=False)
    return output_path

