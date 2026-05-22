import pandas as pd

from src.gerar_excel import criar_resumo, gerar_excel


def test_criar_resumo_conta_status_e_municipios_unicos():
    resultado = pd.DataFrame(
        [
            {"UF": "SP", "Município": "Campinas", "Status": "Encontrado"},
            {"UF": "SP", "Município": "Campinas", "Status": "Encontrado"},
            {"UF": "RJ", "Município": "Niterói", "Status": "Parcial"},
        ]
    )
    municipios = pd.DataFrame(
        [
            {"UF": "SP", "Município": "Campinas", "Status geral": "Encontrado"},
            {"UF": "RJ", "Município": "Niterói", "Status geral": "Parcial"},
            {"UF": "MG", "Município": "Cidade", "Status geral": "Não encontrado"},
            {"UF": "BA", "Município": "Outra", "Status geral": "Site fora do ar"},
            {"UF": "GO", "Município": "Mais uma", "Status geral": "Bloqueio técnico"},
        ]
    )
    pendencias = pd.DataFrame([{"Status": "Site não localizado"}])

    resumo = criar_resumo(resultado, municipios, pendencias)
    valores = dict(zip(resumo["Indicador"], resumo["Valor"]))

    assert valores["Total de municípios no escopo"] == 5
    assert valores["Total de municípios com algum dado encontrado"] == 1
    assert valores["Total de municípios com dados parciais"] == 1
    assert valores["Total de municípios sem dados encontrados"] == 1
    assert valores["Total de sites não localizados"] == 1
    assert valores["Total de sites fora do ar"] == 1
    assert valores["Total de bloqueios técnicos"] == 1
    assert {"Por UF", "Por Município/Capital", "Por Cargo/Área", "Por Status"}.issubset(set(resumo["Seção"]))


def test_gerar_excel_inclui_dados_e_resultado_consolidado(tmp_path):
    output = tmp_path / "resultado.xlsx"
    resultado = pd.DataFrame(
        [
            {
                "UF": "SP",
                "Município/Capital": "Campinas",
                "Município": "Campinas",
                "Esfera": "Municipal",
                "Cargo/Área": "Prefeito",
                "Status": "Encontrado",
                "URL da fonte": "https://campinas.sp.gov.br/",
            }
        ]
    )
    municipios = pd.DataFrame(
        [
            {
                "UF": "SP",
                "Município/Capital": "Campinas",
                "Município": "Campinas",
                "Esfera": "Municipal",
                "Status geral": "Encontrado",
            }
        ]
    )

    gerar_excel(resultado, municipios, pd.DataFrame(), output)

    excel = pd.ExcelFile(output)
    assert excel.sheet_names[:2] == ["Dados", "Resultado consolidado"]
    assert {"Municípios pesquisados", "Pendências", "Resumo", "Fontes e Log", "Configuração"}.issubset(excel.sheet_names)
    dados = pd.read_excel(output, sheet_name="Dados")
    consolidado = pd.read_excel(output, sheet_name="Resultado consolidado")
    assert list(dados.columns) == list(consolidado.columns)
