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
    "/categoria",
    "/publicacoes",
    "/galeria",
    "/normas-legais",
    "/documentos",
    "/turismo",
)

QUERY_IGNORADAS = ("pag=", "page=", "pagina=", "pagina=404", "pg=")
SEGMENTOS_IGNORADOS = {
    "/page/",
    "/pagina/",
    "/category/",
    "/categoria/",
    "/calendario-secretaria/",
    "/downloads/",
    "/detalhe-da-materia/",
    "/detalhe-prefeito/",
    "/gabinete-militar/",
    "/galeria",
    "/agenda",
    "/planejamento-municipal/",
    "/secretarias-paginas/",
    "/turismo/",
    "gabinete-militar",
    "funcoes-da-secretaria",
    "estrutura-da-secretaria",
    "downloads-secretaria",
    "editais-e-publicacoes",
    "instituicoes-relacionadas",
    "simbolos-oficiais",
    "esqueci-minha-senha",
    "/entrar",
}

MAX_BYTES_POR_PAGINA = 2_000_000

CONTEUDO_PRINCIPAL_SELECTORS = (
    "main",
    "article",
    "[role='main']",
    ".entry-content",
    ".post-content",
    ".page-content",
    ".content-area",
    "#content",
    "#main",
)

TAGS_BOILERPLATE = ("script", "style", "noscript", "svg", "header", "nav", "footer", "aside")

BOILERPLATE_CLASS_ID_TOKENS = (
    "breadcrumb",
    "menu",
    "navbar",
    "navigation",
    "rodape",
    "footer",
    "sidebar",
    "social-share",
    "social-icons",
    "social-media",
    "rede-social",
    "redes-sociais",
    "share",
    "search",
    "acessibilidade",
)

CAMINHOS_FALLBACK_BLOQUEIO = (
    "equipe_governo.aspx",
    "equipe-de-governo",
    "equipe-governo",
    "estrutura-organizacional",
    "secretarias",
    "secretaria",
    "gabinete",
    "prefeito",
    "contato",
    "fale-conosco",
)


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
        "delay_entre_requisicoes": 3.0,
        "max_paginas_por_municipio": 60,
        "usar_playwright_quando_necessario": True,
        "browser_backend": "auto",
        "usar_cloakbrowser_quando_necessario": True,
        "usar_caminhos_fallback_bloqueio": True,
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
    for tag in soup(TAGS_BOILERPLATE):
        tag.decompose()

    for tag in list(soup.find_all(True)):
        if tag.attrs is None:
            continue
        marker = " ".join(
            str(value)
            for value in (
                tag.get("id", ""),
                " ".join(tag.get("class", [])),
                tag.get("role", ""),
            )
        ).lower()
        if any(token in marker for token in BOILERPLATE_CLASS_ID_TOKENS):
            tag.decompose()

    candidates = []
    for selector in CONTEUDO_PRINCIPAL_SELECTORS:
        candidates.extend(soup.select(selector))
    container = max(candidates, key=lambda item: len(item.get_text(" ", strip=True)), default=None)
    if not container or len(container.get_text(" ", strip=True)) < 80:
        container = soup.body or soup

    return container.get_text("\n", strip=True)


