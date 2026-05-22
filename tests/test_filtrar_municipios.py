import pandas as pd

from src.filtrar_municipios import filtrar_municipios


def test_filtra_municipios_por_criterios_populacionais_e_capitais():
    df = pd.DataFrame(
        [
            {"UF": "SP", "Estado": "São Paulo", "Município": "Campinas", "População": 1200000, "Capital": False, "Site oficial": ""},
            {"UF": "SP", "Estado": "São Paulo", "Município": "Cidade Pequena", "População": 30000, "Capital": False, "Site oficial": ""},
            {"UF": "MG", "Estado": "Minas Gerais", "Município": "Cidade Media", "População": 15001, "Capital": False, "Site oficial": ""},
            {"UF": "MG", "Estado": "Minas Gerais", "Município": "Cidade Menor", "População": 15000, "Capital": False, "Site oficial": ""},
            {"UF": "PA", "Estado": "Pará", "Município": "Belém", "População": 1300000, "Capital": True, "Site oficial": ""},
            {"UF": "PA", "Estado": "Pará", "Município": "Santarém", "População": 300000, "Capital": False, "Site oficial": ""},
            {"UF": "DF", "Estado": "Distrito Federal", "Município": "Brasília", "População": 2800000, "Capital": True, "Site oficial": ""},
        ]
    )

    result = filtrar_municipios(df)

    assert set(result["Município"]) == {"Campinas", "Cidade Media", "Belém", "Brasília"}
    assert "Critério de inclusão" in result.columns

