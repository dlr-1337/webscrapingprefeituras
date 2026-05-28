from urllib.parse import quote

import pandas as pd
import requests

from src.localizar_sites import (
    buscar_site_oficial_web,
    inferir_urls_basicas,
    localizar_site,
    preencher_sites,
    slugs_municipio,
    testar_url as checar_url,
)


class FakeResponse:
    def __init__(self, status_code=200, content_type="text/html", text=""):
        self.status_code = status_code
        self.headers = {"content-type": content_type}
        self.text = text


class FakeSession:
    def __init__(self, responses=None, exception=None):
        self.responses = list(responses or [])
        self.exception = exception
        self.urls = []

    def get(self, url, **kwargs):
        self.urls.append((url, kwargs))
        if self.exception:
            raise self.exception
        return self.responses.pop(0)


def test_infere_urls_basicas_com_slug_sem_acentos():
    urls = inferir_urls_basicas("São João d'Aliança", "GO")

    assert urls[:8] == [
        "https://saojoaodalianca.go.gov.br/",
        "https://www.saojoaodalianca.go.gov.br/",
        "http://saojoaodalianca.go.gov.br/",
        "http://www.saojoaodalianca.go.gov.br/",
        "https://prefeitura.saojoaodalianca.go.gov.br/",
        "https://www.prefeitura.saojoaodalianca.go.gov.br/",
        "http://prefeitura.saojoaodalianca.go.gov.br/",
        "http://www.prefeitura.saojoaodalianca.go.gov.br/",
    ]
    assert "https://www.saojoao.go.gov.br/" in urls


def test_infere_slug_curto_sem_conectores_para_toponimo_composto():
    urls = inferir_urls_basicas("Venda Nova do Imigrante", "ES")

    assert slugs_municipio("Venda Nova do Imigrante") == [
        "vendanovadoimigrante",
        "vendanovaimigrante",
        "vendanova",
    ]
    assert "https://www.vendanova.es.gov.br/" in urls


def test_localizar_site_usa_site_existente_normalizado_sem_testar_rede():
    session = FakeSession([FakeResponse()])

    site, status, obs = localizar_site("Campinas", "SP", "campinas.sp.gov.br", session=session)

    assert site == "https://campinas.sp.gov.br/"
    assert status == "Encontrado"
    assert "informado" in obs
    assert session.urls == []


def test_localizar_site_sem_inferencia_retorna_candidatos_para_validacao():
    site, status, obs = localizar_site("Campinas", "SP")

    assert site == ""
    assert status == "Site não localizado"
    assert "campinas.sp.gov.br" in obs


def test_localizar_site_com_inferencia_retorna_primeiro_candidato_valido():
    session = FakeSession([FakeResponse(404), FakeResponse(200, "text/html; charset=utf-8")])

    site, status, obs = localizar_site("Campinas", "SP", testar_inferencia=True, session=session)

    assert site == "https://www.campinas.sp.gov.br/"
    assert status == "Necessita validação manual"
    assert "inferido" in obs
    assert len(session.urls) == 2


def test_localizar_site_aceita_bloqueio_em_dominio_oficial_inferido():
    session = FakeSession([FakeResponse(403, "text/html; charset=utf-8")])

    site, status, obs = localizar_site("Aimorés", "MG", testar_inferencia=True, session=session)

    assert site == "https://aimores.mg.gov.br/"
    assert status == "Necessita validação manual"
    assert "inferido" in obs


def test_inferencia_prefere_raiz_sem_www_para_evitar_certificado_invalido():
    session = FakeSession([FakeResponse(200, "text/html; charset=utf-8")])

    site, status, obs = localizar_site("Viana", "ES", testar_inferencia=True, session=session)

    assert site == "https://viana.es.gov.br/"
    assert status.startswith("Necessita")
    assert "inferido" in obs


def test_busca_web_aceita_prefeitura_oficial_e_rejeita_camara():
    camara = quote("https://camara.muritiba.ba.gov.br/")
    oficial = quote("https://muritiba.ba.gov.br/equipe-de-governo/")
    html = f"""
    <html><body>
      <a href="https://duckduckgo.com/l/?uddg={camara}">Câmara Municipal de Muritiba</a>
      <a href="https://duckduckgo.com/l/?uddg={oficial}">Prefeitura Municipal de Muritiba - site oficial</a>
    </body></html>
    """
    session = FakeSession([FakeResponse(200, "text/html", html), FakeResponse(200, "text/html")])

    site, obs = buscar_site_oficial_web("Muritiba", "BA", session=session)

    assert site == "https://muritiba.ba.gov.br/"
    assert "busca web oficial" in obs
    assert len(session.urls) == 2


def test_testar_url_aceita_html_e_rejeita_erros_ou_conteudo_nao_html():
    assert checar_url("https://ok.test", session=FakeSession([FakeResponse(200, "text/html")])) is True
    assert checar_url("https://sem-content-type.test", session=FakeSession([FakeResponse(204, "")])) is True
    assert checar_url("https://pdf.test", session=FakeSession([FakeResponse(200, "application/pdf")])) is False
    assert checar_url("https://erro.test", session=FakeSession(exception=requests.ConnectionError("fora"))) is False


def test_testar_url_aceita_timeout_como_dominio_localizavel_quando_permitido():
    session = FakeSession(exception=requests.Timeout("demorou"))

    assert checar_url("https://timeout.test", session=session, aceitar_bloqueio=True) is True


def test_preencher_sites_adiciona_status_e_observacoes():
    df = pd.DataFrame(
        [
            {"UF": "SP", "Município": "Campinas", "Site oficial": "campinas.sp.gov.br"},
            {"UF": "SP", "Município": "Cidade Sem Site", "Site oficial": ""},
        ]
    )

    result = preencher_sites(df)

    assert list(result["Status localização site"]) == ["Encontrado", "Site não localizado"]
    assert result.loc[0, "Site oficial"] == "https://campinas.sp.gov.br/"
    assert "Candidatos básicos" in result.loc[1, "Observações localização site"]
