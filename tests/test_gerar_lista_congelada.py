from src.gerar_lista_congelada import gerar_lista_congelada


class FakeResponse:
    def __init__(self, data):
        self.data = data

    def raise_for_status(self):
        return None

    def json(self):
        return self.data


class FakeSession:
    def __init__(self):
        self.urls = []

    def get(self, url, timeout=60):
        self.urls.append(url)
        if "localidades" in url:
            return FakeResponse(
                [
                    {
                        "id": 3550308,
                        "nome": "São Paulo",
                        "regiao-imediata": {
                            "regiao-intermediaria": {
                                "UF": {"sigla": "SP", "nome": "São Paulo"},
                            }
                        },
                    },
                    {
                        "id": 3509502,
                        "nome": "Campinas",
                        "regiao-imediata": {
                            "regiao-intermediaria": {
                                "UF": {"sigla": "SP", "nome": "São Paulo"},
                            }
                        },
                    },
                    {
                        "id": 1506807,
                        "nome": "Santarém",
                        "regiao-imediata": {
                            "regiao-intermediaria": {
                                "UF": {"sigla": "PA", "nome": "Pará"},
                            }
                        },
                    },
                ]
            )
        return FakeResponse(
            [
                {"header": "x"},
                {"D1C": "3550308", "V": "11904961"},
                {"D1C": "3509502", "V": "1187974"},
                {"D1C": "1506807", "V": "331937"},
            ]
        )


def test_gerar_lista_congelada_filtra_criterios_e_salva_csv(tmp_path):
    output = tmp_path / "congelada.csv"
    session = FakeSession()

    result = gerar_lista_congelada("2025", output, session=session)

    content = result.read_text(encoding="utf-8")
    assert result == output
    assert "codigo_ibge,municipio,uf,estado,populacao,capital,site_oficial,criterio_inclusao,fonte,data_congelamento" in content
    assert "São Paulo" in content
    assert "Campinas" in content
    assert "Santarém" not in content
    assert any("apisidra.ibge.gov.br" in url for url in session.urls)
