import pandas as pd

from src.gerar_excel import gerar_excel
from src.normalizar_dados import (
    deduplicar_contatos,
    normalizar_email,
    normalizar_municipio,
    normalizar_telefone,
    normalizar_uf,
)


def test_normaliza_uf_municipio_email_e_telefone():
    assert normalizar_uf("sp") == "SP"
    assert normalizar_municipio("sao bernardo do campo") == "Sao Bernardo do Campo"
    assert normalizar_email("GABINETE@EXEMPLO.GOV.BR; gabinete@exemplo.gov.br") == "gabinete@exemplo.gov.br"
    assert normalizar_telefone("+55 11 99999-9999") == "(11) 99999-9999"
    assert normalizar_telefone("11 3333-3333") == "(11) 3333-3333"


def test_deduplica_contatos_repetidos():
    df = pd.DataFrame(
        [
            {"UF": "SP", "Município": "Campinas", "Cargo/Órgão": "Prefeito", "Nome": "João Silva", "E-mail": "a@b.gov.br", "Telefone": "(11) 3333-3333", "Celular": "", "URL específica": "https://x"},
            {"UF": "SP", "Município": "Campinas", "Cargo/Órgão": "Prefeito", "Nome": "João Silva", "E-mail": "a@b.gov.br", "Telefone": "(11) 3333-3333", "Celular": "", "URL específica": "https://x"},
        ]
    )

    assert len(deduplicar_contatos(df)) == 1


def test_gera_excel_com_abas_basicas(tmp_path):
    resultado = pd.DataFrame(
        [
            {
                "UF": "SP",
                "Estado": "São Paulo",
                "Município": "Campinas",
                "População": 100000,
                "Critério de inclusão": "SP acima de 30.000 habitantes",
                "Site oficial": "https://campinas.sp.gov.br/",
                "Cargo/Órgão": "Prefeito",
                "Nome": "João Silva",
                "E-mail": "prefeito@campinas.sp.gov.br",
                "Telefone": "(19) 3333-3333",
                "Celular": "",
                "URL específica": "https://campinas.sp.gov.br/gabinete",
                "Data da coleta": "2026-05-20",
                "Status": "Encontrado",
                "Observações": "",
            }
        ]
    )
    municipios = pd.DataFrame(
        [
            {
                "UF": "SP",
                "Estado": "São Paulo",
                "Município": "Campinas",
                "População": 100000,
                "Critério de inclusão": "SP acima de 30.000 habitantes",
                "Site oficial": "https://campinas.sp.gov.br/",
                "Status geral": "Encontrado",
                "Observações": "",
            }
        ]
    )
    output = tmp_path / "resultado.xlsx"

    gerar_excel(resultado, municipios, pd.DataFrame(), output)

    assert output.exists()
    xls = pd.ExcelFile(output)
    assert xls.sheet_names[0] == "Dados"
    assert set(xls.sheet_names) == {
        "Dados",
        "Resultado consolidado",
        "Municípios pesquisados",
        "Pendências",
        "Resumo",
        "Fontes e Log",
        "Configuração",
    }
