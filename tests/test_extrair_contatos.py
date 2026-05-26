from src.extrair_contatos import (
    carregar_cargos,
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


def test_intervalo_de_anos_nao_vira_telefone():
    assert extrair_telefones("Planejamento 2021-2024 e protocolos 1603-2021") == []


def test_cep_numerico_nao_vira_telefone():
    telefones = extrair_telefones("Endereco: Rua Central, 69, Centro, 36980000. Telefone: 3344-2006")

    assert "36980000" not in telefones
    assert "3344-2006" in telefones


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


def test_gabinete_generico_nao_vira_chefe_de_gabinete():
    cargos = {"chefe_gabinete": ["chefe de gabinete", "gabinete"]}
    texto = """
    Gabinete
    Minha Casa
    Prestacao de Contas
    """

    assert extrair_contatos_de_texto(texto, cargos, "https://cidade.gov.br") == []


def test_desenvolvimento_generico_em_descricao_nao_vira_secretaria_alvo():
    cargos = {"desenvolvimento": ["secretaria de desenvolvimento", "desenvolvimento"]}
    texto = """
    Secretaria Municipal de Agropecuaria
    Desenvolvimento da Agricultura:
    A secretaria trabalha no estimulo ao desenvolvimento da agricultura familiar.
    Conheca o Secretario
    Eracides Caetano de Souza
    Contatos:
    eracides.souza@cidade.gov.br
    (68) 3212-7463
    """

    contatos = extrair_contatos_de_texto(texto, cargos, "https://cidade.gov.br/seagro")

    assert all(item[COL_CARGO_ORGAO] != "Secretaria de Desenvolvimento" for item in contatos)


def test_perfil_conheca_secretario_associa_cargo_contatos():
    cargos = {
        "financas_fazenda": [
            "financas",
            "secretaria de financas",
            "secretaria municipal de financas",
            "secretario municipal de financas",
        ]
    }
    texto = """
    Secretaria Municipal de Financas
    Conheca o Secretario
    Wilson Jose das Chagas Sena Leite
    Secretario Municipal de Financas
    Contatos:
    gabinete.secfinancas@cidade.gov.br
    wilson.leite@cidade.gov.br
    +55 (68) 3212-7424
    Endereco:
    Rua Central, 100
    """

    contatos = extrair_contatos_de_texto(texto, cargos, "https://cidade.gov.br/sefin")

    assert len(contatos) == 1
    assert contatos[0][COL_CARGO_ORGAO] == "Secretaria de Finanças/Fazenda"
    assert contatos[0]["Nome"] == "Wilson Jose das Chagas Sena Leite"
    assert "wilson.leite@cidade.gov.br" in contatos[0]["E-mail"]
    assert contatos[0]["Telefone"] == "+55 (68) 3212-7424"
    assert contatos[0]["Status"] == "Encontrado"


def test_desenvolvimento_economico_nao_duplica_desenvolvimento_generico():
    cargos = {
        "desenvolvimento_economico": ["desenvolvimento economico"],
        "desenvolvimento": ["secretaria municipal de desenvolvimento"],
    }
    cargos_detectados = detectar_cargos("Secretaria Municipal de Desenvolvimento Economico", cargos)

    assert cargos_detectados == ["Secretaria de Desenvolvimento Econômico"]


def test_email_nao_inclui_rotulo_telefone_colado():
    assert extrair_emails("sec.esportes@cidade.gov.brTelefone: (11) 3333-3333") == ["sec.esportes@cidade.gov.br"]


def test_lista_secretarias_extrai_nome_sem_inventar_contato():
    cargos = {
        "desenvolvimento_economico": [
            "desenvolvimento economico",
            "secretaria municipal de desenvolvimento economico",
        ]
    }
    texto = """
    Secretarias
    SDTI
    Secretaria Municipal de Desenvolvimento Economico, Turismo, Tecnologia e Inovacao
    Secretario:
    Coronel Ezequiel de Oliveira Bino
    Endereco:
    Rua Goldwasser Santos
    """

    contatos = extrair_contatos_de_texto(texto, cargos, "https://cidade.gov.br/secretarias")

    assert len(contatos) == 1
    assert contatos[0][COL_CARGO_ORGAO] == "Secretaria de Desenvolvimento Econômico"
    assert contatos[0]["Nome"] == "Coronel Ezequiel de Oliveira Bino"
    assert contatos[0]["Status"] == "Parcial"
    assert contatos[0]["E-mail"] == ""


def test_lista_secretarias_nao_usa_descricao_como_titulo_nem_mistura_blocos():
    cargos = {
        "desenvolvimento_economico": ["desenvolvimento economico"],
        "desenvolvimento": ["secretaria municipal de desenvolvimento social", "desenvolvimento social"],
        "planejamento": ["planejamento"],
    }
    texto = """
    SECRETARIA MUNICIPAL DE AGRICULTURA
    Secretario: Joscival Bispo Rodrigues
    Telefone: (73) 98101-6419
    E-mail: seagri.itabela@gmail.com
    A Secretaria Municipal de Agricultura promove o desenvolvimento economico e social do meio rural.
    SECRETARIA MUNICIPAL DE SAUDE
    Secretaria: Wadla Silva de Andrade Casiano
    Telefone: (73) 99923-1716
    E-mail: secsaude@yahoo.com.br
    SECRETARIA MUNICIPAL DE DESENVOLVIMENTO SOCIAL, TRABALHO E HABITACAO
    Secretaria: Maria Vania Costa Santana Ferreira
    Telefone: (73) 98117-3514
    E-mail: sedesth@gmail.com
    SECRETARIA MUNICIPAL DE INTEGRACAO INSTITUCIONAL
    Secretaria: Emilia Francisca Goncalves de Oliveira
    Telefone: (73) 98171-5313
    E-mail: planejamentoegestao.itabela@gmail.com
    """

    contatos = extrair_contatos_de_texto(texto, cargos, "https://cidade.gov.br/secretarias")
    por_cargo = {item[COL_CARGO_ORGAO]: item for item in contatos}

    assert "Secretaria de Desenvolvimento Econômico" not in por_cargo
    assert por_cargo["Secretaria de Desenvolvimento"]["Nome"] == "Maria Vania Costa Santana Ferreira"
    assert por_cargo["Secretaria de Desenvolvimento"]["E-mail"] == "sedesth@gmail.com"
    assert por_cargo["Secretaria de Desenvolvimento"]["Celular/WhatsApp"] == "(73) 98117-3514"


def test_rotulo_secretario_parenteses_extrai_nome_correto():
    cargos = {
        "planejamento": [
            "planejamento",
            "planejameto",
            "secretaria municipal de planejameto",
        ]
    }
    texto = """
    Secretaria Municipal de Planejameto
    Secretario(a): Willian da Silva Reis Ferreira Filho (Makito)
    planejamento@cidade.gov.br
    (43) 3911-3023
    Secretarias
    Secretaria Municipal de Financas
    Noticias relacionadas
    """

    contatos = extrair_contatos_de_texto(texto, cargos, "https://cidade.gov.br/secretariaView/?id=18")

    assert contatos[0][COL_CARGO_ORGAO] == "Secretaria de Planejamento"
    assert contatos[0]["Nome"] == "Willian da Silva Reis Ferreira Filho"
    assert contatos[0]["E-mail"] == "planejamento@cidade.gov.br"


def test_pagina_secretaria_singular_com_diretorio_nao_associa_lista_a_cargo():
    cargos = {
        "desenvolvimento_economico": ["desenvolvimento economico"],
        "planejamento": ["planejamento"],
    }
    texto = """
    Secretarias
    Secretaria de Protecao e Desenvolvimento Social
    sec.social@cidade.gov.br
    (51) 3451-8000
    Planejamento
    sec.planejamento@cidade.gov.br
    (51) 3450-4066
    """

    contatos = extrair_contatos_de_texto(texto, cargos, "https://cidade.gov.br/secretaria/")

    assert contatos
    assert {item[COL_CARGO_ORGAO] for item in contatos} == {"Contato geral"}


def test_telefones_uteis_nao_vazam_para_vice_prefeito():
    cargos = {
        "prefeito": ["prefeito", "prefeita"],
        "vice_prefeito": ["vice-prefeito", "vice prefeito"],
    }
    texto = """
    Vice-Prefeito
    Daniel Balke
    O vice-prefeito de Ferraz de Vasconcelos, Daniel Balke, e contador.
    Em 2020, foi eleito vice-prefeito junto com a prefeita Priscila.
    AGENDAMENTO DE CONSULTA ON-LINE
    Telefones uteis
    Junta Militar
    (11) 4678-8970
    Defesa Civil
    (11) 95310-2217
    """

    contatos = extrair_contatos_de_texto(texto, cargos, "https://cidade.gov.br/vice-prefeito")
    vice = [item for item in contatos if item[COL_CARGO_ORGAO] == "Vice-prefeito"][0]

    assert vice["Nome"] == "Daniel Balke"
    assert vice["Telefone"] == ""
    assert vice["Celular/WhatsApp"] == ""
    assert vice["Status"] == "Parcial"
    assert all(item[COL_CARGO_ORGAO] != "Prefeito" for item in contatos)


def test_manchete_com_subsecretaria_nao_vira_nome():
    cargos = {"desenvolvimento_economico": ["subsecretaria de esportes e juventude", "desenvolvimento economico"]}
    texto = """
    Prefeitura divulga percurso oficial
    Saude
    Vitoria Pereira
    Subsecretaria de Esportes e Juventude
    """

    contatos = extrair_contatos_de_texto(texto, cargos, "https://cidade.gov.br/")

    assert contatos == []


def test_ultimas_noticias_nao_criam_contato_de_prefeito():
    cargos = {"prefeito": ["prefeito"]}
    texto = """
    Prefeito
    Joao Silva
    Contatos:
    prefeito@cidade.gov.br
    (11) 1111-1111

    Ultimas noticias
    Prefeito Joao Silva acompanha obras
    atendimento@cidade.gov.br
    (11) 2222-2222
    """

    contatos = extrair_contatos_de_texto(texto, cargos, "https://cidade.gov.br/prefeito")
    prefeito = [item for item in contatos if item[COL_CARGO_ORGAO] == "Prefeito"][0]

    assert prefeito["E-mail"] == "prefeito@cidade.gov.br"
    assert "(11) 2222-2222" not in prefeito["Telefone"]


def test_pagina_de_contatos_com_muitos_contatos_nao_associa_cargo_especifico():
    cargos = {"prefeito": ["prefeito"], "planejamento": ["secretaria de planejamento"]}
    texto = """
    Contatos
    Prefeito
    Secretaria de Planejamento
    secretaria1@cidade.gov.br
    secretaria2@cidade.gov.br
    secretaria3@cidade.gov.br
    secretaria4@cidade.gov.br
    (11) 1111-1111
    (11) 2222-2222
    """

    contatos = extrair_contatos_de_texto(texto, cargos, "https://cidade.gov.br/contatos")

    assert contatos
    assert {item[COL_CARGO_ORGAO] for item in contatos} == {"Contato geral"}


def test_secretaria_com_responsavel_nao_puxa_contato_de_rodape():
    cargos = {"financas_fazenda": ["secretaria da fazenda", "fazenda"]}
    texto = """
    Secretaria da Fazenda
    Responsavel
    Agnaldo de Souza Schuab
    E-mail
    fazenda@lajinha.mg.gov.br
    Telefone
    (33) 3344-2006
    Endereco
    Rua Central, Centro, 36980000
    Informacoes
    Telefone: (33) 9999-9999
    Email:
    contato@lajinha.mg.gov.br
    Ouvidoria:
    ouvidoria@lajinha.mg.gov.br
    """

    contatos = extrair_contatos_de_texto(texto, cargos, "https://cidade.gov.br/prefeitura/secretaria-da-fazenda")

    assert len(contatos) == 1
    assert contatos[0][COL_CARGO_ORGAO].endswith("/Fazenda")
    assert contatos[0]["Nome"] == "Agnaldo de Souza Schuab"
    assert contatos[0]["E-mail"] == "fazenda@lajinha.mg.gov.br"
    assert contatos[0]["Telefone"] == "(33) 3344-2006"
    assert "contato@lajinha.mg.gov.br" not in contatos[0]["E-mail"]
    assert "36980000" not in contatos[0]["Telefone"]


def test_secretaria_nao_puxa_telefones_de_diretorias_subordinadas():
    cargos = {"planejamento": ["secretaria de planejamento"]}
    texto = """
    Secretaria de Planejamento e Gestao
    Secretario - Frederic Henrique Magalhaes
    Telefone:
    (31) 3688-1400
    E-mail:
    planejamento@cidade.gov.br
    DIRETORIA DE INOVACAO TECNOLOGICA
    Diretor
    Telefone:
    (31) 3688-1478
    E-mail:
    diretoria@cidade.gov.br
    """

    contatos = extrair_contatos_de_texto(texto, cargos, "https://cidade.gov.br/prefeitura/secretarias/planejamento-e-gestao")

    assert len(contatos) == 1
    assert contatos[0]["Telefone"] == "(31) 3688-1400"
    assert contatos[0]["E-mail"] == "planejamento@cidade.gov.br"
    assert "(31) 3688-1478" not in contatos[0]["Telefone"]
    assert "diretoria@cidade.gov.br" not in contatos[0]["E-mail"]


def test_endereco_com_nome_e_mencao_descritiva_ao_prefeito_nao_cria_prefeito():
    cargos = {"prefeito": ["prefeito"]}
    texto = """
    Secretaria de Cultura e Turismo
    Responsavel
    Maria Luiza Azine Vitor
    E-mail
    cultura@cidade.gov.br
    Telefone
    (33) 3344-2796
    Endereco
    Av. Dr. Rubens Boechat de Oliveira, Centro, Cidade, MG, Brasil, 36980000
    Descricao
    Prestar assessoramento direto e indireto ao Prefeito, em assuntos relativos a Esporte, Cultura e Turismo.
    """

    contatos = extrair_contatos_de_texto(texto, cargos, "https://cidade.gov.br/prefeitura/secretaria-de-cultura")

    assert all(item[COL_CARGO_ORGAO] != "Prefeito" for item in contatos)


def test_pires_do_rio_rotulos_nao_viram_autoridades():
    cargos = {
        "prefeito": ["prefeito", "prefeita", "gabinete da prefeita"],
        "financas_fazenda": ["financas", "fazenda", "secretaria municipal de financas"],
        "desenvolvimento": ["secretaria de desenvolvimento", "desenvolvimento"],
    }
    texto = """
    Gabinete da Prefeita
    Centro Horário
    Base Jurídica
    gabinete@piresdorio.go.gov.br
    (64) 98440-0020

    Continue Lendo Chefe Nédia Mazon Sobre
    Termos de Posse

    Secretaria de Obras e Desenvolvimento Urbano
    Divisão Divisão
    (64) 98440-0071

    Secretaria Municipal de Finanças
    Base Jurídica
    """

    contatos = extrair_contatos_de_texto(texto, cargos, "https://piresdorio.go.gov.br/estrutura/gabinete-da-prefeito/")

    assert all(item["Nome"] not in {"Centro Horário", "Base Jurídica", "Termos de Posse", "Divisão Divisão"} for item in contatos)
    assert all("Continue Lendo" not in item["Nome"] for item in contatos)
    assert all(item[COL_CARGO_ORGAO] != "Prefeito" for item in contatos if item["Nome"])


def test_credito_de_foto_em_noticia_nao_vira_autoridade():
    cargos = {"chefe_gabinete": ["chefe de gabinete", "chefia de gabinete", "gabinete"]}
    texto = """
    Chefe de Gabinete responde interinamente pela presidencia
    Fotos: Marcelo Magalhaes
    A noticia informa que o chefe de gabinete participou da agenda.
    """

    contatos = extrair_contatos_de_texto(texto, cargos, "https://cidade.gov.br/secom/cont_not.asp?idn=1")

    assert all(item["Nome"] != "Fotos: Marcelo Magalhaes" for item in contatos)
    assert all(item["Nome"] != "Marcelo Magalhaes" for item in contatos)


def test_rotulo_institucional_ultima_nao_vira_autoridade():
    cargos = {"vice_prefeito": ["vice-prefeito", "vice prefeito"]}
    texto = """
    Vice-prefeito
    Institucional Ultima
    Atualizacao
    Noticias
    """

    contatos = extrair_contatos_de_texto(texto, cargos, "https://cidade.gov.br/institucional")

    assert all(item["Nome"] != "Institucional Ultima" for item in contatos)


def test_rotulo_sessao_transmissao_nao_vira_autoridade():
    cargos = {"prefeito": ["prefeito", "prefeita"]}
    texto = """
    Prefeito
    Sessao Transmissao
    Portal oficial
    """

    contatos = extrair_contatos_de_texto(texto, cargos, "https://cidade.gov.br/transmissao")

    assert all(item["Nome"] != "Sessao Transmissao" for item in contatos)


def test_rotulo_verba_indenizatoria_nao_vira_autoridade():
    cargos = {"prefeito": ["prefeito", "prefeita"]}
    texto = """
    Prefeito
    Valores Cotas Verba Indenizatoria Ativ
    """

    contatos = extrair_contatos_de_texto(texto, cargos, "https://cidade.gov.br/homepage")

    assert all(item["Nome"] != "Valores Cotas Verba Indenizatoria Ativ" for item in contatos)


def test_pires_do_rio_mescla_nome_e_contato_do_prefeito_no_mesmo_orgao():
    cargos = {"prefeito": ["prefeito", "prefeita", "gabinete da prefeita"]}
    texto = """
    Gabinete da Prefeita
    Hugo Sérgio Batista
    Prefeito

    Gabinete da Prefeita
    Centro Horário
    comunicacao@piresdorio.go.gov.br
    (64) 98440-0043
    """

    contatos = extrair_contatos_de_texto(texto, cargos, "https://piresdorio.go.gov.br/estrutura/gabinete-da-prefeito/")
    prefeito = [item for item in contatos if item[COL_CARGO_ORGAO] == "Prefeito"][0]

    assert prefeito["Nome"] == "Hugo Sérgio Batista"
    assert prefeito["E-mail"] == ""
    assert prefeito["Celular/WhatsApp"] == ""
    assert prefeito["Status"] == "Parcial"


def test_equipe_governo_bauru_nao_vaza_contatos_entre_perfis():
    cargos = {
        "prefeito": ["prefeito", "prefeita"],
        "vice_prefeito": ["vice-prefeito", "vice prefeito"],
        "chefe_gabinete": ["chefe de gabinete", "gabinete"],
        "desenvolvimento_economico": ["desenvolvimento economico", "secretaria de desenvolvimento economico"],
        "financas_fazenda": ["fazenda", "secretaria da fazenda"],
    }
    texto = """
    Prefeita
    Suéllen Silva Rosim
    Fone:
    (014) 3235-1000

    Vice-Prefeito
    Orlando Costa Dias
    Fone:
    (014) 3235-1000

    Gabinete
    Leonardo Marcari
    Fone:
    (014) 3235-1000

    Secretaria de Desenvolvimento Econômico, Turismo e Inovação
    Carlos Agra
    Fone:
    (014) 3227-7819

    Secretaria da Fazenda
    Everson Demarchi
    Fone:
    (014) 3235-1496

    Secretaria de Educação
    Pessoa Fora do Escopo
    Fone:
    (014) 3235-1314
    """

    contatos = extrair_contatos_de_texto(texto, cargos, "https://www2.bauru.sp.gov.br/equipe_governo.aspx")
    por_cargo = {item[COL_CARGO_ORGAO]: item for item in contatos}

    assert por_cargo["Prefeito"]["Nome"] == "Suéllen Silva Rosim"
    assert por_cargo["Vice-prefeito"]["Nome"] == "Orlando Costa Dias"
    assert por_cargo["Vice-prefeito"]["Telefone"] == "3235-1000"
    assert por_cargo["Chefe de gabinete"]["Nome"] == "Leonardo Marcari"
    assert por_cargo["Secretaria de Desenvolvimento Econômico"]["Nome"] == "Carlos Agra"
    assert por_cargo["Secretaria de Desenvolvimento Econômico"]["Telefone"] == "3227-7819"
    assert por_cargo["Secretaria de Finanças/Fazenda"]["Nome"] == "Everson Demarchi"
    assert "(014) 3235-1314" not in por_cargo["Secretaria de Finanças/Fazenda"]["Telefone"]


def test_area_de_desenvolvimento_com_secretaria_em_linhas_separadas_extrai_titular():
    cargos = carregar_cargos()
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

    contatos = extrair_contatos_de_texto(texto, cargos, "https://www.novohamburgo.rs.gov.br/smdei")
    desenvolvimento = [item for item in contatos if item[COL_CARGO_ORGAO] == "Secretaria de Desenvolvimento Econômico"][0]

    assert desenvolvimento["Nome"] == "Daiana de Leonco Monzon"
    assert desenvolvimento["E-mail"] == "smdei@novohamburgo.rs.gov.br"
    assert desenvolvimento["Telefone"] == "(51) 3097-9400"


def test_prefeito_em_linhas_quebradas_nao_usa_nome_de_esposa_da_biografia():
    cargos = carregar_cargos()
    texto = """
    Prefeito
    Elvis
    Leonardo
    Cezar
    Formado em Direito, sempre com o apoio de sua esposa Selma
    Cezar e do seu filho, Caio.
    Elvis Cezar nasceu em Carapicuiba e foi eleito prefeito.
    """

    contatos = extrair_contatos_de_texto(texto, cargos, "https://prefeitura.santanadeparnaiba.sp.gov.br/Plataforma/prefeito")
    nomes = {item["Nome"] for item in contatos if item[COL_CARGO_ORGAO] == "Prefeito"}

    assert "Elvis Leonardo Cezar" in nomes
    assert "Selma Cezar" not in nomes


def test_chefe_de_gabinete_subordinado_em_biografia_nao_vira_chefe_municipal():
    cargos = carregar_cargos()
    texto = """
    Secretaria Municipal de Controle Geral
    Secretario
    Rafael Martins Gomes
    Biografia
    Rafael Martins Gomes atuou como Chefe de Gabinete do Procurador-Geral.
    Contato
    E-mail:
    semconger@novaiguacu.rj.gov.br
    """

    contatos = extrair_contatos_de_texto(texto, cargos, "https://www.novaiguacu.rj.gov.br/semconger/")

    assert all(item[COL_CARGO_ORGAO] != "Chefe de gabinete" for item in contatos)


def test_pires_do_rio_chefia_de_gabinete_usa_responsavel_do_bloco():
    cargos = {
        "chefe_gabinete": ["chefe de gabinete", "chefia de gabinete", "gabinete"],
    }
    texto = """
    Chefia de Gabinete
    Responsável:
    Nédia Mazon
    Telefone:
    64 98440-0020
    E-mail:
    gabinete@piresdorio.go.gov.br

    Superintendência de Comunicação, Tecnologia e Inovação
    Responsável:
    Glênio José Martins Filho
    Telefone:
    64 98440-0043
    E-mail:
    comunicacao@piresdorio.go.gov.br
    """

    contatos = extrair_contatos_de_texto(texto, cargos, "https://piresdorio.go.gov.br/estrutura/gabinete-da-prefeito/")
    chefe = [item for item in contatos if item[COL_CARGO_ORGAO] == "Chefe de gabinete"][0]

    assert chefe["Nome"] == "Nédia Mazon"
    assert chefe["E-mail"] == "gabinete@piresdorio.go.gov.br"
    assert chefe["Celular/WhatsApp"] == "64 98440-0020"
    assert "98440-0043" not in chefe["Celular/WhatsApp"]
def test_concessao_de_areas_nao_vira_agencia_de_desenvolvimento():
    cargos = carregar_cargos()
    texto = """
    Secretaria de Desenvolvimento Municipal
    Concessão de Áreas
    Saiba como solicitar concessão de áreas públicas para instalação de empresas.
    """

    contatos = extrair_contatos_de_texto(texto, cargos, "https://www2.bauru.sp.gov.br/servicos.aspx?m=5")

    assert all(item[COL_CARGO_ORGAO] != "Agência/Sala de Desenvolvimento" for item in contatos)


def test_visualizar_pdf_nao_vira_nome_de_responsavel():
    cargos = {"financas_fazenda": ["fazenda", "secretaria de fazenda"]}
    texto = """
    Secretaria Municipal de Fazenda
    Visualizar PDF
    Estrutura Organizacional
    """

    contatos = extrair_contatos_de_texto(texto, cargos, "https://portal.io.org.br/ba/fazenda/estrutura-organizacional")

    assert all(item["Nome"] != "Visualizar PDF" for item in contatos)


def test_acesso_rapido_nao_vira_nome_de_autoridade():
    cargos = {"prefeito": ["prefeito", "prefeita"]}
    texto = """
    Prefeito
    Acesso Rápido
    Secretarias
    """

    contatos = extrair_contatos_de_texto(texto, cargos, "https://www.colatina.es.gov.br/")

    assert all(item["Nome"] != "Acesso Rápido" for item in contatos)


def test_aplicativo_digital_nao_vira_nome_de_autoridade():
    cargos = {"prefeito": ["prefeito", "prefeita"]}
    texto = """
    Prefeito
    Colatina Digital
    Serviços Online
    """

    contatos = extrair_contatos_de_texto(texto, cargos, "https://www.colatina.es.gov.br/")

    assert all(item["Nome"] != "Colatina Digital" for item in contatos)


def test_menu_servicos_nao_vira_nome_de_autoridade():
    cargos = {"prefeito": ["prefeito", "prefeita"]}
    texto = """
    Prefeito
    Serviços Ponto Eletrônico Processos Seletivos Licitações
    """

    contatos = extrair_contatos_de_texto(texto, cargos, "https://www.colatina.es.gov.br/")

    assert all(item["Nome"] != "Serviços Ponto Eletrônico Processos Seletivos Licitações" for item in contatos)


def test_menu_calendario_nao_vira_nome_de_autoridade():
    cargos = {"prefeito": ["prefeito", "prefeita"]}
    texto = """
    Prefeito
    Calendário de Eventos Agenda
    """

    contatos = extrair_contatos_de_texto(texto, cargos, "https://www.colatina.es.gov.br/")

    assert all(item["Nome"] != "Calendário de Eventos Agenda" for item in contatos)


def test_rotulos_de_portal_nao_viram_nome_de_autoridade():
    cargos = {
        "vice_prefeito": ["vice-prefeito", "vice prefeito"],
        "planejamento": ["planejamento"],
        "prefeito": ["prefeito", "prefeita"],
        "chefe_gabinete": ["chefe de gabinete"],
        "financas_fazenda": ["finanças", "fazenda"],
    }
    texto = """
    Vice-prefeito
    Legislação Denuncia

    Planejamento
    Sistema de Recursos Humanos

    Vice-prefeito
    Corrupção Login

    Vice-prefeito
    Estrutura Organizacional Nosso

    Vice-prefeito
    Estrutura Organizacional

    Planejamento
    Sistema Único

    Planejamento
    Clique Aqui

    Vice-prefeito
    Chefia Chefe

    Prefeito
    Infraestrutura Prefeitura

    Chefe de gabinete
    Imprensa Oficial Art

    Chefe de gabinete
    Técnica Legislativa Art

    Vice-prefeito
    Constituição Estadual

    Finanças
    Negócios Públicos

    Prefeito
    Ouvidoria e Atendimento

    Prefeito
    Serviço de Informações

    Prefeito
    Órgão de Imprensa
    """

    contatos = extrair_contatos_de_texto(texto, cargos, "https://ecoporanga.es.gov.br/")

    assert all(item["Nome"] != "Legislação Denuncia" for item in contatos)
    assert all(item["Nome"] != "Sistema de Recursos Humanos" for item in contatos)
    assert all(item["Nome"] != "Corrupção Login" for item in contatos)
    assert all(item["Nome"] != "Estrutura Organizacional Nosso" for item in contatos)
    assert all(item["Nome"] != "Estrutura Organizacional" for item in contatos)
    assert all(item["Nome"] != "Sistema Único" for item in contatos)
    assert all(item["Nome"] != "Clique Aqui" for item in contatos)
    assert all(item["Nome"] != "Chefia Chefe" for item in contatos)
    assert all(item["Nome"] != "Infraestrutura Prefeitura" for item in contatos)
    assert all(item["Nome"] != "Imprensa Oficial Art" for item in contatos)
    assert all(item["Nome"] != "Técnica Legislativa Art" for item in contatos)
    assert all(item["Nome"] != "Constituição Estadual" for item in contatos)
    assert all(item["Nome"] != "Negócios Públicos" for item in contatos)
    assert all(item["Nome"] != "Ouvidoria e Atendimento" for item in contatos)
    assert all(item["Nome"] != "Serviço de Informações" for item in contatos)
    assert all(item["Nome"] != "Órgão de Imprensa" for item in contatos)


def test_rotulos_institucionais_de_sites_reais_nao_viram_nome():
    cargos = {
        "prefeito": ["prefeito", "prefeita"],
        "vice_prefeito": ["vice-prefeito", "vice prefeito"],
        "chefe_gabinete": ["chefe de gabinete", "gabinete"],
        "financas_fazenda": ["financas", "fazenda"],
        "agencia_desenvolvimento": ["agencia de desenvolvimento", "sala do empreendedor"],
    }
    texto = """
    Prefeito
    Prefeitura de Jatai

    Prefeito
    Ordem dos Advogados

    Vice-prefeito
    Indice de Artigos Resultado

    Prefeito
    Indiretas Todas

    Prefeito
    Piraquara Conheca

    Prefeito
    Nossa Historia Desde

    Prefeito
    Tia Angela

    Vice-prefeito
    Estancia de Socorro

    Chefe de gabinete
    Programa de Integridade

    Financas
    Coordenadoria de Tributacao e Arrecadacao Mobiliarias

    Agencia de Desenvolvimento
    Certidao Negativa de Debitos

    Sala do Empreendedor
    Programa Transformar Tramandai

    Sala do Empreendedor
    Via Rapida Empresa

    Prefeito
    Regimento Interno

    Prefeito
    Quem Somos

    Prefeito
    Emprega Santiago

    Vice-prefeito
    Rotary Club

    Financas
    Anexo III

    Agencia de Desenvolvimento
    Parceria SEBRAE

    Prefeito
    Creche Escola

    Prefeito
    Leis Complementares

    Prefeito
    Oficina Festival

    Prefeito
    Seguro Desemprego

    Prefeito
    Antecedentes Criminais

    Chefe de gabinete
    Linha Direta

    Prefeito
    Situacao de Emergencia

    Vice-prefeito
    Edificio Torre Center

    Vice-prefeito
    Secretarios e Diretores

    Prefeito
    Divida Ativa

    Prefeito
    Forcas Armadas

    Vice-prefeito
    Direito do Consumidor

    Chefe de gabinete
    Em Construcao

    Prefeito
    SECAO II

    Prefeito
    Paulo Afonso

    Vice-prefeito
    Disciplinas Pedagogicas

    Prefeito
    Agendas Disponiveis

    Prefeito
    Assessorias Especiais

    Vice-prefeito
    Pagina Inicial

    Prefeito
    Codigo Nacional

    Planejamento
    Coordenacao Governamental

    Agencia de Desenvolvimento
    Solicitacoes Ambientais

    Desenvolvimento
    Assistencia e Vigilancia

    Prefeito
    Sustentabilidade e Governanca

    Desenvolvimento
    Vagas Disponiveis

    Prefeito
    America Latina

    Prefeito
    Castro Primeira

    Chefe de gabinete
    Atribuicoes Analisar

    Prefeito
    Externos Castramovel

    Vice-prefeito
    Termo de Us

    Prefeito
    Mobilidade Urbana Eduardo Bueno

    Prefeito
    Tupa Milton Carlos

    Prefeito
    Ribeirao Preto Local

    Prefeito
    Assuntos Juridicos

    Prefeito
    Lauro de Freitas Anterior Proximo Se
    """

    contatos = extrair_contatos_de_texto(texto, cargos, "https://cidade.gov.br/")
    nomes = {item["Nome"] for item in contatos}

    assert "Prefeitura de Jatai" not in nomes
    assert "Ordem dos Advogados" not in nomes
    assert "Indice de Artigos Resultado" not in nomes
    assert "Indiretas Todas" not in nomes
    assert "Piraquara Conheca" not in nomes
    assert "Nossa Historia Desde" not in nomes
    assert "Tia Angela" not in nomes
    assert "Estancia de Socorro" not in nomes
    assert "Programa de Integridade" not in nomes
    assert "Coordenadoria de Tributacao e Arrecadacao Mobiliarias" not in nomes
    assert "Certidao Negativa de Debitos" not in nomes
    assert "Programa Transformar Tramandai" not in nomes
    assert "Via Rapida Empresa" not in nomes
    assert "Regimento Interno" not in nomes
    assert "Quem Somos" not in nomes
    assert "Emprega Santiago" not in nomes
    assert "Rotary Club" not in nomes
    assert "Anexo III" not in nomes
    assert "Parceria SEBRAE" not in nomes
    assert "Creche Escola" not in nomes
    assert "Leis Complementares" not in nomes
    assert "Oficina Festival" not in nomes
    assert "Seguro Desemprego" not in nomes
    assert "Antecedentes Criminais" not in nomes
    assert "Linha Direta" not in nomes
    assert "Situacao de Emergencia" not in nomes
    assert "Edificio Torre Center" not in nomes
    assert "Secretarios e Diretores" not in nomes
    assert "Divida Ativa" not in nomes
    assert "Forcas Armadas" not in nomes
    assert "Direito do Consumidor" not in nomes
    assert "Em Construcao" not in nomes
    assert "SECAO II" not in nomes
    assert "Paulo Afonso" not in nomes
    assert "Disciplinas Pedagogicas" not in nomes
    assert "Agendas Disponiveis" not in nomes
    assert "Assessorias Especiais" not in nomes
    assert "Pagina Inicial" not in nomes
    assert "Codigo Nacional" not in nomes
    assert "Coordenacao Governamental" not in nomes
    assert "Solicitacoes Ambientais" not in nomes
    assert "Assistencia e Vigilancia" not in nomes
    assert "Sustentabilidade e Governanca" not in nomes
    assert "Vagas Disponiveis" not in nomes
    assert "America Latina" not in nomes
    assert "Castro Primeira" not in nomes
    assert "Atribuicoes Analisar" not in nomes
    assert "Externos Castramovel" not in nomes
    assert "Termo de Us" not in nomes
    assert "Mobilidade Urbana Eduardo Bueno" not in nomes
    assert "Tupa Milton Carlos" not in nomes
    assert "Ribeirao Preto Local" not in nomes
    assert "Assuntos Juridicos" not in nomes
    assert "Lauro de Freitas Anterior Proximo Se" not in nomes


def test_sobrenome_homem_nao_e_rejeitado_como_home():
    cargos = {"vice_prefeito": ["vice-prefeito", "vice prefeito"]}
    texto = """
    Vice-Prefeito
    Ludovico Jose Homem Marcari
    """

    contatos = extrair_contatos_de_texto(texto, cargos, "https://cidade.gov.br/vice")

    assert any(item["Nome"] == "Ludovico Jose Homem Marcari" for item in contatos)


def test_contas_do_prefeito_nao_vira_fonte_de_perfil_do_prefeito():
    cargos = {"prefeito": ["prefeito", "prefeita"]}
    texto = """
    Prefeito
    Indiretas Todas
    """

    contatos = extrair_contatos_de_texto(texto, cargos, "https://portal.londrina.pr.gov.br/contas-do-prefeito")

    assert all(item[COL_CARGO_ORGAO] != "Prefeito" for item in contatos)


def test_pagina_historica_de_prefeitos_nao_vira_prefeito_atual():
    cargos = {"prefeito": ["prefeito", "prefeita"]}
    texto = """
    Prefeito
    Ennio Brancalion
    """

    contatos = extrair_contatos_de_texto(texto, cargos, "https://www.maua.sp.gov.br/Cidade/Prefeitos")

    assert all(item[COL_CARGO_ORGAO] != "Prefeito" for item in contatos)


def test_pagina_escolar_nao_vira_fonte_de_cargo_executivo():
    cargos = {"prefeito": ["prefeito", "prefeita"]}
    texto = """
    Prefeito
    Tia Angela
    """

    contatos = extrair_contatos_de_texto(texto, cargos, "https://www.piraquara.pr.gov.br/cmei-tia-angela-4921")

    assert all(item[COL_CARGO_ORGAO] != "Prefeito" for item in contatos)


def test_pagina_de_unidade_ou_departamento_nao_vira_executivo():
    cargos = {"vice_prefeito": ["vice-prefeito", "vice prefeito"], "prefeito": ["prefeito", "prefeita"]}

    unidade = extrair_contatos_de_texto(
        "Vice-prefeito\nPaula Louzada Martins Breve",
        cargos,
        "https://www.anchieta.es.gov.br/unidades/7",
    )
    departamento = extrair_contatos_de_texto(
        "Prefeito\nMobilidade Urbana Eduardo Bueno",
        cargos,
        "https://www.francodarocha.sp.gov.br/mobilidadeurbana/",
    )

    assert all(item[COL_CARGO_ORGAO] not in {"Prefeito", "Vice-prefeito"} for item in unidade + departamento)


def test_pdf_e_pagina_de_manaus_so_de_prefeito_nao_viram_vice():
    cargos = {"vice_prefeito": ["vice-prefeito", "vice prefeito"]}
    texto = """
    Vice-prefeito
    David Almeida
    """

    pagina_prefeito = extrair_contatos_de_texto(texto, cargos, "https://www.manaus.am.gov.br/prefeitura/prefeito/")
    pdf = extrair_contatos_de_texto(texto, cargos, "https://cidade.gov.br/site/download?type=txt&fileName=governo.pdf")

    assert all(item[COL_CARGO_ORGAO] != "Vice-prefeito" for item in pagina_prefeito)
    assert all(item[COL_CARGO_ORGAO] != "Vice-prefeito" for item in pdf)


def test_responsavel_inline_nao_inclui_rotulo_no_nome():
    cargos = {"prefeito": ["prefeito", "prefeita"]}
    texto = """
    Gabinete da Prefeita
    Responsável Sebastião Viana
    """

    contatos = extrair_contatos_de_texto(texto, cargos, "https://cidade.gov.br/gabinete")

    assert all(item["Nome"] != "Responsável Sebastião Viana" for item in contatos)
    assert any(item["Nome"] == "Sebastião Viana" for item in contatos)


def test_nome_em_linha_de_endereco_nao_vira_prefeito():
    cargos = {"prefeito": ["prefeito", "prefeita"]}
    texto = """
    Prefeito
    Endereço: Av. Deufino Meireles, 100
    Telefone: (61) 3614-2573
    """

    contatos = extrair_contatos_de_texto(texto, cargos, "https://cidade.gov.br/prefeito")

    assert all(item["Nome"] != "Deufino Meireles" for item in contatos)


def test_responsavel_com_telefone_na_mesma_linha_nao_gruda_rotulo_contato():
    cargos = {"prefeito": ["prefeito", "prefeita"]}
    texto = """
    Gabinete do Prefeito Responsável: Roberto Pereira dos Santos Telefones: 61 3614-2573
    Email: gabineteprefeito@novogama.go.gov.br
    """

    contatos = extrair_contatos_de_texto(texto, cargos, "https://cidade.gov.br/gabinete")

    assert any(item["Nome"] == "Roberto Pereira dos Santos" for item in contatos)
    assert all(item["Nome"] != "Roberto Pereira dos Santos Telefones" for item in contatos)


def test_nome_antes_de_cargo_na_mesma_linha_nao_gruda_chefe():
    cargos = {"chefe_gabinete": ["chefe de gabinete", "gabinete"]}
    texto = """
    Gabinete Kelen Cristina Aires de Melo Cury Chefe de Gabinete
    Telefone (64) 3441-5070
    E-mail gabinete@catalao.go.gov.br
    """

    contatos = extrair_contatos_de_texto(texto, cargos, "https://cidade.gov.br/gabinete")

    assert any(item["Nome"] == "Kelen Cristina Aires de Melo Cury" for item in contatos)
    assert all(item["Nome"] != "Melo Cury Chefe" for item in contatos)


def test_nome_antes_de_vice_na_mesma_linha_nao_gruda_cargo():
    cargos = {"vice_prefeito": ["vice-prefeito", "vice prefeito"]}
    texto = """
    Nelson Martins Fayad Vice-Prefeito
    """

    contatos = extrair_contatos_de_texto(texto, cargos, "https://cidade.gov.br/vice-prefeito")

    assert any(item["Nome"] == "Nelson Martins Fayad" for item in contatos)
    assert all(item["Nome"] != "Nelson Martins Fayad Vice" for item in contatos)


def test_nome_com_vice_isolado_no_fim_eh_aparado():
    cargos = {"vice_prefeito": ["vice-prefeito", "vice prefeito"]}
    texto = """
    Vice Prefeito
    Nelson Martins Fayad Vice
    """

    contatos = extrair_contatos_de_texto(texto, cargos, "https://cidade.gov.br/vice-prefeito")

    assert any(item["Nome"] == "Nelson Martins Fayad" for item in contatos)
    assert all(item["Nome"] != "Nelson Martins Fayad Vice" for item in contatos)


def test_fale_conosco_ouvidoria_nao_vira_prefeito():
    cargos = {"prefeito": ["prefeito", "prefeita"]}
    texto = """
    Gabinete do Prefeito
    Fale conosco
    Ouvidoria e Atendimento
    Responsável ouvidoria
    Hilário Freitas Guimarães
    62 99898-5281
    ouvidoria@itapaci.go.gov.br
    """

    contatos = extrair_contatos_de_texto(texto, cargos, "https://cidade.gov.br/fale-conosco/")

    assert all(item[COL_CARGO_ORGAO] != "Prefeito" for item in contatos)


def test_autoridade_administrativa_eh_responsavel_oficial():
    cargos = {"prefeito": ["prefeito", "prefeita", "gabinete do prefeito"]}
    texto = """
    GABPREF - Gabinete do Prefeito
    Autoridade administrativa
    Paulo Celso Cola Pereira
    Localização
    Avenida Felicindo Lopes, 238
    E-mail: gabinete@piuma.es.gov.br
    Telefone: (28) 3520-6500
    """

    contatos = extrair_contatos_de_texto(texto, cargos, "https://www.piuma.es.gov.br/portal/carta-de-servico/orgao/4/gabpref-gabinete-do-prefeito")
    prefeito = [item for item in contatos if item[COL_CARGO_ORGAO] == "Prefeito"][0]

    assert prefeito["Nome"] == "Paulo Celso Cola Pereira"
    assert prefeito["Nome"] != "Felicindo Lopes"


def test_vice_nao_herda_telefone_do_gabinete_do_prefeito():
    cargos = {"vice_prefeito": ["vice-prefeita", "vice-prefeito"], "prefeito": ["prefeito", "prefeita"]}
    texto = """
    Prefeito:
    Marcus Azevedo Batista
    Vice-Prefeita:
    Raquel da Silva Rocha
    E-mail(s):
    prefeito@saomateus.es.gov.br
    viceprefeita@saomateus.es.gov.br
    Telefones:
    Gabinete (27) 3195-0120
    """

    contatos = extrair_contatos_de_texto(texto, cargos, "https://www.saomateus.es.gov.br/prefeito")
    vice = [item for item in contatos if item[COL_CARGO_ORGAO] == "Vice-prefeito"][0]

    assert vice["Nome"] == "Raquel da Silva Rocha"
    assert vice["E-mail"] == "viceprefeita@saomateus.es.gov.br"
    assert vice["Telefone"] == ""


def test_distritos_industriais_nao_vira_agencia_de_desenvolvimento():
    cargos = carregar_cargos()
    texto = """
    Secretaria de Desenvolvimento Econômico
    Distritos Industriais
    Informações sobre áreas, empresas instaladas e concessões.
    """

    contatos = extrair_contatos_de_texto(texto, cargos, "https://www2.bauru.sp.gov.br/sedecon/")

    assert all(item[COL_CARGO_ORGAO] != "Agência/Sala de Desenvolvimento" for item in contatos)


def test_rotulos_de_portal_mg_nao_viram_nome_de_autoridade():
    cargos = {
        "prefeito": ["prefeito", "prefeita"],
        "vice_prefeito": ["vice-prefeito", "vice prefeito"],
        "chefe_gabinete": ["chefe de gabinete", "gabinete"],
        "planejamento": ["planejamento"],
        "agencia_desenvolvimento": ["agencia de desenvolvimento", "sala do empreendedor"],
    }
    texto = """
    Prefeito
    Nome Completo
    prefeito@cidade.gov.br

    Vice-prefeito
    Principal Vice

    Chefe de gabinete
    Instituto Federal

    Planejamento
    Avaliar Servico Baixar

    Agencia de Desenvolvimento
    COM VOCE
    """

    contatos = extrair_contatos_de_texto(texto, cargos, "https://cidade.gov.br/")
    nomes = {item["Nome"] for item in contatos}

    assert "Nome Completo" not in nomes
    assert "Principal Vice" not in nomes
    assert "Instituto Federal" not in nomes
    assert "Avaliar Servico Baixar" not in nomes
    assert "COM VOCE" not in nomes


def test_sufixos_de_portal_mg_sao_aparados_do_nome():
    cargos = {
        "prefeito": ["prefeito", "prefeita"],
        "vice_prefeito": ["vice-prefeito", "vice prefeito"],
        "planejamento": ["secretaria de planejamento"],
    }
    texto = """
    Prefeito
    Introducao Danilo Mendes Rodrigues

    Vice Prefeito
    Fernando Marangoni Partido

    Secretaria de Planejamento
    Katia Silva Goncalves Acoes
    """

    contatos = extrair_contatos_de_texto(texto, cargos, "https://cidade.gov.br/equipe")
    nomes = {item["Nome"] for item in contatos}

    assert "Danilo Mendes Rodrigues" in nomes
    assert "Fernando Marangoni" in nomes
    assert "Katia Silva Goncalves" in nomes
    assert "Introducao Danilo Mendes Rodrigues" not in nomes
    assert "Fernando Marangoni Partido" not in nomes
    assert "Katia Silva Goncalves Acoes" not in nomes


def test_contatos_de_conselho_nao_vazam_para_secretaria():
    cargos = {"desenvolvimento": ["desenvolvimento social", "secretaria de desenvolvimento social"]}
    texto = """
    Secretaria de Desenvolvimento Social
    Secretaria: Blandina Oliveira
    E-mail: smds@cidade.gov.br
    Telefone: (38) 99161-0120

    Conselho Tutelar
    E-mail: tutelar@cidade.gov.br
    Telefone: (38) 99161-0107
    """

    contatos = extrair_contatos_de_texto(texto, cargos, "https://cidade.gov.br/social")
    social = [item for item in contatos if item[COL_CARGO_ORGAO] == "Secretaria de Desenvolvimento"][0]

    assert social["Nome"] == "Blandina Oliveira"
    assert social["E-mail"] == "smds@cidade.gov.br"
    assert "tutelar@cidade.gov.br" not in social["E-mail"]
    assert "(38) 99161-0107" not in social["Celular/WhatsApp"]


def test_contato_de_endereco_nao_gruda_em_prefeito_publicado():
    cargos = {"prefeito": ["prefeito", "prefeita"]}
    texto = """
    Prefeito
    Joao Silva
    Biografia do prefeito.

    Endereco
    Praca Central, 100
    E-mail: contato@cidade.gov.br
    Telefone: (11) 2222-3333
    """

    contatos = extrair_contatos_de_texto(texto, cargos, "https://cidade.gov.br/prefeito")
    prefeito = [item for item in contatos if item[COL_CARGO_ORGAO] == "Prefeito"][0]

    assert prefeito["Nome"] == "Joao Silva"
    assert prefeito["E-mail"] == ""
    assert prefeito["Telefone"] == ""
    assert prefeito["Status"] == "Parcial"
