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

COL_CARGO_ORGAO = "Cargo/\u00d3rg\u00e3o"


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
    assert contatos[0][COL_CARGO_ORGAO] == "Secretaria de Finanças/Fazenda"
    assert contatos[0]["Nome"] == "Maria Silva"
    assert contatos[0]["E-mail"] == "financas@cidade.gov.br"
    assert contatos[0]["Status"] == "Encontrado"


def test_contato_sem_cargo_vira_contato_geral_parcial():
    contatos = extrair_contatos_de_texto("Fale conosco: contato@cidade.gov.br", CARGOS, "https://cidade.gov.br")

    assert contatos[0][COL_CARGO_ORGAO] == "Contato geral"
    assert contatos[0]["Status"] == "Parcial"


def test_extrai_perfil_institucional_do_prefeito_sem_confundir_biografia():
    cargos = {
        "prefeito": ["prefeito", "prefeita"],
        "vice_prefeito": ["vice-prefeito", "vice prefeito"],
    }
    texto = """
    Prefeito
    Alysson Bestene Lins
    Prefeito

    Alysson Bestene Lins nasceu no dia 24 de junho de 1975, em Rio Branco - Acre.
    Foi eleito vice-prefeito nas eleicoes de 2024.
    Foi secretario Municipal de Educacao, de fevereiro de 2025 ate 04/04/2026
    Contatos:
    alysson.bestene@riobranco.ac.gov.br
    +55 (68) 3212-7336

    Ultimas noticias
    Prefeito Alysson Bestene acompanha obras no municipio
    """

    contatos = extrair_contatos_de_texto(texto, cargos, "https://www.riobranco.ac.gov.br/prefeito/")

    assert len(contatos) == 1
    assert contatos[0][COL_CARGO_ORGAO] == "Prefeito"
    assert contatos[0]["Nome"] == "Alysson Bestene Lins"
    assert contatos[0]["E-mail"] == "alysson.bestene@riobranco.ac.gov.br"
    assert contatos[0]["Telefone"] == "+55 (68) 3212-7336"
    assert contatos[0]["Status"] == "Encontrado"
    assert all(item["Nome"] != "Municipal de Educacao" for item in contatos)
    assert all(item[COL_CARGO_ORGAO] != "Vice-prefeito" for item in contatos)


def test_perfis_consecutivos_nao_vazam_contato_para_cargo_anterior():
    cargos = {
        "prefeito": ["prefeito"],
        "vice_prefeito": ["vice-prefeito", "vice prefeito"],
    }
    texto = """
    Prefeito
    Joao Silva
    Vice-Prefeito
    Maria Souza
    Contatos:
    maria@cidade.gov.br
    (11) 3333-4444
    """

    contatos = extrair_contatos_de_texto(texto, cargos, "https://cidade.gov.br/equipe")
    por_cargo = {item[COL_CARGO_ORGAO]: item for item in contatos}

    assert por_cargo["Prefeito"]["Nome"] == "Joao Silva"
    assert por_cargo["Prefeito"]["E-mail"] == ""
    assert por_cargo["Prefeito"]["Telefone"] == ""
    assert por_cargo["Prefeito"]["Status"] == "Parcial"
    assert por_cargo["Vice-prefeito"]["Nome"] == "Maria Souza"
    assert por_cargo["Vice-prefeito"]["E-mail"] == "maria@cidade.gov.br"
    assert por_cargo["Vice-prefeito"]["Telefone"] == "(11) 3333-4444"
    assert por_cargo["Vice-prefeito"]["Status"] == "Encontrado"


def test_prefeito_estruturado_nao_suprime_vice_prefeito_valido():
    cargos = {
        "prefeito": ["prefeito"],
        "vice_prefeito": ["vice-prefeito", "vice prefeito"],
    }
    texto = """
    Prefeito
    Joao Silva
    Contatos:
    prefeito@cidade.gov.br
    (11) 1111-1111

    Vice-Prefeito: Maria Souza
    E-mail: vice@cidade.gov.br
    Telefone: (11) 2222-2222
    """

    contatos = extrair_contatos_de_texto(texto, cargos, "https://cidade.gov.br/equipe")
    por_cargo = {item[COL_CARGO_ORGAO]: item for item in contatos}

    assert por_cargo["Prefeito"]["Nome"] == "Joao Silva"
    assert por_cargo["Prefeito"]["E-mail"] == "prefeito@cidade.gov.br"
    assert por_cargo["Vice-prefeito"]["Nome"] == "Maria Souza"
    assert por_cargo["Vice-prefeito"]["E-mail"] == "vice@cidade.gov.br"
    assert por_cargo["Vice-prefeito"]["Telefone"] == "(11) 2222-2222"


