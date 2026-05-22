from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

import pandas as pd

from src.carregar_municipios import carregar_municipios
from src.coletar_paginas import FonteConsultada, carregar_config_scraping, coletar_paginas
from src.extrair_contatos import carregar_cargos, extrair_contatos_paginas
from src.filtrar_municipios import aplicar_filtros_cli, filtrar_municipios, salvar_municipios_filtrados
from src.gerar_excel import gerar_excel
from src.localizar_sites import preencher_sites
from src.logger import configurar_logger
from src.normalizar_dados import normalizar_resultados
from src.utils import ensure_project_dirs, load_yaml, project_path
from src.validar_resultados import criar_pendencia, validar_resultados


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Robo de coleta de contatos publicos em sites oficiais de prefeituras brasileiras."
    )
    parser.add_argument("--input", dest="input_path", help="Caminho para XLSX ou CSV com a base de municípios.")
    parser.add_argument(
        "--output",
        dest="output_path",
        default=str(project_path("data", "output", "resultado_final_point_c.xlsx")),
        help="Caminho do Excel final.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Carrega, filtra e localiza sites sem coletar páginas.")
    parser.add_argument("--somente-filtrar", action="store_true", help="Executa apenas carregamento e filtro de municípios.")
    parser.add_argument("--limite", type=int, help="Limita a quantidade de municípios processados.")
    parser.add_argument("--uf", help="Processa apenas uma UF.")
    parser.add_argument("--municipio", help="Processa apenas um município.")
    parser.add_argument("--sem-playwright", action="store_true", help="Desativa uso opcional de Playwright.")
    parser.add_argument("--sem-estaduais", action="store_true", help="Desativa fontes configuradas de governos estaduais.")
    return parser.parse_args()


