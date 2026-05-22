from src.extrair_contatos import (
    detectar_cargos,
    extrair_celulares,
    extrair_contatos_de_texto,
    extrair_emails,
    extrair_telefones,
)


CARGOS = {
    "prefeito": ["prefeito", "prefeita"],
    "financas_fazenda": ["finanças", "fazenda", "secretaria de finanças"],
}


def test_extrai_emails_telefones_e_celulares():
    texto = "Contato: GABINETE@EXEMPLO.GOV.BR, (11) 3333-3333 e +55 11 99999-9999."

    assert extrair_emails(texto) == ["gabinete@exemplo.gov.br"]
    assert "(11) 3333-3333" in extrair_telefones(texto)
    assert "+55 11 99999-9999" in extrair_celulares(texto)


def test_detecta_cargo_e_associa_contato_no_mesmo_bloco():
    texto = """
    Secretaria de Finanças: Maria Silva
    E-mail: financas@cidade.gov.br
    Telefone: 11 3333-3333
    """

    contatos = extrair_contatos_de_texto(texto, CARGOS, "https://cidade.gov.br/financas")

    assert contatos
    assert contatos[0]["Cargo/Órgão"] == "Secretaria de Finanças/Fazenda"
    assert contatos[0]["Nome"] == "Maria Silva"
    assert contatos[0]["E-mail"] == "financas@cidade.gov.br"
    assert contatos[0]["Status"] == "Encontrado"


def test_contato_sem_cargo_vira_contato_geral_parcial():
    contatos = extrair_contatos_de_texto("Fale conosco: contato@cidade.gov.br", CARGOS, "https://cidade.gov.br")

    assert contatos[0]["Cargo/Órgão"] == "Contato geral"
    assert contatos[0]["Status"] == "Parcial"