def pagina_indica_bloqueio(texto: str, html: str = "") -> bool:
    haystack = normalize_for_search(f"{texto} {html[:3000]}")
    sinais_fortes = (
        "access denied",
        "acesso negado",
        "forbidden",
        "verify you are human",
        "verifique se voce e humano",
        "cloudflare error",
        "attention required",
        "temporarily blocked",
    )
    if any(sinal in haystack for sinal in sinais_fortes):
        return True

    # reCAPTCHA em formulario de contato nao deve invalidar uma pagina oficial
    # que renderizou conteudo institucional util.
    texto_normalizado = normalize_for_search(texto)
    if any(sinal in haystack for sinal in ("captcha", "recaptcha", "cloudflare")):
        conteudo_util = len(texto_normalizado) >= 350 and any(
            sinal in texto_normalizado
            for sinal in (
                "prefeitura",
                "secretaria",
                "gabinete",
                "prefeito",
                "contato",
                "equipe de governo",
            )
        )
        return not conteudo_util
    return False


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
    if last_segment.count("-") >= 5 and not last_segment.startswith(("secretaria-", "departamento-", "diretoria-", "gabinete-", "sala-do-empreendedor")):
        return True
    if last_segment.count("-") >= 3 and any(
        token in last_segment
        for token in ("acompanhe", "visita", "lanca", "lança", "promove", "estende", "campanha", "obras-na-cidade")
    ):
        return True
    return any(token in query for token in QUERY_IGNORADAS)


def _url_chave(url: str) -> tuple[str, str, str]:
    parsed = urlparse(url)
    host = parsed.netloc.lower().removeprefix("www.")
    path = parsed.path.rstrip("/") or "/"
    return host, path, parsed.query


def _bases_fallback_bloqueio(site: str) -> list[str]:
    parsed = urlparse(site)
    host = parsed.netloc.lower()
    hosts = [host]
    if host.startswith("www."):
        hosts.append(f"www2.{host[4:]}")
    elif host.startswith("www2."):
        hosts.append(f"www.{host[5:]}")

    bases = []
    for candidate_host in dict.fromkeys(hosts):
        bases.append(clean_url(f"{parsed.scheme}://{candidate_host}/"))
    return bases


def urls_fallback_bloqueio(site: str) -> list[str]:
    urls: list[str] = []
    for base in _bases_fallback_bloqueio(site):
        for path in CAMINHOS_FALLBACK_BLOQUEIO:
            urls.append(clean_url(urljoin(base, path)))
    return list(dict.fromkeys(url for url in urls if url and not _url_deve_ser_ignorada(url)))


def _prioridade_url_relevante(url: str) -> int:
    normalized = normalize_for_search(url).replace("-", "_")
    grupos = (
        ("equipe_governo", "equipe_de_governo", "estrutura_organizacional"),
        ("gabinete", "prefeito", "vice_prefeito", "secretarias", "secretaria"),
        ("sedecon", "desenvolvimento", "seplan", "planejamento", "financas", "fazenda"),
        ("contato", "fale_conosco"),
        ("servicos", "materia", "noticia", "concursos", "licitacoes", "iptu", "nfe"),
    )
    for prioridade, tokens in enumerate(grupos):
        if any(token in normalized for token in tokens):
            return prioridade
    return len(grupos)


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

    unicos = list(dict.fromkeys(links))
    return sorted(unicos, key=lambda link: (_prioridade_url_relevante(link), unicos.index(link)))


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

    try:
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
    finally:
        close = getattr(response, "close", None)
        if callable(close):
            close()


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

    def safe_close(open_browser) -> None:
        if open_browser:
            try:
                open_browser.close()
            except Exception:
                pass

    browser = None
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            response = page.goto(url, wait_until="domcontentloaded", timeout=timeout * 1000)
            try:
                page.wait_for_timeout(1000)
            except PlaywrightError:
                pass
            html = page.content()
            final_url = clean_url(page.url)
            status_http = response.status if response else None
            browser.close()
    except PlaywrightTimeoutError:
        safe_close(browser)
        return "", "Site fora do ar", "Timeout ao acessar URL com Playwright.", url, None, "", "playwright"
    except PlaywrightError as exc:
        safe_close(browser)
        return "", "Necessita validação manual", f"Erro Playwright: {exc}", url, None, "", "playwright"
    except Exception as exc:  # pragma: no cover - proteção para falhas de browser local
        safe_close(browser)
        return "", "Necessita validação manual", f"Erro inesperado no Playwright: {exc}", url, None, "", "playwright"

    if status_http in {401, 403, 429}:
        return html, "Bloqueio técnico", f"HTTP {status_http}.", final_url, status_http, "text/html", "playwright"
    if status_http and status_http >= 500:
        return html, "Site fora do ar", f"HTTP {status_http}.", final_url, status_http, "text/html", "playwright"
    if status_http and status_http >= 400:
        return html, "Página sem informação pública", f"HTTP {status_http}.", final_url, status_http, "text/html", "playwright"
    return html, "Encontrado", "", final_url, status_http, "text/html", "playwright"


