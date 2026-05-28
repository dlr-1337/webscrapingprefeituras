import requests

from src.coletar_paginas import (
    _url_deve_ser_ignorada,
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


class FakeStreamResponse(FakeResponse):
    def __init__(self, url, chunks, status_code=200, content_type="text/html"):
        super().__init__(url, "", status_code, content_type)
        self.chunks = chunks
        self.closed = False
        self.encoding = "utf-8"

    def iter_content(self, chunk_size=65536):
        yield from self.chunks

    def close(self):
        self.closed = True


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


def test_html_para_texto_prioriza_conteudo_principal_e_remove_boilerplate():
    html = """
    <html>
      <body>
        <header>Prefeito Secretarias Autarquias</header>
        <nav>Vice-Prefeito Gabinete</nav>
        <main>
          <h1>Prefeito</h1>
          <h2>Alysson Bestene Lins</h2>
          <p>Contatos: alysson.bestene@riobranco.ac.gov.br</p>
        </main>
        <footer>Municipal de Educacao</footer>
      </body>
    </html>
    """

    texto = html_para_texto(html)

    assert "Alysson Bestene Lins" in texto
    assert "alysson.bestene@riobranco.ac.gov.br" in texto
    assert "Prefeito Secretarias" not in texto
    assert "Municipal de Educa" not in texto


def test_html_para_texto_preserva_mailto_tel_e_remove_cookie():
    html = """
    <html>
      <body>
        <main>
          <h1>Prefeito</h1>
          <h2>Wilson do Cafe</h2>
          <a href="mailto:gabinete@cidade.gov.br?subject=Contato">Email</a>
          <a href="tel:+5577999990000">Telefone</a>
        </main>
        <div id="cookie-card">
          Preferencias de Cookies
          Utilizamos cookies para melhorar sua experiencia.
          <button>Concordar e Fechar</button>
        </div>
      </body>
    </html>
    """

    texto = html_para_texto(html)

    assert "Wilson do Cafe" in texto
    assert "gabinete@cidade.gov.br" in texto
    assert "+5577999990000" in texto
    assert "Concordar e Fechar" not in texto


def test_html_para_texto_preserva_assistencia_social_e_remove_widget_social():
    html = """
    <html>
      <body>
        <main>
          <section class="assistencia-social">
            <h1>Secretaria Municipal de Assistencia Social</h1>
            <p>Telefone: (11) 3333-3333</p>
          </section>
          <div class="social-share">Compartilhar no Facebook</div>
        </main>
      </body>
    </html>
    """

    texto = html_para_texto(html)

    assert "Secretaria Municipal de Assistencia Social" in texto
    assert "(11) 3333-3333" in texto
    assert "Compartilhar no Facebook" not in texto


def test_pagina_indica_bloqueio_por_texto_ou_html():
    assert pagina_indica_bloqueio("Acesso negado")
    assert pagina_indica_bloqueio("", "<div>Cloudflare verify you are human</div>")
    assert not pagina_indica_bloqueio("Página de contatos institucional")


def test_recaptcha_em_pagina_institucional_com_conteudo_util_nao_e_bloqueio():
    texto = " ".join(
        [
            "Prefeitura Municipal",
            "Equipe de Governo",
            "Prefeita Maria Silva",
            "Secretaria de Desenvolvimento Econômico",
            "Secretaria da Fazenda",
            "Contato e Telefones da Prefeitura",
        ]
        * 8
    )

    assert not pagina_indica_bloqueio(texto, "<script src='recaptcha/api.js'></script>")


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
    <a href="/portal/noticias/0/3/2554/informativo-copa-do-mundo/">Noticia com palavra gabinete</a>
    <a href="/portal/download/arquivos/CGzzx/">Download sem extensao</a>
    <a href="/portal/editais/0/1/7964/">Edital com contato</a>
    <a href="/portal/obras/20/">Obra com contato</a>
    <a href="/gabinete-prefeito-noticias">Noticia em slug</a>
    <a href="/contatos?start=25">Paginacao de contatos</a>
    <a href="/contatos/18-escolas-municipais">Escolas municipais</a>
    <a href="/a-cidade/historia/prefeitos-de-lambari">Historico de prefeitos</a>
    <a href="/texto/intendentes_e_prefeitos">Historico de intendentes e prefeitos</a>
    <a href="/portal/contrato/7280/">Contrato municipal</a>
    <a href="/marcador/gabinete-prefeito">Marcador de noticias</a>
    <a href="/estrutura-organizacional/?pg=1&tax=tipo-secretaria%3D5">Secretaria paginada</a>
    <a href="/portal/detalhe-prefeito/21/">Prefeito histórico</a>
    <a href="/portal/secretarias-paginas/30/conselho/">Conselho</a>
    <a href="/portal/turismo/0/9/4813/praca">Turismo</a>
    <a href="/secretaria/15/secretaria/13/controladoria-geral">Secretaria recursiva</a>
    <a href="/secretaria/15/videos">Videos da secretaria</a>
    <a href="/secretaria/15/faq">FAQ da secretaria</a>
    <a href="/portal/portal/catnoticias/7">Categoria de noticias</a>
    <a href="/portal/portal/viewnoticia/3201">Noticia por id</a>
    <a href="/secom/cont_not.asp?titulo=Prefeito-assina-decreto&id=1&link=secom/noticias.asp&idn=43314">Noticia ASP antiga</a>
    <a href="/secom/contagem.asp?idsomar=73">Contador de clique</a>
    <a href="/Site/Tag/%23SecretariaDeInfraestrutura%20%23Prefeitura">Tag de noticias</a>
    <a href="/Site/Servicos/9">Pagina de servicos</a>
    <a href="/servicos/secretaria_de_infraestrutura/pagina_inicial">Servico de secretaria</a>
    <a href="/secretarias/diario_oficial">Diario oficial</a>
    <a href="/fotos/estrutura/secretaria_de_desenvolvimento">Fotos da estrutura</a>
    <a href="/Account/Login">Login</a>
    <a href="/politica-privacidade-protecao-dados">LGPD</a>
    <a href="/editais-licitacoes">Licitacoes</a>
    <a href="/site/tiposservicos">Tipos de servicos</a>
    <a href="/servidores">Servidores</a>
    <a href="/contratos">Contratos</a>
    <a href="/lei-orcamentaria">LOA</a>
    <a href="/licitacoes">Licitacoes portal</a>
    <a href="/dispensas-inexigibilidades">Dispensas</a>
    <a href="/usuario-esic">Usuario e-SIC</a>
    <a href="/esic-registro-solicitacao">Registro e-SIC</a>
    <a href="/sic-presencial">SIC presencial</a>
    <a href="/estatisticas-sic">Estatisticas SIC</a>
    <a href="/dados-genericos-esic">Dados genericos e-SIC</a>
    <a href="/cadastro-esic">Cadastro e-SIC</a>
    <a href="/transmissao">Transmissao</a>
    <a href="/conselhos_municipais/secretaria_de_financas">Conselho municipal</a>
    <a href="/secretarias/consulta_publica_pmsb">Consulta publica</a>
    <a href="/Site/Novidade/novidade-23062021190508125-PPA-Participativo">PPA novidade</a>
    <a href="/Site/AcessoAInformacao">Acesso a informacao generico</a>
    <a href="/Site/Transparencia">Transparencia generica</a>
    <a href="/Site/DiarioOficial">Diario oficial</a>
    <a href="/Site/SaoJoao">Sao Joao</a>
    <a href="/Site/Glossario?Length=4">Glossario</a>
    <a href="/secretaria-de-infraestrutura-em-acao/">Noticia da secretaria</a>
    <a href="/secretaria-de-infraestrutura-em-acao/?share=facebook">Compartilhar</a>
    <a href="/orgao/secretaria/planejamento-e-prestacao-de-contas">Prestacao de contas</a>
    <a href="/orgao/secretaria/legislacoes-e-atos">Legislacoes</a>
    <a href="/orgao/secretaria/portaltransparencia/?servico=fornecedor/filadepagamento">Fila pagamento</a>
    <a href="/orgao/secretaria/recursos-humanos">Recursos humanos</a>
    <a href="/orgao/secretaria/di%C3%A1rio-oficial-do-munic%C3%ADpio">Diario acentuado</a>
    <a href="/orgao/secretaria/acessoexterno/https/transparencia.example">Acesso externo</a>
    <a href="/orgao/secretaria/pesquisa-de-satisfacao">Pesquisa satisfacao</a>
    <a href="/orgao/secretaria/renuncias-de-receitas">Renuncias</a>
    <a href="/orgao/secretaria/emendas-parlamentares">Emendas</a>
    <a href="/orgao/secretaria/carta-de-servicos">Carta servicos</a>
    <a href="/orgao/secretaria/divida-ativa">Divida ativa</a>
    <a href="/orgao/secretaria/lei-de-acesso-informacao">LAI</a>
    <a href="/exibenoticia.php?codnoticia=702/secretaria-em-acao">Noticia PHP</a>
    <a href="/gabinete/5/secretaria/1/administra-o-e-finan-as">Secretaria aninhada no gabinete</a>
    <a href="/gabinetecivil@cidade.sp.gov.br">E-mail colado como URL</a>
    <a href="/planejamento-orcamentario/?cat=20&export=csv">Export CSV</a>
    <a href="/planejamento-saude/?ps_export=json&ps_scope=planejamento">Export JSON</a>
    <a href="mailto:gabinete@cidade.gov.br">Email</a>
    <a href="/noticias">Noticias</a>
    """

    links = extrair_links_relevantes(html, "https://cidade.sp.gov.br/", ["gabinete", "contato"])

    assert links == [
        "https://cidade.sp.gov.br/gabinete",
        "https://cidade.sp.gov.br/contato",
    ]


def test_extrair_links_relevantes_usa_texto_do_link_para_secretarias_numericas():
    html = """
    <a href="/secretaria/view/2">Secretaria de Educacao</a>
    <a href="/secretaria/view/9">Secretaria da Fazenda</a>
    <a href="/secretaria/view/13">Secretaria de Governo</a>
    """

    links = extrair_links_relevantes(html, "https://cidade.sp.gov.br/", ["secretaria", "fazenda", "governo"])

    assert links == [
        "https://cidade.sp.gov.br/secretaria/view/9",
        "https://cidade.sp.gov.br/secretaria/view/13",
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
        config={"timeout_segundos": 1, "retries": 0, "delay_entre_requisicoes": 0, "max_paginas_por_municipio": 5, "user_agent": "teste", "usar_caminhos_fallback_bloqueio": False},
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


def test_coletar_paginas_ignora_link_redirecionado_para_homepage_administrativa():
    home = """
    <html><body>
      <h1>Prefeitura</h1>
      <a href="/contato">Contato</a>
    </body></html>
    """
    homepage_admin = "<html><body>Prefeito Valores Cotas Verba Indenizatoria Ativ</body></html>"
    session = FakeSession(
        {
            "https://cidade.sp.gov.br/": FakeResponse("https://cidade.sp.gov.br/", home),
            "https://cidade.sp.gov.br/contato": FakeResponse("https://cidade.sp.gov.br/homepage", homepage_admin),
        }
    )

    result = coletar_paginas(
        "https://cidade.sp.gov.br/",
        ["contato", "prefeito"],
        config={"timeout_segundos": 1, "retries": 0, "delay_entre_requisicoes": 0, "max_paginas_por_municipio": 5, "user_agent": "teste", "usar_caminhos_fallback_bloqueio": False},
        session=session,
    )

    assert [pagina.url for pagina in result.paginas] == ["https://cidade.sp.gov.br/"]
    assert result.fontes_consultadas[-1].url_final == "https://cidade.sp.gov.br/homepage"
    assert result.fontes_consultadas[-1].status == "PÃ¡gina sem informaÃ§Ã£o pÃºblica"


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
        config={"timeout_segundos": 1, "retries": 0, "delay_entre_requisicoes": 0, "max_paginas_por_municipio": 5, "user_agent": "teste", "usar_caminhos_fallback_bloqueio": False},
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
        config={"timeout_segundos": 1, "retries": 0, "delay_entre_requisicoes": 0, "max_paginas_por_municipio": 5, "user_agent": "teste", "usar_caminhos_fallback_bloqueio": False},
        session=session,
    )

    assert result.status == "Bloqueio técnico"
    assert result.paginas == []
    assert result.fontes_consultadas[0].status == "Bloqueio técnico"


def test_coletar_paginas_classifica_timeout_e_http_bloqueado():
    timeout_result = coletar_paginas(
        "https://timeout.test/",
        ["contato"],
        config={
            "timeout_segundos": 1,
            "retries": 0,
            "delay_entre_requisicoes": 0,
            "max_paginas_por_municipio": 5,
            "user_agent": "teste",
            "usar_playwright_quando_necessario": False,
            "usar_caminhos_fallback_bloqueio": False,
        },
        session=FakeSession(exception=requests.Timeout("demorou")),
    )
    blocked_result = coletar_paginas(
        "https://bloqueio.test/",
        ["contato"],
        config={
            "timeout_segundos": 1,
            "retries": 0,
            "delay_entre_requisicoes": 0,
            "max_paginas_por_municipio": 5,
            "user_agent": "teste",
            "usar_playwright_quando_necessario": False,
            "usar_caminhos_fallback_bloqueio": False,
        },
        session=FakeSession({"https://bloqueio.test/": FakeResponse("https://bloqueio.test/", "bloqueado", 403)}),
    )

    assert timeout_result.status == "Site fora do ar"
    assert "Timeout" in timeout_result.observacoes
    assert timeout_result.fontes_consultadas[0].status == "Site fora do ar"
    assert blocked_result.status == "Bloqueio técnico"
    assert "HTTP 403" in blocked_result.observacoes
    assert blocked_result.fontes_consultadas[0].status_http == 403


def test_baixar_fecha_resposta_streamada_apos_html():
    import src.coletar_paginas as coletor

    response = FakeStreamResponse("https://cidade.sp.gov.br/", [b"<html>Gabinete</html>"])
    session = FakeSession({"https://cidade.sp.gov.br/": response})

    html, status, *_ = coletor._baixar(session, "https://cidade.sp.gov.br/", timeout=1)

    assert html == "<html>Gabinete</html>"
    assert status == "Encontrado"
    assert response.closed


def test_baixar_usa_fallback_oficial_porto_velho_quando_artigo_da_502():
    import src.coletar_paginas as coletor

    original = FakeStreamResponse(
        "https://www.portovelho.ro.gov.br/artigo/22645/o-prefeito",
        [b"erro"],
        status_code=502,
    )
    fallback = FakeStreamResponse(
        "https://agencia.portovelho.ro.gov.br/artigo/22645/o-prefeito",
        [b"<html>Prefeito Leo Moraes</html>"],
    )
    session = FakeSession(
        {
            "https://www.portovelho.ro.gov.br/artigo/22645/o-prefeito": original,
            "https://agencia.portovelho.ro.gov.br/artigo/22645/o-prefeito": fallback,
        }
    )

    html, status, _obs, final_url, *_ = coletor._baixar(
        session,
        "https://www.portovelho.ro.gov.br/artigo/22645/o-prefeito",
        timeout=1,
    )

    assert status == "Encontrado"
    assert html == "<html>Prefeito Leo Moraes</html>"
    assert final_url == "https://agencia.portovelho.ro.gov.br/artigo/22645/o-prefeito"
    assert original.closed
    assert fallback.closed


def test_baixar_fecha_resposta_streamada_em_conteudo_ignorado():
    import src.coletar_paginas as coletor

    response = FakeStreamResponse(
        "https://cidade.sp.gov.br/arquivo.pdf",
        [b"%PDF"],
        content_type="application/pdf",
    )
    session = FakeSession({"https://cidade.sp.gov.br/arquivo.pdf": response})

    html, status, observacao, *_ = coletor._baixar(session, "https://cidade.sp.gov.br/arquivo.pdf", timeout=1)

    assert html == ""
    assert status != "Encontrado"
    assert "application/pdf" in observacao
    assert response.closed


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


def test_coletar_paginas_tenta_navegador_quando_home_tem_timeout(monkeypatch):
    import src.coletar_paginas as coletor

    session = FakeSession(exception=requests.Timeout("demorou"))

    def fake_navegador(url, timeout, backend="auto", usar_cloakbrowser=True):
        return "<html><body>Gabinete do Prefeito Maria Silva</body></html>", "Encontrado", "", url, 200, "text/html", "playwright"

    monkeypatch.setattr(coletor, "_baixar_com_navegador", fake_navegador)

    result = coletar_paginas(
        "https://cidade.sp.gov.br/",
        ["gabinete"],
        config={
            "timeout_segundos": 1,
            "retries": 0,
            "delay_entre_requisicoes": 0,
            "max_paginas_por_municipio": 5,
            "user_agent": "teste",
            "usar_playwright_quando_necessario": True,
            "usar_caminhos_fallback_bloqueio": False,
        },
        session=session,
    )

    assert result.status == "Encontrado"
    assert result.paginas[0].texto == "Gabinete do Prefeito Maria Silva"
    assert [fonte.metodo for fonte in result.fontes_consultadas] == ["requests", "playwright"]


def test_coletar_paginas_tenta_caminho_institucional_quando_home_bloqueia():
    equipe = "<html><body>Equipe de Governo Prefeita Maria Silva Fone: (14) 3333-0000</body></html>"
    session = FakeSession(
        {
            "https://www.bauru.sp.gov.br/": FakeResponse("https://www.bauru.sp.gov.br/", "<html>Acesso negado captcha</html>"),
            "https://www.bauru.sp.gov.br/equipe_governo.aspx": FakeResponse(
                "https://www2.bauru.sp.gov.br/equipe_governo.aspx",
                equipe,
            ),
        }
    )

    result = coletar_paginas(
        "https://www.bauru.sp.gov.br/",
        ["equipe de governo"],
        config={
            "timeout_segundos": 1,
            "retries": 0,
            "delay_entre_requisicoes": 0,
            "max_paginas_por_municipio": 2,
            "user_agent": "teste",
            "usar_playwright_quando_necessario": False,
        },
        session=session,
    )

    assert result.status == "Encontrado"
    assert len(result.paginas) == 1
    assert result.paginas[0].url == "https://www2.bauru.sp.gov.br/equipe_governo.aspx"


def test_url_ignora_rotas_de_licitacao_e_template_eletronico():
    assert _url_deve_ser_ignorada("https://guacui.es.gov.br/licitacao/localizar/o/secretaria-de-financas.html")
    assert _url_deve_ser_ignorada("https://fundao.es.gov.br/secretaria/ler/28/<?=CLIENTE_PROCESSO_ELETRONICO;?>")
    assert _url_deve_ser_ignorada("https://www.aracruz.es.gov.br/secretarias/semfa/noticias")
    assert _url_deve_ser_ignorada("http://transparencia.aracruz.es.gov.br/MostraArquivo.ashx?ArquivoId=6676")
    assert _url_deve_ser_ignorada("https://www.jaguare.es.gov.br/documento?tipo=124")
    assert _url_deve_ser_ignorada("https://iuna.es.gov.br/secretarias/publicacoes/filtro/1?types=Registro")
    assert _url_deve_ser_ignorada("https://iuna.es.gov.br/secretarias/<br/><b>Notice</b>:Trying")
    assert _url_deve_ser_ignorada("https://guacui.es.gov.br/secretaria-de-saude/sobre.html")
    assert _url_deve_ser_ignorada("https://www.piuma.es.gov.br/portal/carta-de-servico/servico/111/licitacao")
    assert _url_deve_ser_ignorada("https://transparencia.serra.es.gov.br/Contrato.Lista.aspx?MunicipioID=1")
    assert _url_deve_ser_ignorada("https://transparencia.serra.es.gov.br/BemImovel.Secretaria.Relatorio.ashx")
    assert _url_deve_ser_ignorada("https://www.jaguare.es.gov.br/secretaria/ler/es-jaguare-pm.ctgi.cloud.el.com.br")
    assert _url_deve_ser_ignorada("https://cidade.rs.gov.br/site/download?type=csv&fileName=secretaria.pdf")
    assert _url_deve_ser_ignorada("https://fazenda.cidade.rj.gov.br/2025/12/17/")
    assert _url_deve_ser_ignorada("https://resende.rj.gov.br/desenvolvimento-rural/orgaos-e-secretarias.html")
    assert _url_deve_ser_ignorada("https://resende.rj.gov.br/desenvolvimento-urbano/publicacoes")
    assert _url_deve_ser_ignorada("https://riobonito.rj.gov.br/secretaria-de-governo/_wp_link_placeholder")
    assert _url_deve_ser_ignorada("https://riobonito.rj.gov.br/secassistenciasocial/")
    assert _url_deve_ser_ignorada("https://balneariogaivota.sc.gov.br/secretarias/gabinete//e-gov.betha.com.br/cdweb/resource.faces?params=x")
    assert _url_deve_ser_ignorada("https://cidade.rs.gov.br/secretarias/sala-do-empreendedor/instagram.com/perfil")
    assert _url_deve_ser_ignorada("https://fazenda.silvajardim.rj.gov.br/acessibilidade")
    assert _url_deve_ser_ignorada("https://www.riodasostras.rj.gov.br/fazenda-secretaria/busca")
    assert _url_deve_ser_ignorada("https://espumoso.rs.gov.br/governo/secretarias/agricultura/")
    assert _url_deve_ser_ignorada("https://espumoso.rs.gov.br/governo/secretarias/obras/")
    assert _url_deve_ser_ignorada("https://gramado.atende.net/subportal/secretaria-da-agricultura")
    assert _url_deve_ser_ignorada("https://gramado.atende.net/subportal/secretaria-de-obras-e-servicos-urbanos")
    assert _url_deve_ser_ignorada("https://www.itaqui.rs.gov.br/agricultura")
    assert _url_deve_ser_ignorada("https://www.itaqui.rs.gov.br/saude")
    assert _url_deve_ser_ignorada("https://www.saogoncalo.rj.gov.br/meio-ambiente-e-transportes/")
    assert _url_deve_ser_ignorada("https://www.juliodecastilhos.rs.gov.br/portal/secretarias/35/esf-castelo-branco")
    assert _url_deve_ser_ignorada("https://www.juliodecastilhos.rs.gov.br/portal/secretarias/29/assessor-de-imprensa")
    assert _url_deve_ser_ignorada("https://www.teresopolis.rj.gov.br/secretarias/agricultura-abastecimento-e-desenvolvimento-rural/feira-virtual-do-produtor/frutas")
    assert _url_deve_ser_ignorada("https://www.chapeco.sc.gov.br/conteudo/37/secretaria-de-servicos-urbanos-e-zeladoria")
    assert _url_deve_ser_ignorada("https://www.chapeco.sc.gov.br/desenvolvimento-sustentavel/conteudo/485/conteudo/485/conteudo/485/")
    assert _url_deve_ser_ignorada("https://www.chapeco.sc.gov.br/desenvolvimento-sustentavel/conteudo/485/mapa-do-site")
    assert _url_deve_ser_ignorada("https://naometoque.rs.gov.br/governo/secretarias/saude/consultas-e-procedimentos/")
    assert _url_deve_ser_ignorada("https://www.ituporanga.sc.gov.br/secretarias/secretaria-de-infraestrutura")
    assert _url_deve_ser_ignorada("https://www.ituporanga.sc.gov.br/secretarias/demutran")
    assert _url_deve_ser_ignorada("https://www.adamantina.sp.gov.br/portal/secretarias/32/secretaria-municipal-de-assuntos-juridicos")
    assert _url_deve_ser_ignorada("https://portal.barueri.sp.gov.br/secretarias/secretaria-da-mulher")
    assert _url_deve_ser_ignorada("https://portal.barueri.sp.gov.br/secretarias/secretaria-servicos-municipais")
    assert _url_deve_ser_ignorada("https://www.batatais.sp.gov.br/secretarias/servicos-publicos")
    assert _url_deve_ser_ignorada("https://www2.bauru.sp.gov.br/gabinete/defesacivil.aspx")
    assert _url_deve_ser_ignorada("https://www.sananduva.rs.gov.br/pg.php?area=EDUCACAO")
    assert _url_deve_ser_ignorada("https://www.sananduva.rs.gov.br/pg.php?area=OBRASURB")
    assert _url_deve_ser_ignorada("https://web.jaraguadosul.sc.gov.br/web/gabinete/objetivos-de-desenvolvimento-sustentavel-ods/ods-igualdade-de-genero")
    assert _url_deve_ser_ignorada("https://cmds.santarosa.rs.gov.br/wp-admin")
    assert _url_deve_ser_ignorada("https://saojose.sc.gov.br/relacao-de-prefeitos/")
    assert _url_deve_ser_ignorada("https://www.araraquara.sp.gov.br/secretarias/desenvolvimento-social/protecao-social-basica-desenvolvimento-social/cras")
    assert _url_deve_ser_ignorada("https://www.araraquara.sp.gov.br/secretarias/desenvolvimento-social/protecao-social-especial-desenvolvimento-social/creas")
    assert _url_deve_ser_ignorada("https://www.araraquara.sp.gov.br/secretarias/direitos-humanos-e-cidadania/sobre-a-secretaria-direitos-humanos-e-cidadania/lgbtqia")
    assert _url_deve_ser_ignorada("https://www2.bauru.sp.gov.br/financas/nfe/nfse.aspx?m=2")
    assert _url_deve_ser_ignorada("https://www2.bauru.sp.gov.br/financas/assunto.aspx?id=10")
    assert _url_deve_ser_ignorada("https://www2.bauru.sp.gov.br/administracao/portaldoservidor/valealimentacao.aspx")
    assert _url_deve_ser_ignorada("https://www2.bauru.sp.gov.br/administracao/cargos.aspx")
    assert _url_deve_ser_ignorada("https://www2.bauru.sp.gov.br/smas")
    assert _url_deve_ser_ignorada("https://www2.bauru.sp.gov.br/semma")
    assert _url_deve_ser_ignorada("https://www.caieiras.sp.gov.br/?id=secretaria-interna&categoria=desenvolvimento_social")
    assert _url_deve_ser_ignorada("https://www.caieiras.sp.gov.br/?id=secretaria-interna&categoria=iprem")
    assert _url_deve_ser_ignorada("https://cajamar.sp.gov.br/desenvolvimento-social/cmas/composicao-cmas/")
    assert _url_deve_ser_ignorada("https://cajamar.sp.gov.br/fazenda/servicos-online/")
    assert _url_deve_ser_ignorada("https://cajamar.sp.gov.br/fazenda/pecas-de-planejamento/")
    assert _url_deve_ser_ignorada("https://cajamar.sp.gov.br/desenvolvimento-urbano-e-economico/?page_id=330")
    assert not _url_deve_ser_ignorada("https://cajamar.sp.gov.br/desenvolvimento-urbano-e-economico/")
    assert _url_deve_ser_ignorada("https://www.camposdojordao.sp.gov.br/gabinete/erro-site/")
    assert _url_deve_ser_ignorada("https://www.camposdojordao.sp.gov.br/gabinete/gabinete/")
    assert _url_deve_ser_ignorada("https://www.camposdojordao.sp.gov.br/gabinete/secretarias/")
    assert _url_deve_ser_ignorada("https://www.camposdojordao.sp.gov.br/gabinete/protocolo-sei/")
    assert _url_deve_ser_ignorada("https://www.carapicuiba.sp.gov.br/secretaria/view/19/midia-video")
    assert _url_deve_ser_ignorada("https://www.catanduva.sp.gov.br/portal/secretarias/5/contratacoes-publicas")
    assert _url_deve_ser_ignorada("https://portal.diadema.sp.gov.br/financas/financas-parcelamentos/")
    assert _url_deve_ser_ignorada("https://portal.diadema.sp.gov.br/planejamento/painel-de-indicadores/")
    assert _url_deve_ser_ignorada("https://portal.diadema.sp.gov.br/planejamento/elementor-48020/")
    assert not _url_deve_ser_ignorada("https://portal.diadema.sp.gov.br/sedet/")
    assert _url_deve_ser_ignorada("https://www.indaiatuba.sp.gov.br/desenvolvimento-economico-industria-comercio-e-turismo/pat/seguro-desemprego/")
    assert _url_deve_ser_ignorada("https://www.indaiatuba.sp.gov.br/desenvolvimento-economico-industria-comercio-e-turismo/ministerio-do-trabalho/")
    assert not _url_deve_ser_ignorada("https://www.indaiatuba.sp.gov.br/desenvolvimento-economico-industria-comercio-e-turismo/banco-do-povo/")
    assert _url_deve_ser_ignorada("https://itapira.sp.gov.br/cidade-de-itapira/biografia-do-prefeito/secretarias/agricultura/78")
    assert not _url_deve_ser_ignorada("https://itapira.sp.gov.br/cidade-de-itapira/biografia-do-prefeito/secretarias/fazenda/74")
    assert _url_deve_ser_ignorada("https://www.itapolis.sp.gov.br/portal/secretarias/9/secretaria-municipal-de-desenvolvimento-agropecuario/")
    assert _url_deve_ser_ignorada("https://www.itapolis.sp.gov.br/portal/secretarias/32/conselho-municipal-de-desenvolvimento-rural/")
    assert _url_deve_ser_ignorada("https://www.itapolis.sp.gov.br/portal/secretarias/16/secretaria-municipal-de-planejamento-urbanistico/201.63.46.6:3000")
    assert _url_deve_ser_ignorada("https://www.itapolis.sp.gov.br/portal/secretarias/16/secretaria-municipal-de-planejamento-urbanistico/*************************")
    assert not _url_deve_ser_ignorada("https://www.itapolis.sp.gov.br/portal/secretarias/5/secretaria-municipal-de-desenvolvimento-economico/")
    assert _url_deve_ser_ignorada("https://www.jau.sp.gov.br/secretaria-economia-financas/codigo-tributario")
    assert _url_deve_ser_ignorada("https://www.jau.sp.gov.br/secretaria-governo/videomonitoramento")
    assert _url_deve_ser_ignorada("https://www.jau.sp.gov.br/secretaria-protecao-direito-animais/canil-municipal")
    assert _url_deve_ser_ignorada("https://jundiai.sp.gov.br/financas/nfs-e/")
    assert _url_deve_ser_ignorada("https://www.aracatuba.sp.gov.br/a-prefeitura/equipe/lucas-zanatta")
    assert not _url_deve_ser_ignorada("https://www.aracatuba.sp.gov.br/a-prefeitura/equipe")
    assert _url_deve_ser_ignorada("https://www.desenvolvimentoeconomico.sp.gov.br/contenthandler/x/mashup/ra:collection?entry=wp_toolbar&mime-type=text%2Fjavascript")
    assert _url_deve_ser_ignorada("https://www.desenvolvimentoeconomico.sp.gov.br/dx/api/dam/v1/items/abc?binary=true")
    assert _url_deve_ser_ignorada("https://www2.bauru.sp.gov.br/arquivos/arquivos_site/sec_administracao/remuneracao_servidores/1")
    assert _url_deve_ser_ignorada("https://www.santos.sp.gov.br/?q=noticia/forum-desenvolvimento-economico")
    assert _url_deve_ser_ignorada("https://www.riodaspedras.sp.gov.br/secretarias.php?page_no=2&FiltroSecretaria=12")
    assert _url_deve_ser_ignorada("https://www.tresdemaio.rs.gov.br/site/conteudos/702-<p>prefeito</p>")
    assert _url_deve_ser_ignorada("https://prefeitura.santarosa.rs.gov.br/?cat=22")
    assert _url_deve_ser_ignorada("https://prefeitura.santarosa.rs.gov.br/?p=16677")
    assert not _url_deve_ser_ignorada("https://www.sananduva.rs.gov.br/pg.php?area=GABINETEDOPREFEITO")
    assert not _url_deve_ser_ignorada("https://www.itaqui.rs.gov.br/planejamento")
    assert not _url_deve_ser_ignorada("https://gramado.atende.net/subportal/secretaria-da-fazenda")
    assert not _url_deve_ser_ignorada("https://espumoso.rs.gov.br/governo/secretarias/desenvolvimento/")
    assert not _url_deve_ser_ignorada("https://espumoso.rs.gov.br/governo/secretarias/coordenacao-e-planejamento/")
    assert _url_deve_ser_ignorada("https://cidade.rs.gov.br/secretaria/view/5?slug=secretaria-de-educacao")
    assert not _url_deve_ser_ignorada("https://cidade.rs.gov.br/secretaria/view/12?slug=turismo-e-desenvolvimento-economico")
