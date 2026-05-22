from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable
from urllib.parse import urldefrag, urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.utils import clean_url, load_yaml, normalize_for_search, project_path, same_domain


EXTENSOES_IGNORADAS = {
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".zip",
    ".rar",
    ".7z",
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".mp4",
    ".mp3",
}

CAMINHOS_IGNORADOS = (
    "/noticia",
    "/noticias",
    "/evento",
    "/eventos",
    "/imprensa",
    "/blog",
    "/avaliar",
    "/category",
    "/publicacoes",
    "/galeria",
    "/normas-legais",
    "/documentos",
    "/turismo",
)

QUERY_IGNORADAS = ("pag=", "page=", "pagina=", "pg=")
SEGMENTOS_IGNORADOS = {
    "/page/",
    "/pagina/",
    "/category/",
    "/downloads/",
    "/detalhe-da-materia/",
    "/detalhe-prefeito/",
    "/galeria",
    "/secretarias-paginas/",
    "/turismo/",
    "simbolos-oficiais",
    "esqueci-minha-senha",
    "/entrar",
}

MAX_BYTES_POR_PAGINA = 2_000_000


@dataclass(slots=True)
class PaginaColetada:
    url: str
    texto: str
    html: str
    status: str = "Encontrado"
    observacoes: str = ""


@dataclass(slots=True)
class FonteConsultada:
    url: str
    url_final: str
    status: str
    observacoes: str = ""
    status_http: int | None = None
    content_type: str = ""
    metodo: str = "requests"
    data_hora: str = ""
    gerou_texto: bool = False


@dataclass(slots=True)
class ResultadoColeta:
    paginas: list[PaginaColetada]
    status: str
    observacoes: str = ""
    fontes_consultadas: list[FonteConsultada] | None = None


def carregar_config_scraping(path: str | Path | None = None) -> dict:
    config_path = Path(path) if path else project_path("config", "scraping.yml")
    defaults = {
        "timeout_segundos": 20,
        "retries": 2,
        "delay_entre_requisicoes": 1.5,
        "max_paginas_por_municipio": 40,
        "usar_playwright_quando_necessario": True,
        "user_agent": "Robo de coleta institucional - contato profissional",
    }
    defaults.update(load_yaml(config_path))
    return defaults