def _baixar_com_cloakbrowser(
    url: str,
    timeout: int,
) -> tuple[str, str, str, str, int | None, str, str]:
    try:
        from cloakbrowser import launch
    except ImportError as exc:
        return "", "Necessita validação manual", f"CloakBrowser indisponível: {exc}.", url, None, "", "cloakbrowser"

    browser = None
    try:
        browser = launch(headless=True)
        page = browser.new_page()
        response = page.goto(url, wait_until="domcontentloaded", timeout=timeout * 1000)
        try:
            page.wait_for_timeout(1000)
        except Exception:
            pass
        html = page.content()
        final_url = clean_url(page.url)
        status_http = response.status if response else None
        browser.close()
    except Exception as exc:  # pragma: no cover - depende do binario externo
        if browser:
            try:
                browser.close()
            except Exception:
                pass
        exc_text = str(exc)
        if "Timeout" in type(exc).__name__ or "timeout" in exc_text.lower():
            return "", "Site fora do ar", "Timeout ao acessar URL com CloakBrowser.", url, None, "", "cloakbrowser"
        return "", "Necessita validação manual", f"Erro CloakBrowser: {exc}", url, None, "", "cloakbrowser"

    if status_http in {401, 403, 429}:
        return html, "Bloqueio técnico", f"HTTP {status_http}.", final_url, status_http, "text/html", "cloakbrowser"
    if status_http and status_http >= 500:
        return html, "Site fora do ar", f"HTTP {status_http}.", final_url, status_http, "text/html", "cloakbrowser"
    if status_http and status_http >= 400:
        return html, "Página sem informação pública", f"HTTP {status_http}.", final_url, status_http, "text/html", "cloakbrowser"
    return html, "Encontrado", "", final_url, status_http, "text/html", "cloakbrowser"


def _resultado_navegador_util(resultado: tuple[str, str, str, str, int | None, str, str]) -> bool:
    html, status, *_ = resultado
    if status != "Encontrado":
        return False
    texto = html_para_texto(html)
    return bool(texto and not pagina_indica_bloqueio(texto, html))


