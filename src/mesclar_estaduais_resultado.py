from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from src.gerar_excel import gerar_excel
from src.utils import project_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Substitui as linhas estaduais de uma entrega por uma coleta estadual corrigida.")
    parser.add_argument(
        "--base",
        default=str(project_path("data", "output", "resultado_final_revalidado_visualmente.xlsx")),
        help="Planilha final existente com dados municipais preservados.",
    )
    parser.add_argument("--estaduais", required=True, help="Planilha gerada somente com fontes estaduais corrigidas.")
    parser.add_argument(
        "--output",
        default=str(project_path("data", "output", "resultado_final_revalidado_visualmente.xlsx")),
        help="Planilha final de saida.",
    )
    return parser.parse_args()


def _read_sheet(path: Path, sheet_name: str, fallback: str | None = None) -> pd.DataFrame:
    workbook = pd.ExcelFile(path)
    if sheet_name in workbook.sheet_names:
        return pd.read_excel(path, sheet_name=sheet_name)
    if fallback and fallback in workbook.sheet_names:
        return pd.read_excel(path, sheet_name=fallback)
    return pd.DataFrame()


def _filtrar_esfera(df: pd.DataFrame, estadual: bool) -> pd.DataFrame:
    if df.empty or "Esfera" not in df.columns:
        return df.copy()
    esfera = df["Esfera"].astype(str).str.strip().str.lower()
    mask = esfera == "estadual"
    return df[mask if estadual else ~mask].reset_index(drop=True)


def _combinar(base_df: pd.DataFrame, estaduais_df: pd.DataFrame) -> pd.DataFrame:
    base_municipal = _filtrar_esfera(base_df, estadual=False)
    estaduais = _filtrar_esfera(estaduais_df, estadual=True)
    if base_municipal.empty:
        return estaduais
    if estaduais.empty:
        return base_municipal
    return pd.concat([base_municipal, estaduais], ignore_index=True)


def mesclar_estaduais(base_path: str | Path, estaduais_path: str | Path, output_path: str | Path) -> Path:
    base = Path(base_path)
    estaduais = Path(estaduais_path)
    if not base.exists():
        raise FileNotFoundError(f"Planilha base nao encontrada: {base}")
    if not estaduais.exists():
        raise FileNotFoundError(f"Planilha estadual nao encontrada: {estaduais}")

    dados = _combinar(_read_sheet(base, "Dados", "Resultado consolidado"), _read_sheet(estaduais, "Dados", "Resultado consolidado"))
    municipios = _combinar(_read_sheet(base, "Municípios pesquisados"), _read_sheet(estaduais, "Municípios pesquisados"))
    pendencias = _combinar(_read_sheet(base, "Pendências"), _read_sheet(estaduais, "Pendências"))
    fontes = _combinar(_read_sheet(base, "Fontes e Log"), _read_sheet(estaduais, "Fontes e Log"))
    return gerar_excel(dados, municipios, pendencias, output_path, fontes)


def main() -> None:
    args = parse_args()
    output = mesclar_estaduais(args.base, args.estaduais, args.output)
    print(f"Planilha final atualizada: {output}")


if __name__ == "__main__":
    main()
