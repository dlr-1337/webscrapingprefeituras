import pandas as pd

from src.escopo_categorias import FONTE_TERRITORIAL_URL, labels_categorias_obrigatorias
from src.gerar_excel import gerar_excel
from src.validar_resultados import auditar_planilha_final, criar_pendencia, garantir_colunas, validar_resultados


def test_garantir_colunas_preserva_ordem_e_preenche_ausentes():
    result = garantir_colunas(pd.DataFrame([{"B": 2, "extra": "x"}]), ["A", "B", "C"])

    assert list(result.columns) == ["A", "B", "C"]
    assert result.loc[0, "A"] == ""
    assert result.loc[0, "B"] == 2
    assert result.loc[0, "C"] == ""


def test_criar_pendencia_monta_campos_padronizados():
    pendencia = criar_pendencia("SP", "Campinas", "Contato", "Sem e-mail", "Não encontrado", "https://x", "obs")

    assert pendencia == {
        "UF": "SP",
        "Esfera": "Municipal",
        "Município/Capital": "Campinas",
        "Município": "Campinas",
        "Tipo de pendência": "Contato",
        "Descrição": "Sem e-mail",
        "URL, se houver": "https://x",
        "Status": "Não encontrado",
        "Observações": "obs",
    }


def test_validar_resultados_aponta_status_invalido_e_url_ausente():
    df = pd.DataFrame(
        [
            {"UF": "SP", "Município": "Campinas", "Status": "Encontrado", "URL específica": ""},
            {"UF": "RJ", "Município": "Niterói", "Status": "Status inventado", "URL específica": "https://x"},
        ]
    )

    pendencias = validar_resultados(df)

    assert [item["Tipo de pendência"] for item in pendencias] == ["URL ausente", "Status inválido"]
    assert all(item["Status"] == "Necessita validação manual" for item in pendencias)


def test_validar_resultados_aceita_nao_publicado_e_url_da_fonte():
    df = pd.DataFrame(
        [
            {"UF": "SP", "Município": "Campinas", "Status": "Não publicado", "URL da fonte": ""},
            {"UF": "SP", "Município": "Campinas", "Status": "Encontrado", "URL da fonte": "https://x", "URL específica": ""},
        ]
    )

    assert validar_resultados(df) == []


def test_validar_resultados_aponta_categoria_obrigatoria_ausente():
    resultado = pd.DataFrame(
        [
            {
                "UF": "SP",
                "Município/Capital": "Campinas",
                "Município": "Campinas",
                "Esfera": "Municipal",
                "Cargo/Área": "Município/Capital e UF",
                "Status": "Encontrado",
                "URL da fonte": FONTE_TERRITORIAL_URL,
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
                "Site oficial": "https://campinas.sp.gov.br/",
            }
        ]
    )

    pendencias = validar_resultados(resultado, municipios)

    assert {item["Tipo de pendência"] for item in pendencias} == {"Cobertura de categoria"}
    assert len(pendencias) == 8
    assert "Prefeito" in {item["Descrição"].rsplit(": ", 1)[1].rstrip(".") for item in pendencias}


def test_auditar_planilha_final_aprova_cobertura_completa(tmp_path):
    input_path = tmp_path / "municipios.csv"
    input_path.write_text(
        "municipio,uf,estado,populacao,capital,site_oficial\n"
        "Campinas,SP,São Paulo,1200000,false,https://campinas.sp.gov.br/\n",
        encoding="utf-8",
    )
    output = tmp_path / "resultado.xlsx"
    dados = pd.DataFrame(
        [
            {
                "UF": "SP",
                "Estado": "São Paulo",
                "Município/Capital": "Campinas",
                "Município": "Campinas",
                "Esfera": "Municipal",
                "Cargo/Área": categoria,
                "Cargo/Órgão": categoria,
                "URL da fonte": "https://campinas.sp.gov.br/",
                "URL específica": "https://campinas.sp.gov.br/",
                "Data da coleta": "2026-05-22",
                "Status": "Encontrado" if categoria == "Município/Capital e UF" else "Não publicado",
                "Observações": "" if categoria == "Município/Capital e UF" else "Não publicado oficialmente na fonte consultada.",
            }
            for categoria in labels_categorias_obrigatorias()
        ]
    )
    municipios = pd.DataFrame(
        [
            {
                "UF": "SP",
                "Estado": "São Paulo",
                "Município/Capital": "Campinas",
                "Município": "Campinas",
                "Esfera": "Municipal",
                "Site oficial": "https://campinas.sp.gov.br/",
                "Status geral": "Não publicado",
                "Observações": "Sem dados publicados para categorias alvo.",
            }
        ]
    )

    gerar_excel(dados, municipios, pd.DataFrame(), output)

    assert auditar_planilha_final(output, input_path).empty


