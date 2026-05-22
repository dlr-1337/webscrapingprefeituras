import requests

from src.coletar_paginas import (
    coletar_paginas,
    extrair_links_relevantes,
    html_para_texto,
    pagina_indica_bloqueio,
)


class FakeResponse:
    def __init__(self, url, text="", status_code=200, content_type="text/html"):
        self.url = url
        self.text = text
        self.status_code = status_code
        self.headers = {"content-type": content_type}


class FakeSession:
    def __init__(self, responses=None, exception=None):
        self.responses = dict(responses or {})
        self.exception = exception
        self.urls = []

    def get(self, url, **kwargs):
        self.urls.append((url, kwargs))
        if self.exception:
            raise self.exception
        response = self.responses[url]
        if isinstance(response, Exception):
            raise response
        return response


def test_html_para_texto_remove_scripts_styles_e_tags_sem_texto():
    html = """
    <html>
      <style>.x { color: red; }</style>
      <script>alert('x')</script>
      <noscript>sem js</noscript>
      <body><h1>Gabinete</h1><p>Prefeito João Silva</p></body>
    </html>
    """

    texto = html_para_texto(html)

    assert "Gabinete" in texto
    assert "Prefeito João Silva" in texto
    assert "alert" not in texto
    assert "color" not in texto
    assert "sem js" not in texto


def test_pagina_indica_bloqueio_por_texto_ou_html():
    assert pagina_indica_bloqueio("Acesso negado")
    assert pagina_indica_bloqueio("", "<div>Cloudflare verify you are human</div>")
    assert not pagina_indica_bloqueio("Página de contatos institucional")


def test_extrair_links_relevantes_filtra_dominio_tipo_e_palavra_chave():
    html = """
    <a href="/gabinete">Gabinete do prefeito</a>
    <a href="/gabinete#top">Gabinete do prefeito</a>
    <a href="https://cidade.sp.gov.br/contato">Fale conosco</a>
    <a href="https://externo.test/contato">Contato externo</a>
    <a href="/arquivo.pdf">Secretaria em PDF</a>
    <a href="/noticias/prefeito-visita-obra">Prefeito visita obra</a>
    <a href="/noticias/desenvolvimento-economico?pag=2">Desenvolvimento econômico</a>
    <a href="/gabinete/prefeito-discute-com-parlamentares-federais-avancos-para-saneamento">Gabinete</a>
    <a href="/category/secretaria-de-desenvolvimento-social/page/2/">Secretaria</a>
    <a href="/publicacoes/secretaria-de-planejamento/">Planejamento</a>
    <a href="/galeria-de-prefeitos/">Prefeitos</a>
    <a href="/administracao/entrar">Entrar</a>
    <a href="/documentos/">Documentos da secretaria</a>
    <a href="/detalhe-da-materia/info/3032/simbolos-oficiais/">Secretaria símbolos</a>
    <a href="/estrutura-organizacional/?pg=1&tax=tipo-secretaria%3D5">Secretaria paginada</a>
    <a href="/portal/detalhe-prefeito/21/">Prefeito histórico</a>
    <a href="/portal/secretarias-paginas/30/conselho/">Conselho</a>
    <a href="/portal/turismo/0/9/4813/praca">Turismo</a>
    <a href="mailto:gabinete@cidade.gov.br">Email</a>
    <a href="/noticias">Noticias</a>
    """

    links = extrair_links_relevantes(html, "https://cidade.sp.gov.br/", ["gabinete", "contato"])

    assert links == [
        "https://cidade.sp.gov.br/gabinete",
        "https://cidade.sp.gov.br/contato",
    ]


def test_coletar_paginas_retorna_site_nao_localizado_quando_site_vazio():
    result = coletar_paginas("", ["gabinete"])

    assert result.paginas == []
    assert result.status == "Site não localizado"
    assert result.fontes_consultadas[0].status == "Site não localizado"


def test_coletar_paginas_visita_home_e_links_relevantes_sem_rede_real():
    home = """
    <html><body>
      <h1>Prefeitura</h1>
      <a href="/gabinete">Gabinete</a>
      <a href="/secretaria.pdf">Secretaria</a>
    </body></html>
    """
    gabinete = "<html><body>Gabinete do Prefeito João Silva contato@cidade.gov.br</body></html>"
    session = FakeSession(
        {
            "https://cidade.sp.gov.br/": FakeResponse("https://cidade.sp.gov.br/", home),
            "https://cidade.sp.gov.br/gabinete": FakeResponse("https://cidade.sp.gov.br/gabinete", gabinete),
        }
    )

    result = coletar_paginas(
        "cidade.sp.gov.br",
        ["gabinete", "secretaria"],
        config={"timeout_segundos": 1, "retries": 0, "delay_entre_requisicoes": 0, "max_paginas_por_municipio": 5, "user_agent": "teste"},
        session=session,
    )

    assert result.status == "Encontrado"
    assert len(result.paginas) == 2
    assert [pagina.url for pagina in result.paginas] == [
        "https://cidade.sp.gov.br/",
        "https://cidade.sp.gov.br/gabinete",
    ]
    assert [fonte.status for fonte in result.fontes_consultadas] == ["Encontrado", "Encontrado"]
    assert all(fonte.gerou_texto for fonte in result.fontes_consultadas)


