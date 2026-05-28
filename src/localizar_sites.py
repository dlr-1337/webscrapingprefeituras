from __future__ import annotations

import re
from urllib.parse import parse_qs, quote_plus, urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup

from src.utils import clean_url, normalize_for_search, slugify_municipio


CONECTORES_TOPONIMICOS = {"d", "da", "de", "do", "das", "dos", "e"}
STATUS_BLOQUEIO_LOCALIZAVEL = {401, 403, 406, 429, 503}
HEADERS_NAVEGADOR = {
    "User-Agent": "Robo de coleta institucional - contato profissional",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
}
DOMINIOS_BLOQUEADOS_BUSCA = (
    "facebook.com",
    "instagram.com",
    "linkedin.com",
    "youtube.com",
    "youtu.be",
    "wikipedia.org",
    "leismunicipais.com.br",
    "jusbrasil.com.br",
    "escavador.com",
    "cnpj.biz",
    "empresascnpj.com",
    "diariooficial",
)
TOKENS_HOST_BLOQUEADOS_BUSCA = (
    "camara",
    "camaras",
    "legislativo",
    "vereador",
    "transparencia",
    "diariooficial",
    "educacao",
    "saude",
)


def _deduplicar(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def slugs_municipio(municipio: str) -> list[str]:
    texto = normalize_for_search(municipio)
    tokens = re.findall(r"[a-z0-9]+", texto)
    tokens_relevantes = [token for token in tokens if token not in CONECTORES_TOPONIMICOS]

    candidatos = [slugify_municipio(municipio)]
    if tokens_relevantes:
        candidatos.append("".join(tokens_relevantes))
    if len(tokens_relevantes) >= 2:
        candidatos.append("".join(tokens_relevantes[:2]))
    if len(tokens) >= 2:
        candidatos.append("".join(tokens[:2]))

    return _deduplicar([slug for slug in candidatos if len(slug) >= 3])


def _urls_para_slug(slug: str, uf: str) -> list[str]:
    host_groups = (
        (f"{slug}.{uf}.gov.br", f"www.{slug}.{uf}.gov.br"),
        (f"prefeitura.{slug}.{uf}.gov.br", f"www.prefeitura.{slug}.{uf}.gov.br"),
    )
    urls: list[str] = []
    for hosts in host_groups:
        for scheme in ("https", "http"):
            for host in hosts:
                urls.append(f"{scheme}://{host}/")
    return urls


def inferir_urls_basicas(municipio: str, uf: str) -> list[str]:
    uf = str(uf).lower()
    slugs = slugs_municipio(municipio)
    if not slugs or not uf:
        return []
    urls: list[str] = []
    for slug in slugs:
        urls.extend(_urls_para_slug(slug, uf))
    return _deduplicar(urls)


def testar_url(
    url: str,
    timeout: int = 5,
    session: requests.Session | None = None,
    aceitar_bloqueio: bool = False,
) -> bool:
    sess = session or requests.Session()
    try:
        response = sess.get(url, timeout=timeout, allow_redirects=True, headers=HEADERS_NAVEGADOR)
        content_type = response.headers.get("content-type", "").lower()
        html = "html" in content_type or "text" in content_type or not content_type
        if response.status_code < 400:
            return html
        return aceitar_bloqueio and response.status_code in STATUS_BLOQUEIO_LOCALIZAVEL and html
    except (requests.Timeout, requests.exceptions.SSLError):
        return aceitar_bloqueio
    except requests.RequestException:
        return False


def _url_resultado_busca(href: str) -> str:
    href = str(href or "").strip()
    if not href:
        return ""
    if href.startswith("//"):
        href = f"https:{href}"
    parsed = urlparse(href)
    if parsed.netloc.endswith("duckduckgo.com") and parsed.path.startswith("/l/"):
        return parse_qs(parsed.query).get("uddg", [""])[0]
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return href
    return ""


def _host_bloqueado(host: str) -> bool:
    host = host.lower().removeprefix("www.")
    if any(domain in host for domain in DOMINIOS_BLOQUEADOS_BUSCA):
        return True
    host_compacto = re.sub(r"[^a-z0-9]+", "", host)
    return any(token in host_compacto for token in TOKENS_HOST_BLOQUEADOS_BUSCA)


def _parece_site_oficial(url: str, municipio: str, uf: str, texto_resultado: str = "") -> bool:
    site = clean_url(url)
    if not site:
        return False
    parsed = urlparse(site)
    host = parsed.netloc.lower().removeprefix("www.")
    uf = str(uf or "").lower()
    if _host_bloqueado(host):
        return False

    host_compacto = re.sub(r"[^a-z0-9]+", "", host)
    slugs = slugs_municipio(municipio)
    dominio_municipal = host.endswith(f".{uf}.gov.br") or host.endswith(".gov.br")
    if dominio_municipal and any(slug in host_compacto for slug in slugs):
        return True

    texto = normalize_for_search(f"{texto_resultado} {host}")
    tokens = [
        token
        for token in re.findall(r"[a-z0-9]+", normalize_for_search(municipio))
        if token not in CONECTORES_TOPONIMICOS
    ]
    if not dominio_municipal or not tokens:
        return False
    menciona_prefeitura = "prefeitura" in texto or "municipio" in texto
    tokens_necessarios = tokens if len(tokens) == 1 else tokens[:2]
    return menciona_prefeitura and all(token in texto for token in tokens_necessarios)


def _raiz_url(url: str) -> str:
    site = clean_url(url)
    parsed = urlparse(site)
    if not parsed.scheme or not parsed.netloc:
        return ""
    return clean_url(f"{parsed.scheme}://{parsed.netloc}/")


def buscar_site_oficial_web(
    municipio: str,
    uf: str,
    timeout: int = 5,
    session: requests.Session | None = None,
    max_resultados: int = 5,
) -> tuple[str, str]:
    sess = session or requests.Session()
    query = quote_plus(f"prefeitura {municipio} {uf} site oficial")
    search_url = f"https://duckduckgo.com/html/?q={query}"
    try:
        response = sess.get(search_url, timeout=timeout, headers=HEADERS_NAVEGADOR)
    except requests.RequestException as exc:
        return "", f"Busca web oficial falhou: {exc}"

    if response.status_code >= 400:
        return "", f"Busca web oficial retornou HTTP {response.status_code}."

    html = getattr(response, "text", "") or ""
    soup = BeautifulSoup(html, "html.parser")
    candidatos: list[tuple[str, str]] = []
    for link in soup.select("a[href]"):
        href = _url_resultado_busca(str(link.get("href", "")))
        texto = link.get_text(" ", strip=True)
        if not href or not _parece_site_oficial(href, municipio, uf, texto):
            continue
        raiz = _raiz_url(href)
        if not raiz:
            continue
        candidatos.append((raiz, href))
        if len(candidatos) >= max_resultados:
            break

    candidatos_unicos: list[tuple[str, str]] = []
    for raiz, origem in candidatos:
        if any(raiz == existente for existente, _ in candidatos_unicos):
            continue
        candidatos_unicos.append((raiz, origem))

    for raiz, origem in candidatos_unicos:
        if testar_url(raiz, timeout=timeout, session=session, aceitar_bloqueio=True):
            return raiz, f"Site localizado por busca web oficial; resultado: {origem}"

    return "", "Busca web oficial não encontrou site com evidência suficiente."


def localizar_site(
    municipio: str,
    uf: str,
    site_existente: str | None = None,
    testar_inferencia: bool = False,
    timeout: int = 5,
    session: requests.Session | None = None,
    usar_busca_web: bool = False,
    max_resultados_busca: int = 5,
) -> tuple[str, str, str]:
    site = clean_url(site_existente)
    if site:
        return site, "Encontrado", "Site informado na base de municípios."

    candidatos = inferir_urls_basicas(municipio, uf)
    if testar_inferencia:
        for candidato in candidatos:
            if testar_url(candidato, timeout=timeout, session=session, aceitar_bloqueio=True):
                return clean_url(candidato), "Necessita validação manual", "Site inferido automaticamente; validar antes da entrega."

    observacoes_busca = ""
    if usar_busca_web:
        site_busca, observacoes_busca = buscar_site_oficial_web(
            municipio,
            uf,
            timeout=timeout,
            session=session,
            max_resultados=max_resultados_busca,
        )
        if site_busca:
            return clean_url(site_busca), "Necessita validação manual", observacoes_busca

    observacao = "Site não informado na base. Candidatos básicos: " + ", ".join(candidatos)
    if observacoes_busca:
        observacao = f"{observacao}. {observacoes_busca}"
    return "", "Site não localizado", observacao


def preencher_sites(
    df: pd.DataFrame,
    testar_inferencia: bool = False,
    timeout: int = 5,
    session: requests.Session | None = None,
    usar_busca_web: bool = False,
    max_resultados_busca: int = 5,
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
            usar_busca_web=usar_busca_web,
            max_resultados_busca=max_resultados_busca,
        )
        sites.append(site)
        status.append(site_status)
        observacoes.append(obs)

    result["Site oficial"] = sites
    result["Status localização site"] = status
    result["Observações localização site"] = observacoes
    return result
