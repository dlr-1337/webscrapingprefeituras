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


def test_gerar_excel_rebaixa_encontrado_sem_dado_publicado(tmp_path):
    output = tmp_path / "resultado.xlsx"
    resultado = pd.DataFrame(
        [
            {
                "UF": "SP",
                "Município/Capital": "Franco da Rocha",
                "Município": "Franco da Rocha",
                "Esfera": "Municipal",
                "Cargo/Área": "Prefeito",
                "Nome": "",
                "E-mail": "",
                "Telefone": "",
                "Celular/WhatsApp": "",
                "Status": "Encontrado",
                "URL da fonte": "https://www.francodarocha.sp.gov.br/",
            },
            {
                "UF": "SP",
                "Município/Capital": "Franco da Rocha",
                "Município": "Franco da Rocha",
                "Esfera": "Municipal",
                "Cargo/Área": "Vice-prefeito",
                "Nome": "",
                "E-mail": "vice@francodarocha.sp.gov.br",
                "Telefone": "",
                "Celular/WhatsApp": "",
                "Status": "Encontrado",
                "URL da fonte": "https://www.francodarocha.sp.gov.br/gabinete/",
            },
        ]
    )
    municipios = pd.DataFrame(
        [
            {
                "UF": "SP",
                "Município/Capital": "Franco da Rocha",
                "Município": "Franco da Rocha",
                "Esfera": "Municipal",
                "Status geral": "Encontrado",
            }
        ]
    )

    gerar_excel(resultado, municipios, pd.DataFrame(), output)

    dados = pd.read_excel(output, sheet_name="Dados")
    prefeito = dados[dados["Cargo/Área"] == "Prefeito"].iloc[0]
    vice = dados[dados["Cargo/Área"] == "Vice-prefeito"].iloc[0]
    assert prefeito["Status"] == "Não publicado"
    assert "sem dado oficial claro" in prefeito["Observações"]
    assert vice["Status"] == "Encontrado"


def test_gerar_excel_descarta_nome_institucional(tmp_path):
    output = tmp_path / "resultado.xlsx"
    resultado = pd.DataFrame(
        [
            {
                "UF": "SP",
                "Município/Capital": "Franco da Rocha",
                "Município": "Franco da Rocha",
                "Esfera": "Municipal",
                "Cargo/Área": "Prefeito",
                "Nome": "Assuntos Jurídicos",
                "Status": "Encontrado",
                "URL da fonte": "https://www.francodarocha.sp.gov.br/assuntos-juridicos/",
            }
        ]
    )
    municipios = pd.DataFrame(
        [
            {
                "UF": "SP",
                "Município/Capital": "Franco da Rocha",
                "Município": "Franco da Rocha",
                "Esfera": "Municipal",
                "Status geral": "Encontrado",
            }
        ]
    )

    gerar_excel(resultado, municipios, pd.DataFrame(), output)

    dados = pd.read_excel(output, sheet_name="Dados")
    row = dados.iloc[0]
    assert pd.isna(row["Nome"])
    assert row["Status"] == "Não publicado"
    assert "rótulo institucional" in row["Observações"]


def test_gerar_excel_rebaixa_fonte_indisponivel_na_validacao(tmp_path):
    output = tmp_path / "resultado.xlsx"
    resultado = pd.DataFrame(
        [
            {
                "UF": "PR",
                "Município/Capital": "Antonina",
                "Município": "Antonina",
                "Esfera": "Municipal",
                "Cargo/Área": "Finanças/Fazenda",
                "Nome": "Rafael Neves Alves",
                "E-mail": "financas@antonina.pr.gov.br",
                "Telefone": "(41) 3978-1042",
                "Celular/WhatsApp": "",
                "Status": "Encontrado",
                "URL da fonte": "https://www.antonina.pr.gov.br/secretariaView/?id=6",
            },
            {
                "UF": "PR",
                "Município/Capital": "Loanda",
                "Município": "Loanda",
                "Esfera": "Municipal",
                "Cargo/Área": "Prefeito",
                "Nome": "Jose Maria Pereira Fernandes",
                "E-mail": "",
                "Telefone": "",
                "Celular/WhatsApp": "",
                "Status": "Parcial",
                "URL da fonte": "https://loanda.pr.gov.br/gabinete/1_Prefeito.html",
            },
            {
                "UF": "PR",
                "Município/Capital": "Quedas do Iguaçu",
                "Município": "Quedas do Iguaçu",
                "Esfera": "Municipal",
                "Cargo/Área": "Vice-prefeito",
                "Nome": "Fatima Manica Revers",
                "E-mail": "gabinete@quedasdoiguacu.pr.gov.br",
                "Telefone": "(46) 3532-8200",
                "Celular/WhatsApp": "",
                "Status": "Encontrado",
                "URL da fonte": "https://www.quedasdoiguacu.pr.gov.br/gabinete/2_Vice-Prefeita.html",
            }
        ]
    )
    municipios = pd.DataFrame(
        [
            {
                "UF": "PR",
                "Município/Capital": "Antonina",
                "Município": "Antonina",
                "Esfera": "Municipal",
                "Status geral": "Encontrado",
            }
        ]
    )

    gerar_excel(resultado, municipios, pd.DataFrame(), output)

    dados = pd.read_excel(output, sheet_name="Dados")
    assert set(dados["Status"]) == {"Site fora do ar"}
    assert dados["Nome"].isna().all()
    assert dados["E-mail"].isna().all()
    assert dados["Observações"].str.contains("indisponibilidade").all()