def criar_sessao(user_agent: str, retries: int) -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": user_agent})
    retry = Retry(
        total=retries,
        connect=retries,
        read=0,
        status=retries,
        backoff_factor=0.5,
        status_forcelist=(500, 502, 503, 504),
        allowed_methods=("GET", "HEAD"),
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def html_para_texto(html: str) -> str:
    soup = BeautifulSoup(html or "", "html.parser")
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()
    return soup.get_text("\n", strip=True)


def pagina_indica_bloqueio(texto: str, html: str = "") -> bool:
    haystack = normalize_for_search(f"{texto} {html[:3000]}")
    sinais = (
        "captcha",
        "recaptcha",
        "cloudflare",
        "access denied",
        "acesso negado",
        "forbidden",
        "verify you are human",
    )
    return any(sinal in haystack for sinal in sinais)


def _url_deve_ser_ignorada(url: str) -> bool:
    parsed = urlparse(url)
    path = parsed.path.lower()
    query = parsed.query.lower()
    if any(path.endswith(ext) for ext in EXTENSOES_IGNORADAS):
        return True
    if any(path.startswith(prefix) for prefix in CAMINHOS_IGNORADOS):
        return True
    if any(segment in path for segment in SEGMENTOS_IGNORADOS):
        return True
    last_segment = path.rstrip("/").rsplit("/", 1)[-1]
    if len(last_segment) >= 45 and last_segment.count("-") >= 5:
        return True
    return any(token in query for token in QUERY_IGNORADAS)


def _url_chave(url: str) -> tuple[str, str, str]:
    parsed = urlparse(url)
    host = parsed.netloc.lower().removeprefix("www.")
    path = parsed.path.rstrip("/") or "/"
    return host, path, parsed.query


def extrair_links_relevantes(html: str, base_url: str, palavras_chave: Iterable[str]) -> list[str]:
    soup = BeautifulSoup(html or "", "html.parser")
    palavras = [normalize_for_search(word) for word in palavras_chave]
    links: list[str] = []

    for anchor in soup.find_all("a", href=True):
        href = str(anchor.get("href", "")).strip()
        if not href or href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        absolute = clean_url(urljoin(base_url, href))
        absolute = urldefrag(absolute).url
        if not absolute or not same_domain(absolute, base_url) or _url_deve_ser_ignorada(absolute):
            continue

        text = normalize_for_search(f"{anchor.get_text(' ', strip=True)} {absolute}")
        if any(word in text for word in palavras):
            links.append(absolute)

    return list(dict.fromkeys(links))


def _baixar(
    session: requests.Session,
    url: str,
    timeout: int,
) -> tuple[str, str, str, str, int | None, str, str]:
    try:
        response = session.get(url, timeout=timeout, allow_redirects=True, stream=True)
    except requests.Timeout:
        return "", "Site fora do ar", "Timeout ao acessar URL.", url, None, "", "requests"
    except requests.RequestException as exc:
        return "", "Site fora do ar", f"Erro de conexão: {exc}", url, None, "", "requests"

    final_url = clean_url(response.url)
    content_type = response.headers.get("content-type", "").lower()
    if response.status_code in {401, 403, 429}:
        return _ler_texto_limitado(response), "Bloqueio técnico", f"HTTP {response.status_code}.", final_url, response.status_code, content_type, "requests"
    if response.status_code >= 500:
        return _ler_texto_limitado(response), "Site fora do ar", f"HTTP {response.status_code}.", final_url, response.status_code, content_type, "requests"
    if response.status_code >= 400:
        return _ler_texto_limitado(response), "Página sem informação pública", f"HTTP {response.status_code}.", final_url, response.status_code, content_type, "requests"

    if content_type and "html" not in content_type and "text" not in content_type:
        return "", "Página sem informação pública", f"Conteúdo ignorado: {content_type}.", final_url, response.status_code, content_type, "requests"

    return _ler_texto_limitado(response), "Encontrado", "", final_url, response.status_code, content_type, "requests"


def _ler_texto_limitado(response: requests.Response, max_bytes: int = MAX_BYTES_POR_PAGINA) -> str:
    if not hasattr(response, "iter_content"):
        return response.text

    chunks: list[bytes] = []
    total = 0
    try:
        for chunk in response.iter_content(chunk_size=65536):
            if not chunk:
                continue
            chunks.append(chunk)
            total += len(chunk)
            if total >= max_bytes:
                break
    except requests.RequestException:
        if not chunks:
            raise

    content = b"".join(chunks)
    encoding = getattr(response, "encoding", None) or "utf-8"
    return content.decode(encoding, errors="replace")


def _baixar_com_playwright(
    url: str,
    timeout: int,
) -> tuple[str, str, str, str, int | None, str, str]:
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        return "", "Necessita validação manual", f"Playwright indisponível: {exc}.", url, None, "", "playwright"

    browser = None
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            response = page.goto(url, wait_until="networkidle", timeout=timeout * 1000)
            html = page.content()
            final_url = clean_url(page.url)
            status_http = response.status if response else None
            browser.close()
    except PlaywrightTimeoutError:
        if browser:
            browser.close()
        return "", "Site fora do ar", "Timeout ao acessar URL com Playwright.", url, None, "", "playwright"
    except PlaywrightError as exc:
        if browser:
            browser.close()
        return "", "Necessita validação manual", f"Erro Playwright: {exc}", url, None, "", "playwright"
    except Exception as exc:  # pragma: no cover - proteção para falhas de browser local
        if browser:
            browser.close()
        return "", "Necessita validação manual", f"Erro inesperado no Playwright: {exc}", url, None, "", "playwright"

    if status_http in {401, 403, 429}:
        return html, "Bloqueio técnico", f"HTTP {status_http}.", final_url, status_http, "text/html", "playwright"
    if status_http and status_http >= 500:
        return html, "Site fora do ar", f"HTTP {status_http}.", final_url, status_http, "text/html", "playwright"
    if status_http and status_http >= 400:
        return html, "Página sem informação pública", f"HTTP {status_http}.", final_url, status_http, "text/html", "playwright"
    return html, "Encontrado", "", final_url, status_http, "text/html", "playwright"


def coletar_paginas(
    site: str,
    palavras_chave: Iterable[str],
    config: dict | None = None,
    logger: logging.Logger | None = None,
    session: requests.Session | None = None,
) -> ResultadoColeta:
    config = config or carregar_config_scraping()
    site = clean_url(site)
    if not site:
        fonte = FonteConsultada(
            url="",
            url_final="",
            status="Site não localizado",
            observacoes="Município sem site oficial informado.",
            data_hora=datetime.now().isoformat(timespec="seconds"),
        )
        return ResultadoColeta([], "Site não localizado", "Município sem site oficial informado.", [fonte])

    timeout = int(config.get("timeout_segundos", 20))
    retries = int(config.get("retries", 2))
    delay = float(config.get("delay_entre_requisicoes", 1.5))
    max_paginas = int(config.get("max_paginas_por_municipio", 40))
    usar_playwright = bool(config.get("usar_playwright_quando_necessario", True))
    session = session or criar_sessao(str(config.get("user_agent")), retries)

    fila = [site]
    visitadas: set[tuple[str, str, str]] = set()
    paginas: list[PaginaColetada] = []
    fontes_consultadas: list[FonteConsultada] = []
    primeiro_status = "Encontrado"
    primeira_observacao = ""

    while fila and len(visitadas) < max_paginas:
        url = fila.pop(0)
        url_key = _url_chave(url)
        if url_key in visitadas:
            continue
        visitadas.add(url_key)
        if len(visitadas) > 1:
            time.sleep(delay)

        if logger:
            logger.info("Acessando página: %s", url)

        html, status, observacao, final_url, status_http, content_type, metodo = _baixar(session, url, timeout)
        if len(visitadas) == 1:
            primeiro_status = status
            primeira_observacao = observacao

        if status != "Encontrado":
            fontes_consultadas.append(
                FonteConsultada(
                    url=url,
                    url_final=final_url or url,
                    status=status,
                    observacoes=observacao,
                    status_http=status_http,
                    content_type=content_type,
                    metodo=metodo,
                    data_hora=datetime.now().isoformat(timespec="seconds"),
                    gerou_texto=False,
                )
            )
            if logger:
                logger.warning("Página ignorada: %s | %s | %s", url, status, observacao)
            if len(visitadas) == 1 and status in {"Site fora do ar", "Bloqueio técnico"}:
                return ResultadoColeta([], status, observacao, fontes_consultadas)
            continue

        texto = html_para_texto(html)
        if not texto and usar_playwright:
            fontes_consultadas.append(
                FonteConsultada(
                    url=url,
                    url_final=final_url or url,
                    status=status,
                    observacoes=observacao or "HTML sem texto visível; tentando fallback Playwright.",
                    status_http=status_http,
                    content_type=content_type,
                    metodo=metodo,
                    data_hora=datetime.now().isoformat(timespec="seconds"),
                    gerou_texto=False,
                )
            )
            html, status, observacao, final_url, status_http, content_type, metodo = _baixar_com_playwright(final_url or url, timeout)
            texto = html_para_texto(html)

        if pagina_indica_bloqueio(texto, html):
            fontes_consultadas.append(
                FonteConsultada(
                    url=url,
                    url_final=final_url or url,
                    status="Bloqueio técnico",
                    observacoes="Página indica captcha, recaptcha ou bloqueio de acesso.",
                    status_http=status_http,
                    content_type=content_type,
                    metodo=metodo,
                    data_hora=datetime.now().isoformat(timespec="seconds"),
                    gerou_texto=bool(texto),
                )
            )
            return ResultadoColeta([], "Bloqueio técnico", "Página indica captcha, recaptcha ou bloqueio de acesso.", fontes_consultadas)

        fontes_consultadas.append(
            FonteConsultada(
                url=url,
                url_final=final_url or url,
                status=status,
                observacoes=observacao,
                status_http=status_http,
                content_type=content_type,
                metodo=metodo,
                data_hora=datetime.now().isoformat(timespec="seconds"),
                gerou_texto=bool(texto),
            )
        )

        if status != "Encontrado":
            if logger:
                logger.warning("Página ignorada: %s | %s | %s", url, status, observacao)
            continue

        if texto:
            paginas.append(PaginaColetada(url=final_url or url, texto=texto, html=html))

        for link in extrair_links_relevantes(html, final_url or url, palavras_chave):
            link_key = _url_chave(link)
            fila_keys = {_url_chave(item) for item in fila}
            if link_key not in visitadas and link_key not in fila_keys and len(visitadas) + len(fila) < max_paginas:
                fila.append(link)

    if paginas:
        return ResultadoColeta(paginas, "Encontrado", f"{len(paginas)} página(s) coletada(s).", fontes_consultadas)
    return ResultadoColeta([], primeiro_status, primeira_observacao or "Nenhuma página textual relevante foi coletada.", fontes_consultadas)
