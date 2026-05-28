from __future__ import annotations

import argparse
import re
import unicodedata
from datetime import datetime
from pathlib import Path

import pandas as pd

from src.carregar_municipios import carregar_municipios
from src.coletar_paginas import FonteConsultada, carregar_config_scraping, coletar_paginas
from src.escopo_categorias import (
    CATEGORIA_IDENTIFICACAO,
    CATEGORIAS_DE_COLETA,
    FONTE_TERRITORIAL_URL,
    categoria_por_label,
    classificar_categoria_resultado,
)
from src.extrair_contatos import carregar_cargos, extrair_contatos_paginas
from src.filtrar_municipios import aplicar_filtros_cli, filtrar_municipios, salvar_municipios_filtrados
from src.gerar_excel import gerar_excel
from src.localizar_sites import preencher_sites
from src.logger import configurar_logger
from src.normalizar_dados import normalizar_resultados
from src.utils import clean_url, ensure_project_dirs, load_yaml, project_path
from src.validar_resultados import criar_pendencia, validar_resultados


FONTES_OFICIAIS_ALTERNATIVAS = [
    {
        "UF": "RO",
        "Município/Capital": "Porto Velho",
        "Esfera": "Municipal",
        "Cargo/Órgão": "Prefeito",
        "Órgão/Secretaria": "Gabinete/Prefeitura",
        "Nome": "Leonardo Barreto de Moraes",
        "URL da fonte": "https://transparencia.portovelho.ro.gov.br/despesas/despesas/149693ea-d294-4a75-ac9a-0b2700eaf822",
        "Status": "Parcial",
        "Observações": "Fonte oficial alternativa usada porque a página institucional do prefeito retornou 502 durante a validação.",
    }
]


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
    parser.add_argument(
        "--sem-testar-inferencia-sites",
        action="store_true",
        help="Não testa URLs oficiais .gov.br inferidas quando a base não informa site.",
    )
    parser.add_argument(
        "--sem-busca-web-sites",
        action="store_true",
        help="Não usa busca web oficial para localizar sites ausentes na base.",
    )
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


def _contatos_oficiais_alternativos(row: pd.Series) -> list[dict]:
    uf = str(row.get("UF", "")).upper()
    municipio = _normalizar_identidade(row.get("Município/Capital", "") or row.get("Município", ""))
    esfera = _normalizar_identidade(row.get("Esfera", "Municipal") or "Municipal")
    contatos: list[dict] = []
    for fonte in FONTES_OFICIAIS_ALTERNATIVAS:
        if str(fonte.get("UF", "")).upper() != uf:
            continue
        if _normalizar_identidade(fonte.get("Município/Capital", "")) != municipio:
            continue
        if _normalizar_identidade(fonte.get("Esfera", "Municipal")) != esfera:
            continue
        cargo = str(fonte.get("Cargo/Órgão", ""))
        url = clean_url(fonte.get("URL da fonte", ""))
        contatos.append(
            {
                "Órgão/Secretaria": fonte.get("Órgão/Secretaria", ""),
                "Cargo/Área": cargo,
                "Cargo/Órgão": cargo,
                "Nome": fonte.get("Nome", ""),
                "E-mail": fonte.get("E-mail", ""),
                "Telefone": fonte.get("Telefone", ""),
                "Celular/WhatsApp": fonte.get("Celular/WhatsApp", ""),
                "Celular": fonte.get("Celular", ""),
                "URL da fonte": url,
                "URL específica": url,
                "Status": fonte.get("Status", "Parcial"),
                "Observações": fonte.get("Observações", ""),
            }
        )
    return contatos


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


def _url_referencia(row: pd.Series) -> str:
    return clean_url(row.get("Site oficial", "")) or FONTE_TERRITORIAL_URL


