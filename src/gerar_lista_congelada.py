from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from typing import Iterable

import pandas as pd
import requests

from src.filtrar_municipios import filtrar_municipios
from src.utils import is_capital, project_path


LOCALIDADES_URL = "https://servicodados.ibge.gov.br/api/v1/localidades/municipios"
SIDRA_URL_TEMPLATE = "https://apisidra.ibge.gov.br/values/t/6579/n6/{codigos}/v/9324/p/{ano}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Gera lista congelada de municípios no escopo com dados IBGE/SIDRA.")
    parser.add_argument("--ano", default="2025", help="Ano da estimativa populacional SIDRA.")
    parser.add_argument(
        "--output",
        default=str(project_path("data", "input", "municipios_ibge_escopo_congelado.csv")),
        help="Caminho do CSV congelado.",
    )
    return parser.parse_args()


def _extract_uf(item: dict) -> dict:
    regiao_imediata = item.get("regiao-imediata") or {}
    intermediaria = regiao_imediata.get("regiao-intermediaria") or {}
    if intermediaria.get("UF"):
        return intermediaria["UF"]
    microrregiao = item.get("microrregiao") or {}
    mesorregiao = microrregiao.get("mesorregiao") or {}
    if mesorregiao.get("UF"):
        return mesorregiao["UF"]
    raise ValueError(f"UF ausente no município IBGE {item.get('id')} - {item.get('nome')}")


def _chunks(values: list[str], size: int = 300) -> Iterable[list[str]]:
    for index in range(0, len(values), size):
        yield values[index : index + size]


def baixar_municipios_ibge(session=requests) -> pd.DataFrame:
    response = session.get(LOCALIDADES_URL, timeout=60)
    response.raise_for_status()
    rows: list[dict] = []
    for item in response.json():
        uf = _extract_uf(item)
        municipio = item["nome"]
        sigla = str(uf["sigla"]).upper()
        rows.append(
            {
                "Código IBGE": str(item["id"]),
                "UF": sigla,
                "Estado": uf["nome"],
                "Município": municipio,
                "Capital": is_capital(municipio, sigla),
            }
        )
    return pd.DataFrame(rows)


def baixar_populacao_sidra(codigos: list[str], ano: str = "2025", session=requests) -> dict[str, int]:
    populacao: dict[str, int] = {}
    for chunk in _chunks(codigos):
        url = SIDRA_URL_TEMPLATE.format(codigos=",".join(chunk), ano=ano)
        response = session.get(url, timeout=90)
        response.raise_for_status()
        for item in response.json()[1:]:
            valor = str(item.get("V", ""))
            if valor.isdigit():
                populacao[str(item["D1C"])] = int(valor)
    return populacao


def gerar_lista_congelada(ano: str = "2025", output: str | Path | None = None, session=requests) -> Path:
    output_path = Path(output) if output else project_path("data", "input", "municipios_ibge_escopo_congelado.csv")
    municipios = baixar_municipios_ibge(session=session)
    populacao = baixar_populacao_sidra(municipios["Código IBGE"].astype(str).tolist(), ano=ano, session=session)

    municipios["População"] = municipios["Código IBGE"].map(populacao).fillna(0).astype(int)
    municipios["Site oficial"] = ""

    filtrados = filtrar_municipios(municipios)
    congelado_em = datetime.now().date().isoformat()
    fonte_sidra = f"SIDRA 6579/v/9324/p/{ano}"

    final = pd.DataFrame(
        {
            "codigo_ibge": filtrados["Código IBGE"],
            "municipio": filtrados["Município"],
            "uf": filtrados["UF"],
            "estado": filtrados["Estado"],
            "populacao": filtrados["População"],
            "capital": filtrados["Capital"].map(lambda value: "true" if bool(value) else "false"),
            "site_oficial": filtrados["Site oficial"],
            "criterio_inclusao": filtrados["Critério de inclusão"],
            "fonte": fonte_sidra,
            "data_congelamento": congelado_em,
        }
    ).sort_values(["uf", "municipio"])

    output_path.parent.mkdir(parents=True, exist_ok=True)
    final.to_csv(output_path, index=False, encoding="utf-8")
    return output_path


def main() -> None:
    args = parse_args()
    output = gerar_lista_congelada(args.ano, args.output)
    print(f"Lista congelada gerada: {output}")


if __name__ == "__main__":
    main()