def resolver_input(input_path: str | None) -> Path:
    if input_path:
        return Path(input_path)
    candidates = [
        project_path("data", "input", "municipios_ibge.xlsx"),
        project_path("data", "input", "municipios_ibge.csv"),
        project_path("data", "input", "exemplo_municipios.csv"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError("Nenhuma base encontrada em data/input.")


def carregar_governos_estaduais(path: str | Path | None = None) -> dict:
    config_path = Path(path) if path else project_path("config", "governos_estaduais.yml")
    if not config_path.exists():
        return {}
    data = load_yaml(config_path)
    return data.get("governos_estaduais", data)


def _metadata_alvo(row: pd.Series) -> dict:
    municipio = row.get("Município", "")
    municipio_capital = row.get("Município/Capital", "") or municipio
    return {
        "UF": row.get("UF", ""),
        "Estado": row.get("Estado", ""),
        "Município/Capital": municipio_capital,
        "Município": municipio,
        "População": row.get("População", ""),
        "Critério de inclusão": row.get("Critério de inclusão", ""),
        "Esfera": row.get("Esfera", "Municipal") or "Municipal",
        "Site oficial": row.get("Site oficial", ""),
    }


def _linha_resultado_pendencia(row: pd.Series, status: str, observacoes: str) -> dict:
    data = _metadata_alvo(row)
    data.update(
        {
            "Órgão/Secretaria": "",
            "Cargo/Área": "",
            "Cargo/Órgão": "",
            "Nome": "",
            "E-mail": "",
            "Telefone": "",
            "Celular/WhatsApp": "",
            "Celular": "",
            "URL da fonte": row.get("Site oficial", ""),
            "URL específica": row.get("Site oficial", ""),
            "Data da coleta": datetime.now().date().isoformat(),
            "Status": status,
            "Observações": observacoes,
        }
    )
    return data


def _criar_alvos_municipais(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    result["Esfera"] = "Municipal"
    result["Município/Capital"] = result["Município"]
    return result


def _criar_alvos_estaduais(municipios_df: pd.DataFrame, governos_config: dict) -> pd.DataFrame:
    rows: list[dict] = []
    for uf, grupo in municipios_df.groupby("UF", sort=True):
        config = governos_config.get(str(uf).upper())
        if not config:
            continue
        site = str(config.get("site", "")).strip()
        if not site:
            continue
        first = grupo.iloc[0]
        nome = str(config.get("nome") or f"Governo Estadual {uf}")
        rows.append(
            {
                "UF": str(uf).upper(),
                "Estado": config.get("estado") or first.get("Estado", ""),
                "Município/Capital": nome,
                "Município": nome,
                "População": "",
                "Capital": False,
                "Critério de inclusão": "Fonte estadual configurada",
                "Esfera": "Estadual",
                "Site oficial": site,
            }
        )
    return pd.DataFrame(rows)


def _montar_alvos(municipios_com_sites: pd.DataFrame, incluir_estaduais: bool) -> pd.DataFrame:
    municipais = _criar_alvos_municipais(municipios_com_sites)
    if not incluir_estaduais:
        return municipais
    estaduais = _criar_alvos_estaduais(municipios_com_sites, carregar_governos_estaduais())
    if estaduais.empty:
        return municipais
    return pd.concat([municipais, estaduais], ignore_index=True)


def _fonte_para_linha(row: pd.Series, fonte: FonteConsultada) -> dict:
    meta = _metadata_alvo(row)
    return {
        **meta,
        "URL consultada": fonte.url,
        "URL final": fonte.url_final,
        "Status": fonte.status,
        "HTTP": "" if fonte.status_http is None else fonte.status_http,
        "Método": fonte.metodo,
        "Gerou texto": "Sim" if fonte.gerou_texto else "Não",
        "Data/hora": fonte.data_hora,
        "Observações": fonte.observacoes,
    }


def executar_pipeline(args: argparse.Namespace) -> Path | None:
    ensure_project_dirs()
    logger = configurar_logger()
    logger.info("Início da execução")

    input_path = resolver_input(args.input_path)
    logger.info("Carregando base de municípios: %s", input_path)
    municipios = carregar_municipios(input_path)
    municipios_filtrados = filtrar_municipios(municipios)
    municipios_filtrados = aplicar_filtros_cli(municipios_filtrados, args.uf, args.municipio, args.limite)
    salvar_municipios_filtrados(municipios_filtrados)
    logger.info("Municípios no escopo após filtros: %s", len(municipios_filtrados))

    if args.somente_filtrar:
        logger.info("Execução encerrada por --somente-filtrar")
        return project_path("data", "output", "municipios_filtrados.xlsx")

    municipios_com_sites = preencher_sites(municipios_filtrados, testar_inferencia=False)
    alvos = _montar_alvos(municipios_com_sites, incluir_estaduais=not args.sem_estaduais)

    if args.dry_run:
        logger.info("Dry-run concluído sem coleta de páginas.")
        print(alvos[["UF", "Município/Capital", "Esfera", "Site oficial"]].to_string(index=False))
        return None

    scraping_config = carregar_config_scraping()
    if args.sem_playwright:
        scraping_config["usar_playwright_quando_necessario"] = False

    palavras_config = load_yaml(project_path("config", "palavras_chave.yml"))
    palavras_chave = palavras_config.get("palavras_chave", [])
    cargos_config = carregar_cargos()

    resultados: list[dict] = []
    pendencias: list[dict] = []
    municipios_pesquisados: list[dict] = []
    fontes_log: list[dict] = []
    data_coleta = datetime.now().date().isoformat()

    for _, row in alvos.iterrows():
        uf = str(row.get("UF", ""))
        municipio = str(row.get("Município", ""))
        municipio_capital = str(row.get("Município/Capital", municipio))
        esfera = str(row.get("Esfera", "Municipal") or "Municipal")
        site = str(row.get("Site oficial", ""))
        logger.info("Processando alvo: %s/%s/%s", municipio_capital, uf, esfera)

        status_geral = "Não publicado"
        observacao_geral = ""

        if not site:
            status_geral = "Site não localizado"
            observacao_geral = str(row.get("Observações localização site", "Site oficial não informado."))
            resultados.append(_linha_resultado_pendencia(row, status_geral, observacao_geral))
            fontes_log.append(
                {
                    **_metadata_alvo(row),
                    "URL consultada": "",
                    "URL final": "",
                    "Status": status_geral,
                    "HTTP": "",
                    "Método": "",
                    "Gerou texto": "Não",
                    "Data/hora": datetime.now().isoformat(timespec="seconds"),
                    "Observações": observacao_geral,
                }
            )
            pendencias.append(
                criar_pendencia(uf, municipio, "Site", "Site oficial não localizado na base.", status_geral, "", observacao_geral, esfera, municipio_capital)
            )
        else:
            try:
                coleta = coletar_paginas(site, palavras_chave, scraping_config, logger=logger)
                fontes_log.extend(_fonte_para_linha(row, fonte) for fonte in (coleta.fontes_consultadas or []))
                if not coleta.paginas:
                    status_geral = coleta.status
                    observacao_geral = coleta.observacoes
                    resultados.append(_linha_resultado_pendencia(row, status_geral, observacao_geral))
                    pendencias.append(
                        criar_pendencia(uf, municipio, "Coleta", observacao_geral, status_geral, site, "", esfera, municipio_capital)
                    )
                else:
                    contatos = extrair_contatos_paginas(coleta.paginas, cargos_config)
                    if contatos:
                        status_geral = "Encontrado" if any(item.get("Status") == "Encontrado" for item in contatos) else "Parcial"
                        observacao_geral = f"{len(contatos)} registro(s) de contato extraído(s)."
                        for contato in contatos:
                            linha = _metadata_alvo(row)
                            linha.update(contato)
                            linha["Data da coleta"] = data_coleta
                            resultados.append(linha)
                        logger.info("Dados encontrados em %s/%s/%s: %s", municipio_capital, uf, esfera, len(contatos))
                    else:
                        status_geral = "Não publicado"
                        observacao_geral = "Páginas coletadas, mas sem contatos associados aos cargos configurados."
                        resultados.append(_linha_resultado_pendencia(row, status_geral, observacao_geral))
                        pendencias.append(
                            criar_pendencia(
                                uf,
                                municipio,
                                "Contato",
                                "Nenhum contato compatível com cargos/secretarias configurados.",
                                status_geral,
                                site,
                                observacao_geral,
                                esfera,
                                municipio_capital,
                            )
                        )
            except Exception as exc:  # pragma: no cover - proteção operacional do pipeline
                status_geral = "Necessita validação manual"
                observacao_geral = f"Erro inesperado ao processar alvo: {exc}"
                logger.exception("Erro ao processar %s/%s/%s", municipio_capital, uf, esfera)
                resultados.append(_linha_resultado_pendencia(row, status_geral, observacao_geral))
                pendencias.append(
                    criar_pendencia(uf, municipio, "Erro", observacao_geral, status_geral, site, "", esfera, municipio_capital)
                )

        municipios_pesquisados.append(
            {
                "UF": uf,
                "Estado": row.get("Estado", ""),
                "Município/Capital": municipio_capital,
                "Município": municipio,
                "População": row.get("População", ""),
                "Critério de inclusão": row.get("Critério de inclusão", ""),
                "Esfera": esfera,
                "Site oficial": site,
                "Status geral": status_geral,
                "Observações": observacao_geral,
            }
        )

    resultado_df = normalizar_resultados(pd.DataFrame(resultados))
    pendencias.extend(validar_resultados(resultado_df))
    municipios_df = pd.DataFrame(municipios_pesquisados)
    pendencias_df = pd.DataFrame(pendencias)
    fontes_df = pd.DataFrame(fontes_log)

    output = gerar_excel(resultado_df, municipios_df, pendencias_df, args.output_path, fontes_df)
    logger.info("Excel final gerado: %s", output)
    logger.info("Fim da execução")
    return output


def main() -> None:
    executar_pipeline(parse_args())


if __name__ == "__main__":
    main()