def _linha_resultado_categoria(
    row: pd.Series,
    categoria_label: str,
    status: str,
    observacoes: str,
    data_coleta: str,
    url_fonte: str = "",
) -> dict:
    categoria = categoria_por_label(categoria_label)
    data = _metadata_alvo(row)
    fonte = clean_url(url_fonte) or _url_referencia(row)
    nome = ""
    if categoria_label == CATEGORIA_IDENTIFICACAO.label:
        nome = f"{data.get('Município/Capital')}/{data.get('UF')}"
        observacoes = observacoes or "Localidade e UF carregadas da base territorial do escopo."
        fonte = FONTE_TERRITORIAL_URL

    data.update(
        {
            "Órgão/Secretaria": categoria.orgao_secretaria,
            "Cargo/Área": categoria.label,
            "Cargo/Órgão": categoria.cargo_area,
            "Nome": nome,
            "E-mail": "",
            "Telefone": "",
            "Celular/WhatsApp": "",
            "Celular": "",
            "URL da fonte": fonte,
            "URL específica": fonte,
            "Data da coleta": data_coleta,
            "Status": status,
            "Observações": observacoes,
        }
    )
    return data


def _linha_contato_com_metadata(row: pd.Series, contato: dict, data_coleta: str) -> tuple[dict, str]:
    categoria_label = classificar_categoria_resultado(contato)
    linha = _metadata_alvo(row)
    linha.update(contato)
    linha["Data da coleta"] = linha.get("Data da coleta") or data_coleta
    linha["URL da fonte"] = clean_url(linha.get("URL da fonte", "")) or _url_referencia(row)
    linha["URL específica"] = clean_url(linha.get("URL específica", "")) or linha["URL da fonte"]

    if categoria_label:
        categoria = categoria_por_label(categoria_label)
        linha["Cargo/Área"] = categoria.label
        linha["Cargo/Órgão"] = linha.get("Cargo/Órgão") or categoria.cargo_area
        linha["Órgão/Secretaria"] = linha.get("Órgão/Secretaria") or categoria.orgao_secretaria

    return linha, categoria_label


def _normalizar_identidade(texto: str) -> str:
    texto_ascii = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", " ", texto_ascii.lower()).strip()


def _nome_representa_localidade(nome: str, row: pd.Series) -> bool:
    nome_norm = _normalizar_identidade(nome)
    if not nome_norm:
        return False

    municipio = (
        row.get("Município/Capital", "")
        or row.get("MunicÃ­pio/Capital", "")
        or row.get("Município", "")
        or row.get("MunicÃ­pio", "")
    )
    municipio_norm = _normalizar_identidade(municipio)
    uf_norm = _normalizar_identidade(row.get("UF", ""))
    estado_norm = _normalizar_identidade(row.get("Estado", ""))
    localidade_variantes = {
        municipio_norm,
        f"{municipio_norm} {uf_norm}".strip(),
        f"{municipio_norm} {estado_norm}".strip(),
    }
    if nome_norm in localidade_variantes:
        return True

    if municipio_norm and nome_norm.startswith(f"{municipio_norm} "):
        sufixo = nome_norm.removeprefix(f"{municipio_norm} ").strip()
        if sufixo in {"centro", "norte", "sul", "leste", "oeste"}:
            return True

    if municipio_norm.startswith(f"{nome_norm} "):
        prefixos_toponimicos = {"alto", "alta", "baixo", "baixa", "bela", "belo", "bom", "boa", "campo", "nova", "novo", "rio", "santa", "santo", "sao"}
        primeira_palavra = nome_norm.split(" ", 1)[0]
        return primeira_palavra in prefixos_toponimicos and len(nome_norm.split()) >= 2

    return False


def _pontuacao_linha_categoria(linha: dict) -> tuple[int, int, int, int, str]:
    status = str(linha.get("Status", ""))
    url = str(linha.get("URL da fonte", "") or linha.get("URL específica", "")).lower()
    nome = str(linha.get("Nome", "") or "").strip()
    tem_contato = any(str(linha.get(campo, "") or "").strip() for campo in ("E-mail", "Telefone", "Celular/WhatsApp", "Celular"))
    status_score = {"Encontrado": 4, "Parcial": 2}.get(status, 0)
    contato_score = 1 if tem_contato else 0
    nome_score = 1 if nome else 0
    fonte_score = 0
    if any(token in url for token in ("equipe_governo", "equipe-governo", "equipe-de-governo")):
        fonte_score += 3
    if any(token in url for token in ("estrutura", "gabinete", "secretaria")):
        fonte_score += 1
    if any(token in url for token in ("default.aspx", "consulta_publica", "fundosocial")):
        fonte_score -= 2
    return status_score, contato_score, nome_score, fonte_score, url


