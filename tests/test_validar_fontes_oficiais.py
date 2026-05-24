import pandas as pd

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

    assert result.loc[0, "Status validação"] == "Validado"
    assert result.loc[0, "Campos conferidos"] == 4


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
