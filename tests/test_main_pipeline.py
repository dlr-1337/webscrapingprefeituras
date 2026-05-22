import argparse
import logging

import pandas as pd

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
    assert pendencias.loc[0, "Status"] == "Site não localizado"
    assert municipios.loc[0, "Status geral"] == "Site não localizado"


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