def _linhas_com_cobertura_categorias(
    row: pd.Series,
    contatos: list[dict],
    status_faltante: str,
    observacao_faltante: str,
    data_coleta: str,
) -> list[dict]:
    linhas = [
        _linha_resultado_categoria(
            row,
            CATEGORIA_IDENTIFICACAO.label,
            "Encontrado",
            "Localidade e UF carregadas da base territorial do escopo.",
            data_coleta,
            FONTE_TERRITORIAL_URL,
        )
    ]
    candidatos_por_categoria: dict[str, list[dict]] = {}

    for contato in contatos:
        linha, categoria_label = _linha_contato_com_metadata(row, contato, data_coleta)
        if not categoria_label:
            continue
        if categoria_label == CATEGORIA_IDENTIFICACAO.label:
            continue
        if _nome_representa_localidade(str(linha.get("Nome", "")), row):
            linha["Nome"] = ""
            if not any(str(linha.get(campo, "") or "").strip() for campo in ("E-mail", "Telefone", "Celular/WhatsApp", "Celular")):
                continue
        candidatos_por_categoria.setdefault(categoria_label, []).append(linha)

    for categoria in CATEGORIAS_DE_COLETA:
        candidatos = candidatos_por_categoria.get(categoria.label, [])
        if candidatos:
            linhas.extend(sorted(candidatos, key=_pontuacao_linha_categoria, reverse=True))
            continue
        linhas.append(_linha_resultado_categoria(row, categoria.label, status_faltante, observacao_faltante, data_coleta))

    return linhas


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

    municipios_com_sites = preencher_sites(
        municipios_filtrados,
        testar_inferencia=not getattr(args, "sem_testar_inferencia_sites", False),
        usar_busca_web=not getattr(args, "sem_busca_web_sites", False),
    )
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
            resultados.extend(
                _linhas_com_cobertura_categorias(row, [], status_geral, observacao_geral, data_coleta)
            )
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
                contatos_alternativos = _contatos_oficiais_alternativos(row)
                if not coleta.paginas and not contatos_alternativos:
                    status_geral = coleta.status
                    observacao_geral = coleta.observacoes
                    resultados.extend(
                        _linhas_com_cobertura_categorias(row, [], status_geral, observacao_geral, data_coleta)
                    )
                    pendencias.append(
                        criar_pendencia(uf, municipio, "Coleta", observacao_geral, status_geral, site, "", esfera, municipio_capital)
                    )
                else:
                    contatos = contatos_alternativos + extrair_contatos_paginas(coleta.paginas, cargos_config)
                    if contatos:
                        status_geral = "Encontrado" if any(item.get("Status") == "Encontrado" for item in contatos) else "Parcial"
                        observacao_geral = f"{len(contatos)} registro(s) de contato extraído(s)."
                        resultados.extend(
                            _linhas_com_cobertura_categorias(
                                row,
                                contatos,
                                "Não publicado",
                                "Páginas oficiais consultadas, mas sem dado oficial claro para esta categoria.",
                                data_coleta,
                            )
                        )
                        logger.info("Dados encontrados em %s/%s/%s: %s", municipio_capital, uf, esfera, len(contatos))
                    else:
                        status_geral = "Não publicado"
                        observacao_geral = "Páginas coletadas, mas sem contatos associados aos cargos configurados."
                        resultados.extend(
                            _linhas_com_cobertura_categorias(row, [], status_geral, observacao_geral, data_coleta)
                        )
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
                resultados.extend(
                    _linhas_com_cobertura_categorias(row, [], status_geral, observacao_geral, data_coleta)
                )
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

    municipios_df = pd.DataFrame(municipios_pesquisados)
    resultado_df = normalizar_resultados(pd.DataFrame(resultados))
    pendencias.extend(validar_resultados(resultado_df, municipios_df))
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