def test_auditar_planilha_final_aponta_data_url_e_escopo(tmp_path):
    input_path = tmp_path / "municipios.csv"
    input_path.write_text(
        "municipio,uf,estado,populacao,capital,site_oficial\n"
        "Campinas,SP,São Paulo,1200000,false,https://campinas.sp.gov.br/\n"
        "Limeira,SP,São Paulo,300000,false,https://limeira.sp.gov.br/\n",
        encoding="utf-8",
    )
    output = tmp_path / "resultado.xlsx"
    dados = pd.DataFrame(
        [
            {
                "UF": "SP",
                "Município/Capital": "Campinas",
                "Município": "Campinas",
                "Esfera": "Municipal",
                "Cargo/Área": "Município/Capital e UF",
                "Status": "Encontrado",
                "URL da fonte": "",
                "Data da coleta": "",
            }
        ]
    )
    municipios = pd.DataFrame(
        [{"UF": "SP", "Município/Capital": "Campinas", "Município": "Campinas", "Esfera": "Municipal"}]
    )

    gerar_excel(dados, municipios, pd.DataFrame(), output)
    issues = auditar_planilha_final(output, input_path)

    assert {"Fonte", "Data", "Cobertura", "Escopo"}.issubset(set(issues["Tipo"]))


def test_auditar_planilha_final_reprova_linha_estadual_fora_do_escopo(tmp_path):
    input_path = tmp_path / "municipios.csv"
    input_path.write_text(
        "municipio,uf,estado,populacao,capital,site_oficial\n"
        "Campinas,SP,São Paulo,1200000,false,https://campinas.sp.gov.br/\n",
        encoding="utf-8",
    )
    output = tmp_path / "resultado.xlsx"
    dados = pd.DataFrame(
        [
            {
                "UF": "SP",
                "Estado": "São Paulo",
                "Município/Capital": "Campinas",
                "Município": "Campinas",
                "Esfera": "Municipal",
                "Cargo/Área": categoria,
                "Cargo/Órgão": categoria,
                "URL da fonte": "https://campinas.sp.gov.br/",
                "URL específica": "https://campinas.sp.gov.br/",
                "Data da coleta": "2026-05-22",
                "Status": "Encontrado" if categoria == "Município/Capital e UF" else "Não publicado",
                "Observações": "" if categoria == "Município/Capital e UF" else "Não publicado oficialmente na fonte consultada.",
            }
            for categoria in labels_categorias_obrigatorias()
        ]
        + [
            {
                "UF": "SP",
                "Estado": "São Paulo",
                "Município/Capital": "Governo do Estado de São Paulo",
                "Município": "Governo do Estado de São Paulo",
                "Esfera": "Estadual",
                "Cargo/Área": "Município/Capital e UF",
                "Cargo/Órgão": "Município/Capital e UF",
                "URL da fonte": "https://www.saopaulo.sp.gov.br/",
                "URL específica": "https://www.saopaulo.sp.gov.br/",
                "Data da coleta": "2026-05-22",
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
                "Município/Capital": "Campinas",
                "Município": "Campinas",
                "Esfera": "Municipal",
                "Site oficial": "https://campinas.sp.gov.br/",
                "Status geral": "Encontrado",
            },
            {
                "UF": "SP",
                "Estado": "São Paulo",
                "Município/Capital": "Governo do Estado de São Paulo",
                "Município": "Governo do Estado de São Paulo",
                "Esfera": "Estadual",
                "Site oficial": "https://www.saopaulo.sp.gov.br/",
                "Status geral": "Encontrado",
            },
        ]
    )

    gerar_excel(dados, municipios, pd.DataFrame(), output)
    issues = auditar_planilha_final(output, input_path)

    assert any("fora do escopo municipal" in str(descricao) for descricao in issues["Descrição"])
