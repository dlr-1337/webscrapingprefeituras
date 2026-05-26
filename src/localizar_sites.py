from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd
import requests

from src.utils import clean_url, slugify_municipio


def inferir_urls_basicas(municipio: str, uf: str) -> list[str]:
    slug = slugify_municipio(municipio)
    uf = str(uf).lower()
    if not slug or not uf:
        return []
    return [
        f"https://www.{slug}.{uf}.gov.br/",
        f"https://{slug}.{uf}.gov.br/",
        f"http://www.{slug}.{uf}.gov.br/",
        f"http://{slug}.{uf}.gov.br/",
        f"https://www.prefeitura.{slug}.{uf}.gov.br/",
        f"https://prefeitura.{slug}.{uf}.gov.br/",
        f"http://www.prefeitura.{slug}.{uf}.gov.br/",
        f"http://prefeitura.{slug}.{uf}.gov.br/",
    ]


def testar_url(url: str, timeout: int = 5, session: requests.Session | None = None) -> bool:
    sess = session or requests.Session()
    try:
        response = sess.get(url, timeout=timeout, allow_redirects=True)
        content_type = response.headers.get("content-type", "").lower()
        return response.status_code < 400 and ("html" in content_type or not content_type)
    except requests.RequestException:
        return False


def localizar_site(
    municipio: str,
    uf: str,
    site_existente: str | None = None,
    testar_inferencia: bool = False,
    timeout: int = 5,
    session: requests.Session | None = None,
) -> tuple[str, str, str]:
    site = clean_url(site_existente)
    if site:
        return site, "Encontrado", "Site informado na base de municípios."

    candidatos = inferir_urls_basicas(municipio, uf)
    if testar_inferencia:
        for candidato in candidatos:
            if testar_url(candidato, timeout=timeout, session=session):
                return clean_url(candidato), "Necessita validação manual", "Site inferido automaticamente; validar antes da entrega."

    observacao = "Site não informado na base. Candidatos básicos: " + ", ".join(candidatos)
    return "", "Site não localizado", observacao


def preencher_sites(
    df: pd.DataFrame,
    testar_inferencia: bool = False,
    timeout: int = 5,
    session: requests.Session | None = None,
) -> pd.DataFrame:
    result = df.copy()
    sites: list[str] = []
    status: list[str] = []
    observacoes: list[str] = []

    for _, row in result.iterrows():
        site, site_status, obs = localizar_site(
            municipio=str(row.get("Município", "")),
            uf=str(row.get("UF", "")),
            site_existente=str(row.get("Site oficial", "")),
            testar_inferencia=testar_inferencia,
            timeout=timeout,
            session=session,
        )
        sites.append(site)
        status.append(site_status)
        observacoes.append(obs)

    result["Site oficial"] = sites
    result["Status localização site"] = status
    result["Observações localização site"] = observacoes
    return result
