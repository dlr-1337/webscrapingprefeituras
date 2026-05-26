import pandas as pd

import src.validar_fontes_oficiais as modulo
from src.validar_fontes_oficiais import _texto_contem_valor, selecionar_linhas_para_validacao, validar_registros


def test_validar_registros_confere_campos_na_fonte():
    dados = pd.DataFrame(
        [
            {
                "UF": "AC",
                "Município/Capital": "Rio Branco",
                "Cargo/Área": "Desenvolvimento econômico",
                "Status": "Encontrado",
                "Nome": "Coronel Ezequiel de Oliveira Bino",
                "E-mail": "ezequiel.bino@riobranco.ac.gov.br; sdti@riobranco.ac.gov.br",
                "Telefone": "(68) 3212-7307",
                "Celular/WhatsApp": "",
                "URL da fonte": "https://fonte.test/sdti",
            }
        ]
    )

    def fetcher(url):
        assert url == "https://fonte.test/sdti"
        return (
            "Secretaria de Desenvolvimento Econômico Secretário Coronel Ezequiel de Oliveira Bino "
            "ezequiel.bino@riobranco.ac.gov.br sdti@riobranco.ac.gov.br +55 (68) 3212-7307",
            "Encontrado",
            "",
        )

    result = validar_registros(dados, fetcher)

    status_col = next(c for c in result.columns if str(c).startswith("Status valida"))
    assert result.loc[0, status_col] == "Validado"
    assert result.loc[0, "Campos conferidos"] == 4


