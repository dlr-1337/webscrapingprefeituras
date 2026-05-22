from src.utils import (
    clean_url,
    estado_from_uf,
    is_capital,
    normalize_key,
    parse_bool,
    parse_int,
    same_domain,
    slugify_municipio,
    uf_from_estado,
)


def test_normalizacao_de_chaves_slug_e_parse_de_numeros():
    assert normalize_key("Nome do Município") == "nome_do_municipio"
    assert slugify_municipio("São João d'Aliança") == "saojoaodalianca"
    assert parse_int("1.234.567 habitantes") == 1234567
    assert parse_int("") == 0


def test_parse_bool_aceita_variacoes_positivas_e_negativas():
    assert parse_bool(True) is True
    assert parse_bool("sim") is True
    assert parse_bool("capital") is True
    assert parse_bool("não") is False
    assert parse_bool(None) is False


def test_uf_estado_e_capital_comparam_sem_acentos():
    assert uf_from_estado("Sao Paulo") == "SP"
    assert estado_from_uf("df") == "Distrito Federal"
    assert is_capital("Brasilia", "DF") is True
    assert is_capital("Campinas", "SP") is False


def test_clean_url_normaliza_e_same_domain_aceita_subdominios():
    assert clean_url(" Cidade.SP.GOV.BR/contato?x=1#frag ") == "https://cidade.sp.gov.br/contato?x=1"
    assert clean_url(None) == ""
    assert clean_url("nan") == ""
    assert same_domain("https://transparencia.cidade.sp.gov.br/page", "https://cidade.sp.gov.br/") is True
    assert same_domain("https://outra.sp.gov.br/", "https://cidade.sp.gov.br/") is False