def test_coletar_paginas_deduplica_www_http_e_https():
    home = """
    <html><body>
      <h1>Prefeitura</h1>
      <a href="http://cidade.sp.gov.br/gabinete">Gabinete</a>
      <a href="https://www.cidade.sp.gov.br/gabinete/">Gabinete duplicado</a>
    </body></html>
    """
    gabinete = "<html><body>Gabinete contato@cidade.gov.br</body></html>"
    session = FakeSession(
        {
            "https://cidade.sp.gov.br/": FakeResponse("https://cidade.sp.gov.br/", home),
            "http://cidade.sp.gov.br/gabinete": FakeResponse("http://cidade.sp.gov.br/gabinete", gabinete),
        }
    )

    result = coletar_paginas(
        "https://cidade.sp.gov.br/",
        ["gabinete"],
        config={"timeout_segundos": 1, "retries": 0, "delay_entre_requisicoes": 0, "max_paginas_por_municipio": 5, "user_agent": "teste"},
        session=session,
    )

    assert [pagina.url for pagina in result.paginas] == [
        "https://cidade.sp.gov.br/",
        "http://cidade.sp.gov.br/gabinete",
    ]


def test_coletar_paginas_detecta_bloqueio_no_primeiro_html():
    session = FakeSession(
        {"https://cidade.sp.gov.br/": FakeResponse("https://cidade.sp.gov.br/", "<html>captcha requerido</html>")}
    )

    result = coletar_paginas(
        "https://cidade.sp.gov.br/",
        ["gabinete"],
        config={"timeout_segundos": 1, "retries": 0, "delay_entre_requisicoes": 0, "max_paginas_por_municipio": 5, "user_agent": "teste"},
        session=session,
    )

    assert result.status == "Bloqueio técnico"
    assert result.paginas == []
    assert result.fontes_consultadas[0].status == "Bloqueio técnico"


def test_coletar_paginas_classifica_timeout_e_http_bloqueado():
    timeout_result = coletar_paginas(
        "https://timeout.test/",
        ["contato"],
        config={"timeout_segundos": 1, "retries": 0, "delay_entre_requisicoes": 0, "max_paginas_por_municipio": 5, "user_agent": "teste"},
        session=FakeSession(exception=requests.Timeout("demorou")),
    )
    blocked_result = coletar_paginas(
        "https://bloqueio.test/",
        ["contato"],
        config={"timeout_segundos": 1, "retries": 0, "delay_entre_requisicoes": 0, "max_paginas_por_municipio": 5, "user_agent": "teste"},
        session=FakeSession({"https://bloqueio.test/": FakeResponse("https://bloqueio.test/", "bloqueado", 403)}),
    )

    assert timeout_result.status == "Site fora do ar"
    assert "Timeout" in timeout_result.observacoes
    assert timeout_result.fontes_consultadas[0].status == "Site fora do ar"
    assert blocked_result.status == "Bloqueio técnico"
    assert "HTTP 403" in blocked_result.observacoes
    assert blocked_result.fontes_consultadas[0].status_http == 403


def test_coletar_paginas_usa_playwright_quando_requests_nao_tem_texto(monkeypatch):
    import src.coletar_paginas as coletor

    session = FakeSession({"https://cidade.sp.gov.br/": FakeResponse("https://cidade.sp.gov.br/", "")})

    def fake_playwright(url, timeout):
        return "<html><body>Gabinete do Prefeito</body></html>", "Encontrado", "", url, 200, "text/html", "playwright"

    monkeypatch.setattr(coletor, "_baixar_com_playwright", fake_playwright)

    result = coletar_paginas(
        "https://cidade.sp.gov.br/",
        ["gabinete"],
        config={"timeout_segundos": 1, "retries": 0, "delay_entre_requisicoes": 0, "max_paginas_por_municipio": 5, "user_agent": "teste", "usar_playwright_quando_necessario": True},
        session=session,
    )

    assert result.paginas[0].texto == "Gabinete do Prefeito"
    assert [fonte.metodo for fonte in result.fontes_consultadas] == ["requests", "playwright"]