def test_cargo_executivo_diferente_nao_e_suprimido_por_telefone_compartilhado():
    cargos = {
        "prefeito": ["prefeito"],
        "vice_prefeito": ["vice-prefeito", "vice prefeito"],
    }
    texto = """
    Prefeito
    Joao Silva
    Contatos:
    prefeito@cidade.gov.br
    (11) 1111-1111

    Vice-Prefeito Maria Souza
    E-mail: vice@cidade.gov.br
    Telefone: (11) 1111-1111
    """

    contatos = extrair_contatos_de_texto(texto, cargos, "https://cidade.gov.br/equipe")
    por_cargo = {item[COL_CARGO_ORGAO]: item for item in contatos}

    assert por_cargo["Prefeito"]["Nome"] == "Joao Silva"
    assert por_cargo["Prefeito"]["E-mail"] == "prefeito@cidade.gov.br"
    assert por_cargo["Vice-prefeito"]["Nome"] == "Maria Souza"
    assert por_cargo["Vice-prefeito"]["E-mail"] == "vice@cidade.gov.br"
    assert por_cargo["Vice-prefeito"]["Telefone"] == "(11) 1111-1111"


def test_linha_em_branco_limita_janela_do_perfil_apos_contato():
    cargos = {"prefeito": ["prefeito"]}
    proximos_blocos = (
        ("Ouvidoria", "atendimento@cidade.gov.br", "(11) 9999-8888"),
        ("Secretaria Municipal de Saude", "saude@cidade.gov.br", "(11) 3333-4444"),
        ("Endereco\nRua Central, 100", "", "(11) 5555-6666"),
    )

    for titulo, email, telefone in proximos_blocos:
        linha_email = f"{email}\n" if email else ""
        texto = f"""
        Prefeito
        Joao Silva
        Contatos:
        prefeito@cidade.gov.br
        (11) 1111-1111

        {titulo}
        {linha_email}{telefone}
        """

        contatos = extrair_contatos_de_texto(texto, cargos, "https://cidade.gov.br/prefeito")
        prefeito = [item for item in contatos if item[COL_CARGO_ORGAO] == "Prefeito"][0]
        contatos_gerais = [item for item in contatos if item[COL_CARGO_ORGAO] == "Contato geral"]

        assert prefeito["Nome"] == "Joao Silva"
        assert prefeito["E-mail"] == "prefeito@cidade.gov.br"
        assert prefeito["Telefone"] == "(11) 1111-1111"
        assert telefone not in prefeito["Telefone"]
        if email:
            assert email not in prefeito["E-mail"]

        assert contatos_gerais
        assert telefone in contatos_gerais[0]["Telefone"]
        if email:
            assert email in contatos_gerais[0]["E-mail"]


def test_bloco_executivo_sem_nome_preserva_cargo_especifico():
    cargos = {"prefeito": ["prefeito"]}
    textos = (
        """
        Gabinete do Prefeito
        prefeito@cidade.gov.br
        (11) 1111-1111
        """,
        """
        Prefeito - Gabinete
        prefeito@cidade.gov.br
        (11) 1111-1111
        """,
    )

    for texto in textos:
        contatos = extrair_contatos_de_texto(texto, cargos, "https://cidade.gov.br/gabinete")
        prefeito = [item for item in contatos if item[COL_CARGO_ORGAO] == "Prefeito"][0]

        assert prefeito["Nome"] == ""
        assert prefeito["E-mail"] == "prefeito@cidade.gov.br"
        assert prefeito["Telefone"] == "(11) 1111-1111"
        assert prefeito["Status"] == "Encontrado"


def test_contato_geral_preserva_email_novo_com_telefone_compartilhado():
    cargos = {"prefeito": ["prefeito"]}
    texto = """
    Prefeito
    Joao Silva
    Contatos:
    prefeito@cidade.gov.br
    (11) 1111-1111

    Ouvidoria
    atendimento@cidade.gov.br
    (11) 1111-1111
    """

    contatos = extrair_contatos_de_texto(texto, cargos, "https://cidade.gov.br/prefeito")
    prefeito = [item for item in contatos if item[COL_CARGO_ORGAO] == "Prefeito"][0]
    contatos_gerais = [item for item in contatos if item[COL_CARGO_ORGAO] == "Contato geral"]

    assert prefeito["E-mail"] == "prefeito@cidade.gov.br"
    assert contatos_gerais
    assert contatos_gerais[0]["E-mail"] == "atendimento@cidade.gov.br"
    assert contatos_gerais[0]["Telefone"] == "(11) 1111-1111"


