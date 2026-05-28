from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests

from src.localizar_sites import localizar_site
from src.utils import clean_url, normalize_key, project_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Preenche e revisa sites oficiais na lista congelada do escopo.")
    parser.add_argument(
        "--input",
        dest="input_path",
        default=str(project_path("data", "input", "municipios_ibge_escopo_congelado.csv")),
        help="CSV/XLSX congelado sem ou com sites oficiais.",
    )
    parser.add_argument(
        "--output",
        dest="output_path",
        default=str(project_path("data", "input", "municipios_ibge_escopo_congelado_com_sites.csv")),
        help="CSV de saída com site_oficial e campos de revisão.",
    )
    parser.add_argument(
        "--pendencias",
        dest="pendencias_path",
        default=str(project_path("data", "output", "sites_oficiais_pendentes.xlsx")),
        help="XLSX com sites inferidos ou não localizados para revisão.",
    )
    parser.add_argument("--timeout", type=int, default=5, help="Timeout em segundos por candidato de URL.")
    parser.add_argument("--workers", type=int, default=12, help="Quantidade de validações paralelas.")
    parser.add_argument(
        "--sem-busca-web-sites",
        action="store_true",
        help="Não usa busca web oficial para localizar sites ausentes na base.",
    )
    return parser.parse_args()


def _read_input(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(path)
    if suffix == ".csv":
        last_error: Exception | None = None
        for encoding in ("utf-8-sig", "utf-8", "latin1"):
            try:
                return pd.read_csv(path, sep=None, engine="python", encoding=encoding)
            except Exception as exc:  # pragma: no cover - fallback diagnostic only
                last_error = exc
        raise ValueError(f"Não foi possível ler CSV {path}: {last_error}")
    raise ValueError(f"Formato não suportado: {path.suffix}. Use CSV ou XLSX.")


def _find_column(df: pd.DataFrame, *aliases: str) -> str:
    wanted = {normalize_key(alias) for alias in aliases}
    for column in df.columns:
        if normalize_key(str(column)) in wanted:
            return str(column)
    raise ValueError(f"Coluna obrigatória não encontrada. Esperado: {', '.join(aliases)}")


def _optional_column(df: pd.DataFrame, *aliases: str) -> str | None:
    try:
        return _find_column(df, *aliases)
    except ValueError:
        return None


def _value(row: pd.Series, column: str | None) -> str:
    if not column:
        return ""
    value = row.get(column, "")
    if pd.isna(value):
        return ""
    return str(value).strip()


def preencher_sites_congelados(
    input_path: str | Path,
    output_path: str | Path,
    pendencias_path: str | Path | None = None,
    timeout: int = 5,
    workers: int = 1,
    session=requests,
    usar_busca_web: bool = True,
) -> tuple[Path, Path | None]:
    input_file = Path(input_path)
    output_file = Path(output_path)
    pendencias_file = Path(pendencias_path) if pendencias_path else None

    df = _read_input(input_file)
    municipio_col = _find_column(df, "municipio", "município")
    uf_col = _find_column(df, "uf")
    site_col = _optional_column(df, "site_oficial", "site oficial", "site", "url", "prefeitura_url")

    data_validacao = datetime.now().date().isoformat()

    def processar_row(row: pd.Series) -> tuple[str, str, str]:
        site, site_status, obs = localizar_site(
            municipio=_value(row, municipio_col),
            uf=_value(row, uf_col),
            site_existente=_value(row, site_col),
            testar_inferencia=True,
            timeout=timeout,
            session=session,
            usar_busca_web=usar_busca_web,
        )
        return clean_url(site), site_status, obs

    rows = [row for _, row in df.iterrows()]
    if workers > 1:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            resultados = list(executor.map(processar_row, rows))
    else:
        resultados = [processar_row(row) for row in rows]

    sites = [site for site, _, _ in resultados]
    status = [site_status for _, site_status, _ in resultados]
    observacoes = [obs for _, _, obs in resultados]

    result = df.copy()
    result["site_oficial"] = sites
    result["status_localizacao_site"] = status
    result["observacoes_localizacao_site"] = observacoes
    result["data_validacao_site"] = data_validacao

    output_file.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output_file, index=False, encoding="utf-8")

    if pendencias_file:
        pendentes = result[result["status_localizacao_site"] != "Encontrado"].copy()
        pendencias_file.parent.mkdir(parents=True, exist_ok=True)
        pendentes.to_excel(pendencias_file, index=False)

    return output_file, pendencias_file


def main() -> None:
    args = parse_args()
    output, pendencias = preencher_sites_congelados(
        args.input_path,
        args.output_path,
        args.pendencias_path,
        timeout=args.timeout,
        workers=args.workers,
        usar_busca_web=not args.sem_busca_web_sites,
    )
    print(f"Base com sites gerada: {output}")
    if pendencias:
        print(f"Pendências de revisão geradas: {pendencias}")


if __name__ == "__main__":
    main()
