import pandas as pd

from src.validar_resultados import criar_pendencia, garantir_colunas, validar_resultados


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