def test_linha_em_branco_limita_janela_do_perfil_sem_contato():
    cargos = {"prefeito": ["prefeito"]}
    proximos_blocos = (
        ("Ouvidoria", "atendimento@cidade.gov.br", "(11) 9999-8888"),
        ("Secretaria Municipal de Saude", "saude@cidade.gov.br", "(11) 3333-4444"),
    )

    for titulo, email, telefone in proximos_blocos:
        texto = f"""
        Prefeito
        Joao Silva

        {titulo}
        {email}
        {telefone}
        """

        contatos = extrair_contatos_de_texto(texto, cargos, "https://cidade.gov.br/prefeito")
        prefeito = [item for item in contatos if item[COL_CARGO_ORGAO] == "Prefeito"][0]
        contatos_gerais = [item for item in contatos if item[COL_CARGO_ORGAO] == "Contato geral"]

        assert prefeito["Nome"] == "Joao Silva"
        assert prefeito["E-mail"] == ""
        assert prefeito["Telefone"] == ""
        assert prefeito["Status"] == "Parcial"
        assert contatos_gerais
        assert contatos_gerais[0]["E-mail"] == email
        assert contatos_gerais[0]["Telefone"] == telefone


def test_contato_da_ouvidoria_nao_continua_perfil_anterior():
    cargos = {"prefeito": ["prefeito"]}
    textos = (
        """
        Prefeito
        Joao Silva

        Contato da Ouvidoria
        atendimento@cidade.gov.br
        (11) 2222-2222
        """,
        """
        Prefeito
        Joao Silva

        Contato Ouvidoria
        atendimento@cidade.gov.br
        (11) 2222-2222
        """,
        """
        Prefeito
        Joao Silva

        Contato - Ouvidoria
        atendimento@cidade.gov.br
        (11) 2222-2222
        """,
        """
        Prefeito
        Joao Silva

        Contato: Ouvidoria
        atendimento@cidade.gov.br
        (11) 2222-2222
        """,
        """
        Prefeito
        Joao Silva

        Contatos - Ouvidoria
        atendimento@cidade.gov.br
        (11) 2222-2222
        """,
        """
        Prefeito
        Joao Silva

        Contato \u2013 Ouvidoria
        atendimento@cidade.gov.br
        (11) 2222-2222
        """,
    )

    for texto in textos:
        contatos = extrair_contatos_de_texto(texto, cargos, "https://cidade.gov.br/prefeito")
        prefeito = [item for item in contatos if item[COL_CARGO_ORGAO] == "Prefeito"][0]
        contatos_gerais = [item for item in contatos if item[COL_CARGO_ORGAO] == "Contato geral"]

        assert prefeito["Nome"] == "Joao Silva"
        assert prefeito["E-mail"] == ""
        assert prefeito["Telefone"] == ""
        assert contatos_gerais
        assert contatos_gerais[0]["E-mail"] == "atendimento@cidade.gov.br"
        assert contatos_gerais[0]["Telefone"] == "(11) 2222-2222"


def test_linha_em_branco_permite_continuacao_explicita_de_contato():
    cargos = {"prefeito": ["prefeito"]}
    texto = """
    Prefeito
    Joao Silva

    Contatos:
    prefeito@cidade.gov.br
    (11) 1111-1111
    """

    contatos = extrair_contatos_de_texto(texto, cargos, "https://cidade.gov.br/prefeito")
    prefeito = [item for item in contatos if item[COL_CARGO_ORGAO] == "Prefeito"][0]

    assert prefeito["Nome"] == "Joao Silva"
    assert prefeito["E-mail"] == "prefeito@cidade.gov.br"
    assert prefeito["Telefone"] == "(11) 1111-1111"
    assert prefeito["Status"] == "Encontrado"


