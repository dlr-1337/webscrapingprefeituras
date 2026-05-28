import pandas as pd

from src.gerar_excel import gerar_excel
from src.mesclar_estaduais_resultado import mesclar_estaduais


def test_mesclar_estaduais_preserva_municipais_e_substitui_estaduais(tmp_path):
    base = tmp_path / "base.xlsx"
    estaduais = tmp_path / "estaduais.xlsx"
    output = tmp_path / "final.xlsx"

    gerar_excel(
        pd.DataFrame(
            [
                {
                    "UF": "SP",
                    "Município/Capital": "Campinas",
                    "Município": "Campinas",
                    "Esfera": "Municipal",
                    "Cargo/Área": "Prefeito",
                    "Status": "Encontrado",
                    "URL da fonte": "https://campinas.sp.gov.br/",
                    "Data da coleta": "2026-05-28",
                },
                {
                    "UF": "SP",
                    "Município/Capital": "Governo estadual antigo",
                    "Município": "Governo estadual antigo",
                    "Esfera": "Estadual",
                    "Cargo/Área": "Planejamento",
                    "Status": "Não publicado",
                    "URL da fonte": "https://antigo.example/",
                    "Data da coleta": "2026-05-28",
                    "Observações": "Antigo.",
                },
            ]
        ),
        pd.DataFrame(
            [
                {"UF": "SP", "Município/Capital": "Campinas", "Município": "Campinas", "Esfera": "Municipal"},
                {
                    "UF": "SP",
                    "Município/Capital": "Governo estadual antigo",
                    "Município": "Governo estadual antigo",
                    "Esfera": "Estadual",
                },
            ]
        ),
        pd.DataFrame(),
        base,
    )
    gerar_excel(
        pd.DataFrame(
            [
                {
                    "UF": "AL",
                    "Município/Capital": "Secretaria de Estado do Desenvolvimento, Industria, Comercio e Servicos de Alagoas",
                    "Município": "Secretaria de Estado do Desenvolvimento, Industria, Comercio e Servicos de Alagoas",
                    "Esfera": "Estadual",
                    "Cargo/Área": "Desenvolvimento econômico",
                    "Status": "Encontrado",
                    "URL da fonte": "https://alagoasdigital.al.gov.br/orgao/64",
                    "Data da coleta": "2026-05-28",
                }
            ]
        ),
        pd.DataFrame(
            [
                {
                    "UF": "AL",
                    "Município/Capital": "Secretaria de Estado do Desenvolvimento, Industria, Comercio e Servicos de Alagoas",
                    "Município": "Secretaria de Estado do Desenvolvimento, Industria, Comercio e Servicos de Alagoas",
                    "Esfera": "Estadual",
                }
            ]
        ),
        pd.DataFrame(),
        estaduais,
    )

    mesclar_estaduais(base, estaduais, output)

    dados = pd.read_excel(output, sheet_name="Dados")
    assert "Campinas" in set(dados["Município/Capital"])
    assert "Governo estadual antigo" not in set(dados["Município/Capital"])
    assert "Secretaria de Estado do Desenvolvimento, Industria, Comercio e Servicos de Alagoas" in set(
        dados["Município/Capital"]
    )
