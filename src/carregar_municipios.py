from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.utils import estado_from_uf, is_capital, normalize_key, parse_bool, parse_int, uf_from_estado


COLUMN_ALIASES = {
    "municipio": "Município",
    "nome_municipio": "Município",
    "nome_do_municipio": "Município",
    "cidade": "Município",
    "uf": "UF",
    "sigla_uf": "UF",
    "estado": "Estado",
    "nome_estado": "Estado",
    "populacao": "População",
    "habitantes": "População",
    "populacao_estimada": "População",
    "capital": "Capital",
    "is_capital": "Capital",
    "capital_do_estado": "Capital",
    "site": "Site oficial",
    "site_oficial": "Site oficial",
    "url": "Site oficial",
    "prefeitura_url": "Site oficial",
    "site_prefeitura": "Site oficial",
}

CANONICAL_COLUMNS = ["UF", "Estado", "Município", "População", "Capital", "Site oficial"]


def _read_csv(path: Path) -> pd.DataFrame:
    last_error: Exception | None = None
    for encoding in ("utf-8-sig", "utf-8", "latin1"):
        try:
            return pd.read_csv(path, sep=None, engine="python", encoding=encoding)
        except Exception as exc:  # pragma: no cover - only used for fallback diagnostics
            last_error = exc
    raise ValueError(f"Não foi possível ler CSV {path}: {last_error}")


def _read_input(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(path)
    if suffix == ".csv":
        return _read_csv(path)
    raise ValueError(f"Formato não suportado: {path.suffix}. Use XLSX ou CSV.")


def normalizar_colunas(df: pd.DataFrame) -> pd.DataFrame:
    rename: dict[str, str] = {}
    for column in df.columns:
        canonical = COLUMN_ALIASES.get(normalize_key(str(column)))
        if canonical and canonical not in rename.values():
            rename[column] = canonical

    normalized = df.rename(columns=rename).copy()
    for column in CANONICAL_COLUMNS:
        if column not in normalized.columns:
            normalized[column] = ""

    normalized = normalized[CANONICAL_COLUMNS].copy()
    normalized["Município"] = normalized["Município"].fillna("").astype(str).str.strip()

    normalized["UF"] = normalized["UF"].fillna("").astype(str).str.strip().str.upper()
    if "Estado" in normalized:
        missing_uf = normalized["UF"].eq("")
        normalized.loc[missing_uf, "UF"] = normalized.loc[missing_uf, "Estado"].apply(uf_from_estado)

    normalized["Estado"] = normalized["Estado"].fillna("").astype(str).str.strip()
    missing_estado = normalized["Estado"].eq("")
    normalized.loc[missing_estado, "Estado"] = normalized.loc[missing_estado, "UF"].apply(estado_from_uf)

    normalized["População"] = normalized["População"].apply(parse_int)
    normalized["Capital"] = normalized.apply(
        lambda row: parse_bool(row["Capital"]) or is_capital(row["Município"], row["UF"]),
        axis=1,
    )
    normalized["Site oficial"] = normalized["Site oficial"].fillna("").astype(str).str.strip()

    return normalized


def carregar_municipios(caminho: str | Path) -> pd.DataFrame:
    path = Path(caminho)
    if not path.exists():
        raise FileNotFoundError(f"Base de municípios não encontrada: {path}")

    df = normalizar_colunas(_read_input(path))
    missing_required = df["Município"].eq("") | df["UF"].eq("")
    if missing_required.any():
        count = int(missing_required.sum())
        raise ValueError(f"Base possui {count} linha(s) sem Município ou UF.")

    return df