def test_linha_em_branco_permite_rotulo_de_contato_apos_contato_existente():
    cargos = {"prefeito": ["prefeito"]}
    texto = """
    Prefeito
    Joao Silva
    E-mail: prefeito@cidade.gov.br

    Telefone: (11) 1111-1111
    """

    contatos = extrair_contatos_de_texto(texto, cargos, "https://cidade.gov.br/prefeito")
    prefeito = [item for item in contatos if item[COL_CARGO_ORGAO] == "Prefeito"][0]

    assert prefeito["Nome"] == "Joao Silva"
    assert prefeito["E-mail"] == "prefeito@cidade.gov.br"
    assert prefeito["Telefone"] == "(11) 1111-1111"
    assert prefeito["Status"] == "Encontrado"
    assert all(item[COL_CARGO_ORGAO] != "Contato geral" for item in contatos)


def test_manchete_com_prefeito_nome_nao_vira_perfil():
    cargos = {"prefeito": ["prefeito"]}
    texto = """
    Prefeito Joao Silva acompanha obras no bairro
    Contato:
    atendimento@cidade.gov.br
    (11) 2222-2222
    """

    contatos = extrair_contatos_de_texto(texto, cargos, "https://cidade.gov.br/noticias")

    assert all(item[COL_CARGO_ORGAO] != "Prefeito" for item in contatos)
    assert contatos[0][COL_CARGO_ORGAO] == "Contato geral"
    assert contatos[0]["E-mail"] == "atendimento@cidade.gov.br"
    assert contatos[0]["Telefone"] == "(11) 2222-2222"


def test_busca_de_nome_nao_atravessa_cargo_diferente():
    cargos = {
        "prefeito": ["prefeito"],
        "vice_prefeito": ["vice-prefeito", "vice prefeito"],
    }
    texto = """
    Prefeito
    Vice-Prefeito
    Maria Souza
    Contatos:
    maria@cidade.gov.br
    (11) 3333-4444
    """

    contatos = extrair_contatos_de_texto(texto, cargos, "https://cidade.gov.br/equipe")
    por_cargo = {item[COL_CARGO_ORGAO]: item for item in contatos}

    assert "Prefeito" not in por_cargo
    assert por_cargo["Vice-prefeito"]["Nome"] == "Maria Souza"
    assert por_cargo["Vice-prefeito"]["E-mail"] == "maria@cidade.gov.br"
    assert por_cargo["Vice-prefeito"]["Telefone"] == "(11) 3333-4444"


def test_linha_cargo_nome_fecha_janela_do_perfil_anterior():
    cargos = {
        "prefeito": ["prefeito"],
        "chefe_gabinete": ["chefe de gabinete", "gabinete"],
    }
    linhas_cargo_nome = (
        "Chefe de gabinete: Maria Silva",
        "Chefe de gabinete:Maria Silva",
        "Chefe de gabinete - Maria Silva",
        "Chefe de gabinete-Maria Silva",
        "Chefe de gabinete \u2013 Maria Silva",
        "Chefe de gabinete\u2013Maria Silva",
        "Chefe de gabinete \u2014 Maria Silva",
        "Chefe de gabinete\u2014Maria Silva",
    )
    for linha_cargo_nome in linhas_cargo_nome:
        texto = f"""
        Prefeito
        Alysson Bestene Lins
        Prefeito
        Contatos:
        prefeito@cidade.gov.br
        (11) 1111-1111

        {linha_cargo_nome}
        E-mail: gabinete@cidade.gov.br
        Telefone: (11) 2222-2222
        """

        contatos = extrair_contatos_de_texto(texto, cargos, "https://cidade.gov.br/prefeito")
        prefeito = [item for item in contatos if item[COL_CARGO_ORGAO] == "Prefeito"][0]
        chefe = [item for item in contatos if item[COL_CARGO_ORGAO] == "Chefe de gabinete"][0]

        assert prefeito["Nome"] == "Alysson Bestene Lins"
        assert prefeito["E-mail"] == "prefeito@cidade.gov.br"
        assert prefeito["Telefone"] == "(11) 1111-1111"
        assert "gabinete@cidade.gov.br" not in prefeito["E-mail"]
        assert "(11) 2222-2222" not in prefeito["Telefone"]
        assert chefe["Nome"] == "Maria Silva"
        assert chefe["E-mail"] == "gabinete@cidade.gov.br"
        assert chefe["Telefone"] == "(11) 2222-2222"


def test_rejeita_menu_como_nome_de_autoridade():
    texto = "Prefeito Secretarias\nGestao Administrativa\nCidade Autarquias\n"

    assert extrair_contatos_de_texto(texto, CARGOS, "https://cidade.gov.br") == []