def _baixar_com_navegador(
    url: str,
    timeout: int,
    backend: str = "auto",
    usar_cloakbrowser: bool = True,
) -> tuple[str, str, str, str, int | None, str, str]:
    backend_normalizado = normalize_for_search(backend or "auto")
    if backend_normalizado not in {"auto", "playwright", "cloakbrowser"}:
        backend_normalizado = "auto"

    tentativas: list[tuple[str, str, str, str, int | None, str, str]] = []

    if backend_normalizado in {"auto", "playwright"}:
        resultado = _baixar_com_playwright(url, timeout)
        tentativas.append(resultado)
        if backend_normalizado == "playwright" or _resultado_navegador_util(resultado) or not usar_cloakbrowser:
            return resultado

    if backend_normalizado in {"auto", "cloakbrowser"} and usar_cloakbrowser:
        resultado = _baixar_com_cloakbrowser(url, timeout)
        tentativas.append(resultado)
        if backend_normalizado == "cloakbrowser" or _resultado_navegador_util(resultado):
            return resultado

    if tentativas:
        return max(tentativas, key=lambda item: (item[1] == "Encontrado", bool(item[0])))
    return "", "Necessita validação manual", "Nenhum backend de navegador disponível.", url, None, "", "browser"


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
    browser_backend = str(config.get("browser_backend", "auto") or "auto")
    usar_cloakbrowser = bool(config.get("usar_cloakbrowser_quando_necessario", True))
    usar_fallback_bloqueio = bool(config.get("usar_caminhos_fallback_bloqueio", True))
    session = session or criar_sessao(str(config.get("user_agent")), retries)

    fila = [site]
    visitadas: set[tuple[str, str, str]] = set()
    paginas: list[PaginaColetada] = []
    fontes_consultadas: list[FonteConsultada] = []
    primeiro_status = "Encontrado"
    primeira_observacao = ""
    fallback_bloqueio_inserido = False

    def inserir_fallback_bloqueio() -> bool:
        nonlocal fallback_bloqueio_inserido
        if fallback_bloqueio_inserido or not usar_fallback_bloqueio:
            return False
        fallback_bloqueio_inserido = True
        fila_keys = {_url_chave(item) for item in fila}
        adicionados = 0
        for candidate in urls_fallback_bloqueio(site):
            candidate_key = _url_chave(candidate)
            if candidate_key in visitadas or candidate_key in fila_keys:
                continue
            if len(visitadas) + len(fila) >= max_paginas:
                break
            fila.append(candidate)
            fila_keys.add(candidate_key)
            adicionados += 1
        return adicionados > 0

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

        if status != "Encontrado" and usar_playwright and status in {"Bloqueio técnico", "Página sem informação pública"}:
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
                    gerou_texto=bool(html_para_texto(html)),
                )
            )
            html, status, observacao, final_url, status_http, content_type, metodo = _baixar_com_navegador(
                final_url or url,
                timeout,
                browser_backend,
                usar_cloakbrowser=usar_cloakbrowser,
            )
            if len(visitadas) == 1 and status == "Encontrado":
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
                if inserir_fallback_bloqueio():
                    continue
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
            html, status, observacao, final_url, status_http, content_type, metodo = _baixar_com_navegador(
                final_url or url,
                timeout,
                browser_backend,
                usar_cloakbrowser=usar_cloakbrowser,
            )
            texto = html_para_texto(html)

        if pagina_indica_bloqueio(texto, html) and usar_playwright and metodo not in {"playwright", "cloakbrowser"}:
            fontes_consultadas.append(
                FonteConsultada(
                    url=url,
                    url_final=final_url or url,
                    status="Bloqueio técnico",
                    observacoes="Página indica captcha, recaptcha ou bloqueio de acesso; tentando navegador.",
                    status_http=status_http,
                    content_type=content_type,
                    metodo=metodo,
                    data_hora=datetime.now().isoformat(timespec="seconds"),
                    gerou_texto=bool(texto),
                )
            )
            html_nav, status_nav, observacao_nav, final_url_nav, status_http_nav, content_type_nav, metodo_nav = _baixar_com_navegador(
                final_url or url,
                timeout,
                browser_backend,
                usar_cloakbrowser=usar_cloakbrowser,
            )
            texto_nav = html_para_texto(html_nav)
            if status_nav == "Encontrado" and texto_nav and not pagina_indica_bloqueio(texto_nav, html_nav):
                html, status, observacao, final_url, status_http, content_type, metodo = (
                    html_nav,
                    status_nav,
                    observacao_nav,
                    final_url_nav,
                    status_http_nav,
                    content_type_nav,
                    metodo_nav,
                )
                texto = texto_nav

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
            if len(visitadas) == 1 and not paginas:
                if inserir_fallback_bloqueio():
                    if logger:
                        logger.warning("Primeira página bloqueada; tentando caminhos institucionais alternativos.")
                    continue
                return ResultadoColeta([], "Bloqueio técnico", "Página indica captcha, recaptcha ou bloqueio de acesso.", fontes_consultadas)
            if logger:
                logger.warning("Página ignorada por bloqueio aparente: %s", url)
            continue

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
