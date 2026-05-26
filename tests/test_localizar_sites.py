import requests

from src.localizar_sites import inferir_urls_basicas, localizar_site, preencher_sites, testar_url as checar_url
import pandas as pd


class FakeResponse:
    def __init__(self, status_code=200, content_type="text/html"):
        self.status_code = status_code
        self.headers = {"content-type": content_type}


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
    assert inferir_urls_basicas("São João d'Aliança", "GO") == [
        "https://www.saojoaodalianca.go.gov.br/",
        "https://saojoaodalianca.go.gov.br/",
        "http://www.saojoaodalianca.go.gov.br/",
        "http://saojoaodalianca.go.gov.br/",
        "https://www.prefeitura.saojoaodalianca.go.gov.br/",
        "https://prefeitura.saojoaodalianca.go.gov.br/",
        "http://www.prefeitura.saojoaodalianca.go.gov.br/",
        "http://prefeitura.saojoaodalianca.go.gov.br/",
    ]


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

    assert site == "https://campinas.sp.gov.br/"
    assert status == "Necessita validação manual"
    assert "inferido" in obs
    assert len(session.urls) == 2


def test_testar_url_aceita_html_e_rejeita_erros_ou_conteudo_nao_html():
    assert checar_url("https://ok.test", session=FakeSession([FakeResponse(200, "text/html")])) is True
    assert checar_url("https://sem-content-type.test", session=FakeSession([FakeResponse(204, "")])) is True
    assert checar_url("https://pdf.test", session=FakeSession([FakeResponse(200, "application/pdf")])) is False
    assert checar_url("https://erro.test", session=FakeSession(exception=requests.ConnectionError("fora"))) is False


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
