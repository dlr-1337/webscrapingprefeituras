import argparse
import logging

import pandas as pd

from src.escopo_categorias import labels_categorias_obrigatorias
from src import main as main_module


def _args(input_path, output_path, **overrides):
    values = {
        "input_path": str(input_path),
        "output_path": str(output_path),
        "dry_run": False,
        "somente_filtrar": False,
        "limite": None,
        "uf": None,
        "municipio": None,
        "sem_playwright": True,
        "sem_estaduais": True,
        "sem_testar_inferencia_sites": True,
        "sem_busca_web_sites": True,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_executar_pipeline_com_site_ausente_gera_excel_e_pendencia(tmp_path, monkeypatch):
    input_path = tmp_path / "municipios.csv"
    output_path = tmp_path / "resultado.xlsx"
    input_path.write_text(
        "municipio,uf,populacao,capital,site\n"
        "Campinas,SP,1200000,nao,\n",
        encoding="utf-8",
    )

    logger = logging.getLogger("teste_pipeline")
    logger.handlers.clear()
    logger.addHandler(logging.NullHandler())
    monkeypatch.setattr(main_module, "configurar_logger", lambda: logger)
    monkeypatch.setattr(main_module, "salvar_municipios_filtrados", lambda df: tmp_path / "municipios_filtrados.xlsx")

    result = main_module.executar_pipeline(_args(input_path, output_path))

    assert result == output_path
    assert output_path.exists()
    pendencias = pd.read_excel(output_path, sheet_name="Pendências")
    municipios = pd.read_excel(output_path, sheet_name="Municípios pesquisados")
    dados = pd.read_excel(output_path, sheet_name="Dados")
    assert pendencias.loc[0, "Status"] == "Site não localizado"
    assert municipios.loc[0, "Status geral"] == "Site não localizado"
    assert set(dados["Cargo/Área"]) == set(labels_categorias_obrigatorias())
    identidade = dados[dados["Cargo/Área"] == "Município/Capital e UF"].iloc[0]
    prefeito = dados[dados["Cargo/Área"] == "Prefeito"].iloc[0]
    assert identidade["Status"] == "Encontrado"
    assert prefeito["Status"] == "Site não localizado"


def test_executar_pipeline_somente_filtrar_retorna_planilha_filtrada(tmp_path, monkeypatch):
    input_path = tmp_path / "municipios.csv"
    filtered_path = tmp_path / "filtrados.xlsx"
    input_path.write_text(
        "municipio,uf,populacao,capital,site\n"
        "Campinas,SP,1200000,nao,https://campinas.sp.gov.br\n",
        encoding="utf-8",
    )

    logger = logging.getLogger("teste_pipeline_filtrar")
    logger.handlers.clear()
    logger.addHandler(logging.NullHandler())
    monkeypatch.setattr(main_module, "configurar_logger", lambda: logger)
    monkeypatch.setattr(main_module, "salvar_municipios_filtrados", lambda df: filtered_path)
    monkeypatch.setattr(main_module, "project_path", lambda *parts: filtered_path)

    result = main_module.executar_pipeline(_args(input_path, tmp_path / "nao_usado.xlsx", somente_filtrar=True))

    assert result == filtered_path


def test_executar_pipeline_dry_run_imprime_sites_sem_gerar_excel(tmp_path, monkeypatch, capsys):
    input_path = tmp_path / "municipios.csv"
    input_path.write_text(
        "municipio,uf,populacao,capital,site\n"
        "Campinas,SP,1200000,nao,campinas.sp.gov.br\n",
        encoding="utf-8",
    )

    logger = logging.getLogger("teste_pipeline_dry_run")
    logger.handlers.clear()
    logger.addHandler(logging.NullHandler())
    monkeypatch.setattr(main_module, "configurar_logger", lambda: logger)
    monkeypatch.setattr(main_module, "salvar_municipios_filtrados", lambda df: tmp_path / "municipios_filtrados.xlsx")

    result = main_module.executar_pipeline(_args(input_path, tmp_path / "resultado.xlsx", dry_run=True))

    output = capsys.readouterr().out
    assert result is None
    assert "Campinas" in output
    assert "Municipal" in output
    assert "https://campinas.sp.gov.br/" in output


def test_montar_alvos_inclui_governo_estadual_configurado():
    municipios = pd.DataFrame(
        [
            {
                "UF": "SP",
                "Estado": "São Paulo",
                "Município": "Campinas",
                "População": 1200000,
                "Capital": False,
                "Critério de inclusão": "SP acima de 30.000 habitantes",
                "Site oficial": "https://campinas.sp.gov.br/",
            }
        ]
    )

    alvos = main_module._montar_alvos(municipios, incluir_estaduais=True)

    assert set(alvos["Esfera"]) == {"Municipal", "Estadual"}
    estadual = alvos[alvos["Esfera"] == "Estadual"].iloc[0]
    assert estadual["UF"] == "SP"
    assert "Governo" in estadual["Município/Capital"]
    assert estadual["Site oficial"]


def test_nome_igual_localidade_nao_entra_como_pessoa():
    row = pd.Series({"UF": "RS", "Estado": "Rio Grande do Sul", "MunicÃ­pio/Capital": "Santa Maria", "MunicÃ­pio": "Santa Maria"})

    assert main_module._nome_representa_localidade("Santa Maria", row)
    assert main_module._nome_representa_localidade("Santa Maria/RS", row)
    assert not main_module._nome_representa_localidade("Juliana Barboza", row)

    row_com_nome_longo = pd.Series({"UF": "SP", "Estado": "Sao Paulo", "MunicÃ­pio/Capital": "Santa Cruz do Rio Pardo", "MunicÃ­pio": "Santa Cruz do Rio Pardo"})
    assert main_module._nome_representa_localidade("Santa Cruz", row_com_nome_longo)


def test_nome_com_sufixo_geografico_nao_entra_como_pessoa():
    row = pd.Series({"UF": "PR", "Estado": "Parana", "MunicÃ­pio/Capital": "Cascavel", "MunicÃ­pio": "Cascavel"})

    assert main_module._nome_representa_localidade("CASCAVEL NORTE", row)
    assert not main_module._nome_representa_localidade("Nelson Cipriani", row)


def test_fonte_oficial_alternativa_de_porto_velho_cobre_prefeito():
    row = pd.Series(
        {
            "UF": "RO",
            "Estado": "Rondonia",
            "Município/Capital": "Porto Velho",
            "Município": "Porto Velho",
            "Esfera": "Municipal",
            "Site oficial": "https://www.portovelho.ro.gov.br/",
        }
    )

    contatos = main_module._contatos_oficiais_alternativos(row)
    linhas = main_module._linhas_com_cobertura_categorias(
        row,
        contatos,
        "Não publicado",
        "Sem dado oficial claro.",
        "2026-05-25",
    )
    dados = pd.DataFrame(linhas)
    prefeito = dados[dados["Cargo/Área"] == "Prefeito"].iloc[0]

    assert contatos[0]["Nome"] == "Leonardo Barreto de Moraes"
    assert "transparencia.portovelho.ro.gov.br" in prefeito["URL da fonte"]
    assert prefeito["Status"] == "Parcial"


def test_cobertura_preserva_multiplos_contatos_na_mesma_categoria():
    row = pd.Series(
        {
            "UF": "SP",
            "Estado": "São Paulo",
            "Município/Capital": "Campinas",
            "Município": "Campinas",
            "Esfera": "Municipal",
            "Site oficial": "https://campinas.sp.gov.br/",
        }
    )
    contatos = [
        {
            "Órgão/Secretaria": "Gabinete/Prefeitura",
            "Cargo/Área": "Prefeito",
            "Cargo/Órgão": "Prefeito",
            "Nome": "Pessoa Um",
            "E-mail": "um@example.gov.br",
            "URL da fonte": "https://campinas.sp.gov.br/gabinete",
            "Status": "Encontrado",
        },
        {
            "Órgão/Secretaria": "Gabinete/Prefeitura",
            "Cargo/Área": "Prefeito",
            "Cargo/Órgão": "Prefeito",
            "Nome": "Pessoa Dois",
            "E-mail": "dois@example.gov.br",
            "URL da fonte": "https://campinas.sp.gov.br/gabinete",
            "Status": "Encontrado",
        },
    ]

    linhas = main_module._linhas_com_cobertura_categorias(
        row,
        contatos,
        "Não publicado",
        "Sem dado oficial claro.",
        "2026-05-25",
    )

    dados = pd.DataFrame(linhas)
    prefeitos = dados[dados["Cargo/Área"] == "Prefeito"]
    assert len(prefeitos) == 2
    assert set(prefeitos["E-mail"]) == {"um@example.gov.br", "dois@example.gov.br"}
    assert set(labels_categorias_obrigatorias()).issubset(set(dados["Cargo/Área"]))


def test_classifica_chefa_de_gabinete_no_escopo():
    row = pd.Series(
        {
            "UF": "BA",
            "Estado": "Bahia",
            "Município/Capital": "Muritiba",
            "Município": "Muritiba",
            "Esfera": "Municipal",
            "Site oficial": "https://www.muritiba.ba.gov.br/",
        }
    )
    contatos = [
        {
            "Órgão/Secretaria": "Contato geral",
            "Cargo/Área": "Contato geral",
            "Cargo/Órgão": "Contato geral",
            "Nome": "",
            "E-mail": "gabinete@muritiba.ba.gov.br",
            "URL da fonte": "https://www.muritiba.ba.gov.br/secretaria/14/chefa-de-gabinete",
            "Status": "Parcial",
        }
    ]

    linhas = main_module._linhas_com_cobertura_categorias(
        row,
        contatos,
        "Não publicado",
        "Sem dado oficial claro.",
        "2026-05-25",
    )

    dados = pd.DataFrame(linhas)
    gabinete = dados[dados["Cargo/Área"] == "Chefe de gabinete"].iloc[0]
    assert gabinete["E-mail"] == "gabinete@muritiba.ba.gov.br"
    assert gabinete["Status"] == "Parcial"