def test_baixar_texto_playwright_combina_texto_de_requests(monkeypatch):
    monkeypatch.setattr(
        modulo,
        "_baixar_com_navegador",
        lambda url, timeout, backend: ("<html><body>Portal resumido</body></html>", "Encontrado", "", url, 200, "text/html", "playwright"),
    )
    monkeypatch.setattr(modulo, "criar_sessao", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(
        modulo,
        "_baixar",
        lambda session, url, timeout: (
            "<html><body>Prefeito Municipal Tadeu Dias</body></html>",
            "Encontrado",
            "",
            url,
            200,
            "text/html",
            "requests",
        ),
    )

    texto, status, _obs = modulo.baixar_texto_playwright("https://fonte.test/prefeito", timeout=1)

    assert status == "Encontrado"
    assert "Portal resumido" in texto
    assert "Tadeu Dias" in texto


def test_validar_desenvolvimento_economico_aceita_industria_e_comercio_oficial():
    dados = pd.DataFrame(
        [
            {
                "UF": "GO",
                "Municipio/Capital": "Anicuns",
                "Cargo/Area": "Desenvolvimento econômico",
                "Orgao/Secretaria": "Secretaria Municipal de Indústria e Comércio",
                "Status": "Encontrado",
                "Nome": "",
                "E-mail": "agricultura@anicuns.go.gov.br",
                "Telefone": "",
                "Celular/WhatsApp": "",
                "URL da fonte": "https://fonte.test/industria-comercio",
            }
        ]
    )
    texto = """
    Secretaria Municipal de Indústria e Comércio
    E-mail:
    agricultura@anicuns.go.gov.br
    Competências
    Orientar o desenvolvimento industrial e comercial.
    """

    result = validar_registros(dados, lambda _url: (texto, "Encontrado", ""), max_linhas=0)

    status_col = next(c for c in result.columns if str(c).startswith("Status valida"))
    assert result.loc[0, status_col] == "Validado"


def test_validar_registros_aponta_divergencia():
    dados = pd.DataFrame(
        [
            {
                "UF": "SP",
                "Município/Capital": "Campinas",
                "Cargo/Área": "Prefeito",
                "Status": "Encontrado",
                "Nome": "Nome Ausente",
                "E-mail": "prefeito@campinas.sp.gov.br",
                "Telefone": "",
                "Celular/WhatsApp": "",
                "URL da fonte": "https://fonte.test/prefeito",
            }
        ]
    )

    result = validar_registros(dados, lambda _url: ("prefeito@campinas.sp.gov.br", "Encontrado", ""))

    assert result.loc[0, "Status validação"] == "Divergente"
    assert "Nome não localizado" in result.loc[0, "Observações"]


def test_validar_registros_registra_falha_de_navegador_sem_quebrar():
    dados = pd.DataFrame(
        [
            {
                "UF": "SP",
                "Município/Capital": "Campinas",
                "Cargo/Área": "Prefeito",
                "Status": "Encontrado",
                "Nome": "Maria Silva",
                "E-mail": "",
                "Telefone": "",
                "Celular/WhatsApp": "",
                "URL da fonte": "https://fonte.test/prefeito",
            }
        ]
    )

    result = validar_registros(dados, lambda _url: (_ for _ in ()).throw(RuntimeError("timeout")))

    assert result.loc[0, "Status validação"] == "Não validado"
    assert "Erro ao abrir fonte" in result.loc[0, "Observações"]


def test_validar_registros_nao_compara_html_de_erro_como_divergencia():
    dados = pd.DataFrame(
        [
            {
                "UF": "SP",
                "MunicÃ­pio/Capital": "Boituva",
                "Cargo/Ãrea": "Prefeito",
                "Status": "Encontrado",
                "Nome": "",
                "E-mail": "",
                "Telefone": "(15) 3363-8800",
                "Celular/WhatsApp": "",
                "URL da fonte": "https://fonte.test/gabinete",
            }
        ]
    )

    result = validar_registros(dados, lambda _url: ("Cloudflare Error 522", "Site fora do ar", "HTTP 522."))

    status_col = next(c for c in result.columns if str(c).startswith("Status valida"))
    assert result.loc[0, status_col] == "N\u00e3o validado"


def test_validacao_telefone_nao_remove_ddd_55_do_texto_da_pagina():
    texto = "Telefone:\n(55) 3398-0040\nFuncionamento: das 9h as 15h"

    assert _texto_contem_valor(texto, "Telefone", "(55) 3398-0040")


def test_selecionar_linhas_para_validacao_ignora_linhas_sem_campos():
    dados = pd.DataFrame(
        [
            {"UF": "SP", "Cargo/Área": "Município/Capital e UF", "Status": "Encontrado", "Nome": "Campinas/SP", "E-mail": "", "Telefone": "", "Celular/WhatsApp": ""},
            {"UF": "RJ", "Status": "Encontrado", "Nome": "Maria Silva", "E-mail": "", "Telefone": "", "Celular/WhatsApp": ""},
        ]
    )

    selected = selecionar_linhas_para_validacao(dados)

    assert len(selected) == 1
    assert selected.iloc[0]["UF"] == "RJ"


def test_selecionar_linhas_zero_retorna_todas_elegiveis():
    dados = pd.DataFrame(
        [
            {"UF": "SP", "Cargo/Área": "Prefeito", "Status": "Encontrado", "Nome": "Maria Silva", "E-mail": "", "Telefone": "", "Celular/WhatsApp": ""},
            {"UF": "RJ", "Cargo/Área": "Prefeito", "Status": "Encontrado", "Nome": "João Souza", "E-mail": "", "Telefone": "", "Celular/WhatsApp": ""},
        ]
    )

    selected = selecionar_linhas_para_validacao(dados, max_linhas=0)

    assert len(selected) == 2


def test_validar_registros_rejeita_nome_estranho_mesmo_presente_na_fonte():
    dados = pd.DataFrame(
        [
            {
                "UF": "GO",
                "Município/Capital": "Pires do Rio",
                "Cargo/Área": "Prefeito",
                "Órgão/Secretaria": "Gabinete/Prefeitura",
                "Status": "Encontrado",
                "Nome": "Base Jurídica",
                "E-mail": "gabinete@piresdorio.go.gov.br",
                "Telefone": "",
                "Celular/WhatsApp": "(64) 98440-0020",
                "URL da fonte": "https://piresdorio.go.gov.br/estrutura/gabinete-da-prefeito/",
            }
        ]
    )

    texto = "Gabinete da Prefeita Base Jurídica gabinete@piresdorio.go.gov.br (64) 98440-0020"
    result = validar_registros(dados, lambda _url: (texto, "Encontrado", ""))

    assert result.loc[0, "Status validação"] == "Divergente"
    assert "não parece pessoa" in result.loc[0, "Observações"]


def test_validar_registros_rejeita_rotulo_sessao_transmissao():
    dados = pd.DataFrame(
        [
            {
                "UF": "BA",
                "Municipio/Capital": "Itajuipe",
                "Cargo/Area": "Prefeito",
                "Orgao/Secretaria": "Gabinete/Prefeitura",
                "Status": "Parcial",
                "Nome": "Sessao Transmissao",
                "E-mail": "",
                "Telefone": "",
                "Celular/WhatsApp": "",
                "URL da fonte": "https://fonte.test/homepage",
            }
        ]
    )
    texto = "Prefeito Sessao Transmissao Portal oficial"

    result = validar_registros(dados, lambda _url: (texto, "Encontrado", ""), max_linhas=0)

    status_col = next(c for c in result.columns if str(c).startswith("Status valida"))
    obs_col = next(c for c in result.columns if str(c).startswith("Observa"))
    assert result.loc[0, status_col] == "Divergente"
    assert "pessoa" in result.loc[0, obs_col].lower()


def test_validar_registros_rejeita_rotulo_verba_indenizatoria():
    dados = pd.DataFrame(
        [
            {
                "UF": "BA",
                "Municipio/Capital": "Itubera",
                "Cargo/Area": "Prefeito",
                "Orgao/Secretaria": "Gabinete/Prefeitura",
                "Status": "Parcial",
                "Nome": "Valores Cotas Verba Indenizatoria Ativ",
                "E-mail": "",
                "Telefone": "",
                "Celular/WhatsApp": "",
                "URL da fonte": "https://fonte.test/homepage",
            }
        ]
    )
    texto = "Prefeito Valores Cotas Verba Indenizatoria Ativ"

    result = validar_registros(dados, lambda _url: (texto, "Encontrado", ""), max_linhas=0)

    status_col = next(c for c in result.columns if str(c).startswith("Status valida"))
    obs_col = next(c for c in result.columns if str(c).startswith("Observa"))
    assert result.loc[0, status_col] == "Divergente"
    assert "pessoa" in result.loc[0, obs_col].lower()


def test_validar_registros_rejeita_nome_presente_apenas_em_endereco():
    dados = pd.DataFrame(
        [
            {
                "UF": "MG",
                "MunicÃ­pio/Capital": "Lajinha",
                "Cargo/Ãrea": "Prefeito",
                "Ã“rgÃ£o/Secretaria": "Gabinete/Prefeitura",
                "Status": "Encontrado",
                "Nome": "Rubens Boechat",
                "E-mail": "",
                "Telefone": "(33) 3344-2796",
                "Celular/WhatsApp": "",
                "URL da fonte": "https://fonte.test/cultura",
            }
        ]
    )
    texto = """
    Secretaria de Cultura e Turismo
    Telefone: (33) 3344-2796
    Endereco
    Av. Dr. Rubens Boechat de Oliveira, Centro, Lajinha, MG, 36980000
    Descricao
    Prestar assessoramento direto ao Prefeito.
    """

    result = validar_registros(dados, lambda _url: (texto, "Encontrado", ""))

    status_col = next(c for c in result.columns if str(c).startswith("Status valida"))
    obs_col = next(c for c in result.columns if str(c).startswith("Observa"))
    assert result.loc[0, status_col] == "Divergente"
    assert "endere" in result.loc[0, obs_col].lower()


def test_validar_registros_rejeita_credito_de_foto_como_nome():
    dados = pd.DataFrame(
        [
            {
                "UF": "BA",
                "Municipio/Capital": "Feira de Santana",
                "Cargo/Area": "Chefe de gabinete",
                "Orgao/Secretaria": "Gabinete/Prefeitura",
                "Status": "Parcial",
                "Nome": "Marcelo Magalhaes",
                "E-mail": "",
                "Telefone": "",
                "Celular/WhatsApp": "",
                "URL da fonte": "https://fonte.test/noticia",
            }
        ]
    )
    texto = "Chefe de Gabinete responde interinamente pela presidencia. Fotos: Marcelo Magalhaes"

    result = validar_registros(dados, lambda _url: (texto, "Encontrado", ""), max_linhas=0)

    status_col = next(c for c in result.columns if str(c).startswith("Status valida"))
    obs_col = next(c for c in result.columns if str(c).startswith("Observa"))
    assert result.loc[0, status_col] == "Divergente"
    assert "credito" in result.loc[0, obs_col].lower()


def test_validar_registros_sem_linhas_retorna_colunas_esperadas():
    dados = pd.DataFrame(
        [
            {
                "UF": "CE",
                "MunicÃ­pio/Capital": "Fortaleza",
                "Cargo/Ãrea": "Prefeito",
                "Status": "NÃ£o publicado",
                "Nome": "",
                "E-mail": "",
                "Telefone": "",
                "Celular/WhatsApp": "",
                "URL da fonte": "https://fortaleza.ce.gov.br/",
            }
        ]
    )

    result = validar_registros(dados, lambda _url: ("", "Encontrado", ""), max_linhas=0)

    assert result.empty
    assert any(str(column).startswith("Status valida") for column in result.columns)


def test_validar_registros_associa_telefone_por_digitos_no_bloco_da_categoria():
    dados = pd.DataFrame(
        [
            {
                "UF": "GO",
                "Município/Capital": "Pires do Rio",
                "Cargo/Área": "Chefe de gabinete",
                "Órgão/Secretaria": "Gabinete/Prefeitura",
                "Status": "Encontrado",
                "Nome": "Nédia Mazon",
                "E-mail": "gabinete@piresdorio.go.gov.br",
                "Telefone": "",
                "Celular/WhatsApp": "(64) 98440-0020",
                "URL da fonte": "https://piresdorio.go.gov.br/estrutura/gabinete-da-prefeito/",
            }
        ]
    )

    texto = """
    Chefia de Gabinete
    Responsável:
    Nédia Mazon
    Telefone:
    64 98440-0020
    E-mail:
    gabinete@piresdorio.go.gov.br
    """

    result = validar_registros(dados, lambda _url: (texto, "Encontrado", ""))

    assert result.loc[0, "Status validação"] == "Validado"


def test_validar_registros_associa_contato_ao_nome_publicado_da_secretaria():
    dados = pd.DataFrame(
        [
            {
                "UF": "RS",
                "Município/Capital": "Novo Hamburgo",
                "Cargo/Área": "Secretaria de Desenvolvimento Econômico",
                "Órgão/Secretaria": "Secretaria de Desenvolvimento Econômico",
                "Status": "Encontrado",
                "Nome": "Daiana de Leonco Monzon",
                "E-mail": "smdei@novohamburgo.rs.gov.br",
                "Telefone": "(51) 3097-9400",
                "Celular/WhatsApp": "",
                "URL da fonte": "https://www.novohamburgo.rs.gov.br/smdei",
            }
        ]
    )
    texto = """
    Desenvolvimento Economico e Inovacao
    A Secretaria de Desenvolvimento Economico e Inovacao fomenta negocios.
    Secretaria
    Daiana de Leonco Monzon
    Estrutura Organizacional
    Telefone
    :
    (51) 3097-9400
    E-mail
    :
    smdei@novohamburgo.rs.gov.br
    """

    result = validar_registros(dados, lambda _url: (texto, "Encontrado", ""), max_linhas=0)

    assert result.loc[0, "Status validação"] == "Validado"


def test_validar_registros_associa_nome_quebrado_em_linhas_consecutivas():
    dados = pd.DataFrame(
        [
            {
                "UF": "SP",
                "Município/Capital": "Santana de Parnaíba",
                "Cargo/Área": "Prefeito",
                "Órgão/Secretaria": "Gabinete/Prefeitura",
                "Status": "Encontrado",
                "Nome": "Elvis Leonardo Cezar",
                "E-mail": "",
                "Telefone": "(11) 4622-7500",
                "Celular/WhatsApp": "",
                "URL da fonte": "https://prefeitura.santanadeparnaiba.sp.gov.br/Plataforma/prefeito",
            }
        ]
    )
    texto = """
    Av. Marechal Mascarenhas de Moraes, 1283
    (11) 4622-7500
    Prefeito
    Elvis
    Leonardo
    Cezar
    Formado em Direito pela UNIP.
    """

    result = validar_registros(dados, lambda _url: (texto, "Encontrado", ""), max_linhas=0)

    assert result.loc[0, "Status validação"] == "Validado"
