import pandas as pd
import pytest

from src.carregar_municipios import carregar_municipios, normalizar_colunas


def test_normaliza_colunas_flexiveis_e_completa_dados_derivados():
    df = pd.DataFrame(
        [
            {
                "cidade": "  Campinas  ",
                "estado": "Sao Paulo",
                "uf": "",
                "habitantes": "1.139.047",
                "capital": "nao",
                "site": " campinas.sp.gov.br ",
            },
            {
                "cidade": "Brasilia",
                "estado": "",
                "uf": "df",
                "habitantes": "2.817.381",
                "capital": "",
                "site": "",
            },
        ]
    )

    result = normalizar_colunas(df)

    assert list(result.columns) == ["UF", "Estado", "Município", "População", "Capital", "Site oficial"]
    assert result.loc[0, "UF"] == "SP"
    assert result.loc[0, "População"] == 1139047
    assert bool(result.loc[0, "Capital"]) is False
    assert result.loc[0, "Site oficial"] == "campinas.sp.gov.br"
    assert result.loc[1, "Estado"] == "Distrito Federal"
    assert bool(result.loc[1, "Capital"]) is True


def test_carrega_csv_com_separador_detectado(tmp_path):
    input_path = tmp_path / "municipios.csv"
    input_path.write_text(
        "municipio;uf;populacao;capital;site\n"
        "Curitiba;PR;1773718;sim;https://curitiba.pr.gov.br\n",
        encoding="utf-8",
    )

    result = carregar_municipios(input_path)

    assert len(result) == 1
    assert result.loc[0, "Município"] == "Curitiba"
    assert result.loc[0, "UF"] == "PR"
    assert bool(result.loc[0, "Capital"]) is True


def test_carregar_municipios_rejeita_arquivo_inexistente(tmp_path):
    with pytest.raises(FileNotFoundError, match="Base de municípios não encontrada"):
        carregar_municipios(tmp_path / "ausente.csv")


def test_carregar_municipios_rejeita_formato_nao_suportado(tmp_path):
    input_path = tmp_path / "municipios.txt"
    input_path.write_text("municipio,uf\nCampinas,SP\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Formato não suportado"):
        carregar_municipios(input_path)


def test_carregar_municipios_rejeita_linhas_sem_municipio_ou_uf(tmp_path):
    input_path = tmp_path / "municipios.csv"
    input_path.write_text(
        "municipio,uf,populacao\n"
        ",SP,100000\n"
        "Cidade sem UF,,100000\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="2 linha"):
        carregar_municipios(input_path)
