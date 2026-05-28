import pandas as pd
import requests

from src.preencher_sites_congelados import preencher_sites_congelados


class FakeResponse:
    def __init__(self, status_code=200, content_type="text/html"):
        self.status_code = status_code
        self.headers = {"content-type": content_type}


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.urls = []

    def get(self, url, **kwargs):
        self.urls.append((url, kwargs))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def test_preencher_sites_congelados_gera_base_e_pendencias(tmp_path):
    input_path = tmp_path / "congelada.csv"
    output_path = tmp_path / "com_sites.csv"
    pendencias_path = tmp_path / "pendencias.xlsx"
    input_path.write_text(
        "codigo_ibge,municipio,uf,estado,populacao,capital,site_oficial\n"
        "1,Cidade Com Site,SP,São Paulo,100000,false,cidade.sp.gov.br\n"
        "2,Campinas,SP,São Paulo,1200000,false,\n"
        "3,Cidade Timeout,SP,São Paulo,90000,false,\n",
        encoding="utf-8",
    )
    session = FakeSession(
        [
            FakeResponse(404),
            FakeResponse(200, "text/html; charset=utf-8"),
            requests.ConnectionError("fora"),
            requests.ConnectionError("fora"),
            requests.ConnectionError("fora"),
            requests.ConnectionError("fora"),
            requests.ConnectionError("fora"),
            requests.ConnectionError("fora"),
            requests.ConnectionError("fora"),
            requests.ConnectionError("fora"),
        ]
    )

    output, pendencias = preencher_sites_congelados(
        input_path,
        output_path,
        pendencias_path,
        session=session,
        timeout=1,
        usar_busca_web=False,
    )

    result = pd.read_csv(output)
    assert output == output_path
    assert pendencias == pendencias_path
    assert list(result["status_localizacao_site"]) == [
        "Encontrado",
        "Necessita validação manual",
        "Site não localizado",
    ]
    assert result.loc[0, "site_oficial"] == "https://cidade.sp.gov.br/"
    assert result.loc[1, "site_oficial"] == "https://www.campinas.sp.gov.br/"
    assert result.loc[2, "site_oficial"] != result.loc[2, "site_oficial"]

    pendentes = pd.read_excel(pendencias_path)
    assert set(pendentes["status_localizacao_site"]) == {"Necessita validação manual", "Site não localizado"}
    assert len(session.urls) == 10
