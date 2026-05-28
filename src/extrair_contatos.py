from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

from src.coletar_paginas import PaginaColetada
from src.utils import load_yaml, normalize_for_search, project_path, strip_accents


EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PHONE_PATTERN = re.compile(
    r"(?<!\d)(?:\+?55\s*)?(?:\(?([1-9]{2})\)?\s*)?(9?\d{4})[\s.\-]?(\d{4})(?!\d)"
)
NAME_PATTERN = re.compile(
    r"\b([A-ZÁÀÂÃÉÈÊÍÌÓÒÔÕÚÙÇ][a-záàâãéèêíìóòôõúùç']+"
    r"(?:\s+(?:de|da|do|dos|das|e))?"
    r"(?:\s+[A-ZÁÀÂÃÉÈÊÍÌÓÒÔÕÚÙÇ][a-záàâãéèêíìóòôõúùç']+){1,5})\b"
)

CARGO_LABELS = {
    "prefeito": "Prefeito",
    "vice_prefeito": "Vice-prefeito",
    "chefe_gabinete": "Chefe de gabinete",
    "desenvolvimento_economico": "Secretaria de Desenvolvimento Econômico",
    "desenvolvimento": "Secretaria de Desenvolvimento",
    "financas_fazenda": "Secretaria de Finanças/Fazenda",
    "planejamento": "Secretaria de Planejamento",
    "agencia_desenvolvimento": "Agência/Sala de Desenvolvimento",
}

NOME_EXCLUDE = {
    "prefeitura municipal",
    "secretaria municipal",
    "desenvolvimento economico",
    "sala do empreendedor",
    "iss online",
    "concursos e selecoes",
    "fale conosco",
    "portal da transparencia",
    "painel de facilidades",
    "praca",
    "diario oficial",
    "acessar o conteudo",
    "acesso rapido",
    "prefeito secretarias",
    "secretarias autarquias",
    "orgaos municipais",
    "gestao administrativa",
    "cidade autarquias",
    "gabinete militar",
    "municipal de educacao",
    "ultimas noticias",
    "endereco",
    "contatos",
    "ano mes semana dia boletim informativo",
    "assistencia social",
    "base juridica",
    "casa civil",
    "ciencia e tecnologia",
    "calendario de eventos agenda",
    "comunidade mariele franco",
    "colatina digital",
    "competencias e atribuicoes",
    "concessao de areas",
    "corrupcao login",
    "controle ambiental economia solidaria",
    "constituicao federal",
    "constituicao estadual",
    "diretoria de financas publicas coordenador",
    "estrada do aviario",
    "estrutura organizacional nosso",
    "horario de atendimento",
    "infraestrutura prefeitura",
    "imprensa oficial art",
    "licenciamento e regularizacao",
    "legislacao denuncia",
    "meio ambiente cultura",
    "ministerio da mulher",
    "minha casa",
    "municipio de acrelandia assessor parlamentar",
    "negocios publicos",
    "nossa historia desde",
    "obras publicas",
    "orgao de imprensa",
    "ouvidoria e atendimento",
    "parque chico mendes novo mirante",
    "poder executivo",
    "poderes publicos",
    "prestacao de contas",
    "procuradoria geral",
    "projeto de lei complementar",
    "ramal menino jesus prefeitura",
    "rio branco",
    "rua alvorada",
    "rua rui barbosa",
    "segundo andar",
    "seguranca publica",
    "servico de informacoes",
    "servicos ponto eletronico processos seletivos licitacoes",
    "sistema de recursos humanos",
    "sistema unico",
    "saude de jussara opcao",
    "superintendencia executiva",
    "trabalho coordenadoria",
    "valores cotas verba indenizatoria",
    "planejameto noticias",
    "continue lendo",
    "visualizar pdf",
    "termos de posse",
    "tia angela",
    "chefia chefe",
    "cidadao empresa turista",
    "clique aqui",
    "tecnica legislativa art",
    "divisao divisao",
    "distritos industriais",
    "patrulha agricola rural",
    "sessao transmissao",
    "nome completo",
    "acre alagoas amazonas amapa bahia ceara",
    "assessoria tecnica especial",
    "avaliar servico baixar",
    "associacao",
    "com voce",
    "facebook tweet",
    "links uteis",
    "manutencao e serv",
    "parcialmente nublado max",
    "principal vice",
    "santa vitoria",
    "santos dumont",
    "sao lourenco",
    "minas gerais mato grosso",
    "reforma agraria departamento",
    "postagens anteriores edicao",
    "controladoria geral",
    "informacao radar",
    "pontos de referencia",
    "sul mato grosso para paraiba pernambuco",
    "eduardo rodrigues claudia sales",
    "protecao social especial",
    "processo seletivo simplificado",
    "estudo do empreendedorismo",
    "planejamento e orcamento",
    "planejamento e projetos politica",
    "administracao publicado",
    "administracao publica",
    "governo e planejamento",
    "governo de condeuba",
    "governo de itapaci",
    "mulheres responsa",
    "advogado e empresario",
    "esporte e lazer",
    "capela mortuaria",
    "abertura de mei",
    "aquicultura e pesca",
    "alta complexidade",
    "antecedentes criminais",
    "anexo iii",
    "anexo viii",
    "assessor de apoio legislativo",
    "assessora especial",
    "assessoria de comunicacao",
    "assessoria de convenios",
    "categorias de paginas dinamicas",
    "certidao negativa de debitos",
    "coordenadoria de tributacao e arrecadacao mobiliarias",
    "dama utilizamos",
    "estancia de socorro",
    "forma de acompanhamento",
    "governou louveira",
    "imprimir corrigir",
    "imprimir fechar categoria",
    "indiretas todas",
    "indice de artigos resultado",
    "galeria de fotos",
    "galeria de prefeitos",
    "mapa do site covid",
    "beto araujo",
    "certidao estadual",
    "canta cerrado",
    "campo bom",
    "cascavel norte",
    "conselheiros tutelares",
    "constituicoes feder",
    "creche escola",
    "divida ativa",
    "edificio torre center",
    "pesquisar confirmacao",
    "politica de privacidade",
    "ordem dos advogados",
    "piraquara conheca",
    "programa de integridade",
    "programa primeiros passos",
    "programa transformar",
    "programas sociais",
    "publicacao ou veto fluxo",
    "funcionamento trajetoria",
    "emprega santiago",
    "estagiarios abril",
    "frederico westphalen",
    "fomento parana",
    "jogos escolares",
    "junta militar",
    "forcas armadas",
    "junimar salvador borges",
    "leis complementares",
    "linha direta",
    "lutar unidos",
    "parceria sebrae",
    "perguntas frequentes",
    "pela pasta",
    "quem somos",
    "regimento interno",
    "retrospectiva anual",
    "rotary club",
    "seguro desemprego",
    "secretarios e diretores",
    "situacao de emergencia",
    "agendas disponiveis",
    "anterior proximo",
    "america latina",
    "assuntos juridicos",
    "atribuicoes analisar",
    "areia branca",
    "assistencia e vigilancia",
    "assessorias especiais",
    "castro primeira",
    "codigo de posturas",
    "codigo nacional",
    "coordenacao governamental",
    "direito do consumidor",
    "direito publico",
    "disciplinas pedagogicas",
    "em construcao",
    "externos castramovel",
    "expansao industrial e portuaria",
    "gerente de esportes",
    "mobilidade urbana",
    "mobilidade urbana eduardo bueno",
    "pagina inicial",
    "paulo afonso",
    "projeto rosa amiga",
    "sao francisco",
    "sao paulo",
    "secao de habilitacao",
    "secao ii",
    "seguranca cidada",
    "solicitacoes ambientais",
    "sustentabilidade e governanca",
    "termo de us",
    "tupa milton carlos",
    "universidade sao francisco",
    "vagas disponiveis",
    "ribeirao preto local",
    "transloc transportes",
    "unidades executivas",
    "via rapida empresa",
    "concordar e fechar",
    "aceitar cookies",
    "preferencias de cookies",
    "politica de privacidade",
    "selo ouro",
    "analise de uso",
    "olhe preco",
    "sub menus",
    "accessibility toolbar",
    "legislatura periodo",
    "marketing e jornalismo",
    "polo de bebidas",
    "amargosa top",
    "partido socialista brasileiro",
    "movimento democratico brasileiro",
    "composicao da coligacao",
    "insatisfeito regular",
    "satisfeito muito",
    "quadra poliesportiva",
    "atividades ludicas",
    "censo escolar",
}

NOME_TOKEN_EXCLUDE = {
    "acessar",
    "acesso",
    "covid",
    "dama",
    "dados",
    "chefe",
    "fluxo",
    "funcionamento",
    "interpretacao",
    "accessibility",
    "cookies",
    "cookie",
    "legislatura",
    "mapa",
    "marketing",
    "menus",
    "regional",
    "publicacao",
    "selo",
    "site",
    "subchefe",
    "toolbar",
    "trajetoria",
    "utilizamos",
    "veto",
    "data",
    "grosso",
    "ir",
    "mato",
    "menu",
    "abertura",
    "administracao",
    "assessor",
    "assessoria",
    "capela",
    "certidao",
    "cidadania",
    "biografia",
    "curriculo",
    "especial",
    "esporte",
    "lazer",
    "mei",
    "mortuaria",
    "orcamento",
    "pecuaria",
    "planejamento",
    "politica",
    "processo",
    "projetos",
    "protecao",
    "publica",
    "publicado",
    "simplificado",
    "para",
    "paraiba",
    "pernambuco",
    "sul",
    "violao",
    "acessibilidade",
    "adjunto",
    "agraria",
    "anteriores",
    "controladoria",
    "completo",
    "consulta",
    "edicao",
    "fone",
    "geral",
    "governo",
    "informacao",
    "listagem",
    "mais",
    "medicamentos",
    "postagens",
    "pontos",
    "referencia",
    "referencias",
    "reforma",
    "secr",
    "sede",
    "veja",
    "whastsapp",
    "agricultura",
    "alagoas",
    "analises",
    "avaliar",
    "acompanhamento",
    "apoio",
    "aquicultura",
    "arrecadacao",
    "assessora",
    "baixar",
    "camara",
    "clinicas",
    "cachaca",
    "comercio",
    "conheca",
    "conselho",
    "conservacao",
    "defesa",
    "diretor",
    "debitos",
    "drogas",
    "economico",
    "emprego",
    "feira",
    "fiscal",
    "fisioterapia",
    "instituto",
    "lugares",
    "livre",
    "ltda",
    "mobiliarias",
    "max",
    "nublado",
    "parcialmente",
    "patrimonio",
    "pelo",
    "pesca",
    "pesquisar",
    "plano",
    "plurianual",
    "primeiros",
    "roteiro",
    "saber",
    "seletivo",
    "serrana",
    "passos",
    "social",
    "superintendente",
    "turismo",
    "unidade",
    "velha",
    "vereadores",
    "voce",
    "agricola",
    "administrativa",
    "autarquias",
    "ambiental",
    "andar",
    "ano",
    "art",
    "atendimento",
    "autor",
    "autoria",
    "atualizacao",
    "atualizado",
    "avenida",
    "advogado",
    "advogados",
    "aviario",
    "bairro",
    "base",
    "branco",
    "calendario",
    "categorias",
    "chefia",
    "cidadao",
    "cidade",
    "clique",
    "casa",
    "centro",
    "ciencia",
    "civil",
    "complementar",
    "competencias",
    "concessao",
    "areas",
    "aqui",
    "comunidade",
    "contato",
    "contatos",
    "conteudo",
    "convenios",
    "cotas",
    "contas",
    "controle",
    "coordenadoria",
    "corrupcao",
    "continue",
    "constituicao",
    "cultura",
    "dia",
    "denuncia",
    "delegacia",
    "departamento",
    "despesas",
    "deputada",
    "deputado",
    "destaque",
    "destaques",
    "digital",
    "dinamicas",
    "diminuir",
    "direto",
    "diario",
    "diretoria",
    "educacao",
    "email",
    "endereco",
    "endere",
    "empresa",
    "empresario",
    "estrada",
    "estancia",
    "estado",
    "estadual",
    "estrutura",
    "eventos",
    "executivo",
    "federal",
    "financas",
    "foto",
    "fotos",
    "fonte",
    "fundiaria",
    "galeria",
    "gerencia",
    "imagem",
    "imagens",
    "imprensa",
    "informacoes",
    "infraestrutura",
    "indiretas",
    "juridica",
    "juridico",
    "legislativo",
    "licitacao",
    "licitacoes",
    "login",
    "gabinete",
    "gestao",
    "governou",
    "graduada",
    "graduado",
    "habitacao",
    "horario",
    "juventude",
    "indice",
    "integridade",
    "lei",
    "legislacao",
    "lendo",
    "licenciamento",
    "localizacao",
    "mariele",
    "meio",
    "menino",
    "ministerio",
    "mes",
    "minha",
    "municipais",
    "municipal",
    "municipio",
    "mun",
    "mulher",
    "mulheres",
    "negocios",
    "negativa",
    "nossa",
    "nosso",
    "desde",
    "obras",
    "oficial",
    "opcao",
    "ordem",
    "organizacional",
    "orgao",
    "orgaos",
    "ouvidoria",
    "parque",
    "patrulha",
    "poder",
    "poderes",
    "portal",
    "praca",
    "posse",
    "prestacao",
    "pdf",
    "presidente",
    "prefeita",
    "prefeito",
    "prefeitura",
    "prefeituras",
    "ponto",
    "popular",
    "privacidade",
    "programa",
    "procurador",
    "processos",
    "publicas",
    "publicos",
    "redacao",
    "rapido",
    "rapida",
    "redes",
    "redigir",
    "regularizacao",
    "recursos",
    "resultado",
    "responsavel",
    "responsaveis",
    "responsa",
    "reportagem",
    "rua",
    "saude",
    "secretaria",
    "secretarias",
    "secretario",
    "sec",
    "servico",
    "servicos",
    "sistema",
    "sessao",
    "sociais",
    "sobre",
    "sua",
    "subsecretaria",
    "subsecretario",
    "telefone",
    "telefones",
    "tecnologia",
    "tecnica",
    "territorio",
    "legislativa",
    "termos",
    "eletronico",
    "seletivos",
    "tribunal",
    "trabalho",
    "transparencia",
    "transmissao",
    "todas",
    "transformar",
    "tributacao",
    "turista",
    "tia",
    "indenizatoria",
    "rural",
    "urbano",
    "urbanismo",
    "turistica",
    "departamentos",
    "divisao",
    "distritos",
    "industriais",
    "institucional",
    "filtrar",
    "noticia",
    "noticias",
    "paginas",
    "apagar",
    "agenda",
    "ultima",
    "ultimas",
    "ultimo",
    "unico",
    "antecedentes",
    "anexo",
    "armadas",
    "ativa",
    "canta",
    "center",
    "cerrado",
    "complexidade",
    "constituicoes",
    "conselheiros",
    "creche",
    "criminais",
    "desemprego",
    "diretores",
    "direitos",
    "divida",
    "edificio",
    "emprega",
    "emergencia",
    "escola",
    "escolares",
    "estagiarios",
    "executivas",
    "feder",
    "festival",
    "fomento",
    "forcas",
    "frequentes",
    "humanos",
    "infantil",
    "interno",
    "jogos",
    "junta",
    "leis",
    "linha",
    "militar",
    "oficina",
    "parceria",
    "perguntas",
    "pela",
    "predio",
    "regimento",
    "retrospectiva",
    "rotary",
    "sebrae",
    "seguro",
    "secretarios",
    "agendas",
    "ambientais",
    "assistencia",
    "assessorias",
    "assuntos",
    "atribuicoes",
    "analisar",
    "anterior",
    "castramovel",
    "codigo",
    "construcao",
    "consumidor",
    "coordenacao",
    "disciplinas",
    "disponiveis",
    "expansao",
    "externos",
    "gerente",
    "governamental",
    "governanca",
    "habilitacao",
    "industrial",
    "inicial",
    "juridico",
    "juridicos",
    "local",
    "mobilidade",
    "nacional",
    "pedagogicas",
    "portuaria",
    "primeira",
    "proximo",
    "posturas",
    "publico",
    "se",
    "secao",
    "seguranca",
    "solicitacoes",
    "sustentabilidade",
    "universidade",
    "vagas",
    "vigilancia",
    "situacao",
    "somos",
    "torre",
    "transportes",
    "tutelares",
    "unidades",
    "via",
    "ver",
    "visualizar",
    "verba",
    "valores",
}

NOME_PREFIXOS_INVALIDOS = {
    "casado",
    "cirurgiao",
    "foi",
    "servidor",
    "vereadora",
    "vereador",
    "prefeitos",
    "introducao",
    "adjunto",
}

CARGOS_EXECUTIVOS = {"Prefeito", "Vice-prefeito", "Chefe de gabinete"}
PARTICULAS_NOME = {"de", "da", "do", "dos", "das", "e"}

SECOES_RUIDOSAS = {
    "ultimas noticias",
    "ultimas notícias",
    "noticias recentes",
    "notícias recentes",
    "agendamento de consulta on-line",
    "telefones uteis",
    "telefones úteis",
    "veja tambem",
    "veja também",
    "leia tambem",
    "leia também",
    "noticias relacionadas",
    "notícias relacionadas",
}

SECOES_DADOS_GERAIS = (
    "endereco",
    "localizacao",
    "horario",
    "humanos",
    "data",
    "horario de funcionamento",
    "informacoes",
    "links uteis",
)

SECOES_SUBORDINADAS = (
    "assessoria",
    "coordenacao",
    "coordenadoria",
    "conselho",
    "cras",
    "creas",
    "departamento",
    "diretoria",
    "diretor",
    "divisao",
    "gerencia",
    "programa",
    "setor",
    "superintendencia",
    "unidade",
)

CREDITO_AUTORIA_PREFIXOS = (
    "foto",
    "fotos",
    "credito",
    "creditos",
    "imagem",
    "imagens",
    "autor",
    "autoria",
    "reportagem",
    "redacao",
)

ENDERECO_PREFIXOS = (
    "alameda ",
    "avenida ",
    "av ",
    "av. ",
    "bairro ",
    "cep",
    "endere",
    "endereco",
    "estrada ",
    "localiza",
    "localizacao",
    "logradouro",
    "praca ",
    "rodovia ",
    "rua ",
    "travessa ",
)

VARIACOES_GENERICAS_IGNORADAS = {
    ("chefe_gabinete", "gabinete"),
    ("desenvolvimento", "desenvolvimento"),
    ("financas_fazenda", "fazenda"),
    ("financas_fazenda", "financas"),
    ("planejamento", "planejamento"),
}

COL_ORGAO = "\u00d3rg\u00e3o/Secretaria"
COL_CARGO_AREA = "Cargo/\u00c1rea"
COL_CARGO_ORGAO = "Cargo/\u00d3rg\u00e3o"
COL_URL_ESPECIFICA = "URL espec\u00edfica"
COL_OBSERVACOES = "Observa\u00e7\u00f5es"
PROFILE_BLANK_LINE = "__PROFILE_BLANK_LINE__"
CONTATO_CONTINUACAO_PREFIXOS = (
    "contatos",
    "contato",
    "e-mail",
    "email",
    "telefone",
    "telefones",
    "fone",
    "celular",
    "whatsapp",
)

NOME_PREFIXOS_DESCARTAVEIS = {
    "assessor",
    "assessora",
    "chefe",
    "completo",
    "curriculo",
    "deputada",
    "deputado",
    "destaque",
    "destaques",
    "detalhes",
    "fechar",
    "habitacao",
    "historia",
    "horario",
    "horarios",
    "imprimir",
    "introducao",
    "nome",
    "pelo",
    "principal",
    "responsavel",
    "responsaveis",
    "titular",
}
NOME_SUFFIXOS_DESCARTAVEIS = {
    "acao",
    "acoes",
    "ao",
    "biografia",
    "dados",
    "data",
    "detalhes",
    "adjunta",
    "adjunto",
    "em",
    "endere",
    "fone",
    "formulario",
    "funcao",
    "categoria",
    "corrigir",
    "dr",
    "dra",
    "conheca",
    "graduada",
    "graduado",
    "introducao",
    "na",
    "partido",
    "procurador",
    "procuradora",
    "saber",
    "sede",
    "vice",
}


def carregar_cargos(path: str | Path | None = None) -> dict[str, list[str]]:
    config_path = Path(path) if path else project_path("config", "cargos.yml")
    data = load_yaml(config_path)
    return {str(key): [str(item) for item in value or []] for key, value in data.items()}


def extrair_emails(texto: str) -> list[str]:
    emails = [_limpar_email(email.lower()) for email in EMAIL_PATTERN.findall(texto or "")]
    emails = [email for email in emails if email]
    return list(dict.fromkeys(emails))


def _limpar_email(email: str) -> str:
    value = str(email or "").strip().strip(".,;:")
    for suffix in ("telefone", "telefones", "fone", "celular", "whatsapp"):
        if value.endswith(suffix):
            value = value[: -len(suffix)]
            break
    return value.strip(".,;:")


def extrair_telefones(texto: str) -> list[str]:
    telefones: list[str] = []
    for match in PHONE_PATTERN.finditer(texto or ""):
        telefone = match.group(0).strip()
        somente_digitos = re.sub(r"\D", "", telefone)
        if _parece_intervalo_de_anos(match):
            continue
        if not match.group(1) and telefone == somente_digitos and len(somente_digitos) == 8:
            continue
        telefones.append(telefone)
    return list(dict.fromkeys(telefones))


def _parece_intervalo_de_anos(match: re.Match) -> bool:
    if match.group(1):
        return False
    inicio = match.group(2)
    fim = match.group(3)
    if len(inicio) != 4 or len(fim) != 4:
        return False
    if inicio.startswith(("19", "20")) and fim.startswith(("19", "20")):
        return True
    return bool(fim.startswith("20") and 101 <= int(inicio) <= 3112)


def _digits(value: str) -> str:
    digits = re.sub(r"\D", "", value or "")
    if digits.startswith("55") and len(digits) in {12, 13}:
        digits = digits[2:]
    return digits


def telefone_eh_celular(value: str) -> bool:
    digits = _digits(value)
    if len(digits) == 11:
        return digits[2] == "9"
    if len(digits) == 9:
        return digits[0] == "9"
    return False


def extrair_celulares(texto: str) -> list[str]:
    return [phone for phone in extrair_telefones(texto) if telefone_eh_celular(phone)]


def dividir_blocos(texto: str) -> list[str]:
    text = re.sub(r"\r\n?", "\n", texto or "")
    raw_blocks = re.split(r"\n{2,}", text)
    blocks: list[str] = []
    for raw in raw_blocks:
        lines = [line.strip() for line in raw.splitlines() if line.strip()]
        if not lines:
            continue
        if len(" ".join(lines)) > 1200:
            blocks.extend("\n".join(lines[i : i + 8]) for i in range(0, len(lines), 8))
        else:
            blocks.append("\n".join(lines))
    return blocks or [text]


def _termo_cargo_presente(haystack: str, needle: str) -> bool:
    if not needle:
        return False

    candidates = {needle, needle.replace(" ", "-")}
    for candidate in candidates:
        escaped = re.escape(candidate)
        if candidate in {"prefeito", "prefeita"}:
            pattern = rf"(?<!vice-)(?<!vice )(?<![\w-]){escaped}(?![\w-])"
        else:
            pattern = rf"(?<![\w-]){escaped}(?![\w-])"
        for match in re.finditer(pattern, haystack):
            if candidate.replace("-", " ") in {"chefe de gabinete", "chefia de gabinete"}:
                suffix = haystack[match.end() : match.end() + 80]
                if re.match(r"^\s+(do|da|de)\s+(?!prefeit[oa]\b|executivo\b|municipio\b|municipal\b)", suffix):
                    continue
            return True
    return False


def _ignorar_variacao_generica(cargo_key: str, variacao: str) -> bool:
    return (cargo_key, normalize_for_search(variacao)) in VARIACOES_GENERICAS_IGNORADAS


def detectar_cargos(texto: str, cargos_config: dict[str, list[str]]) -> list[str]:
    haystack = normalize_for_search(texto)
    encontrados: list[str] = []
    for cargo_key, variacoes in cargos_config.items():
        for variacao in variacoes:
            if _ignorar_variacao_generica(cargo_key, variacao):
                continue
            needle = normalize_for_search(variacao)
            if _termo_cargo_presente(haystack, needle):
                encontrados.append(CARGO_LABELS.get(cargo_key, cargo_key.replace("_", " ").title()))
                break
    if (
        "Secretaria de Desenvolvimento Econômico" in encontrados
        and "Secretaria de Desenvolvimento" in encontrados
        and "desenvolvimento economico" in haystack
    ):
        encontrados = [cargo for cargo in encontrados if cargo != "Secretaria de Desenvolvimento"]
    return list(dict.fromkeys(encontrados))


def _nome_valido(nome: str) -> bool:
    nome = str(nome or "").strip(" \t\n\r:-|,.;")
    if not nome or re.search(r"[@\d]", nome):
        return False
    normalized = normalize_for_search(nome)
    if re.match(r"^(de|da|do|dos|das|e)\s+", normalized):
        return False
    if any(term in normalized for term in NOME_EXCLUDE):
        return False
    if any(normalized.startswith(prefix) for prefix in NOME_PREFIXOS_INVALIDOS):
        return False
    normalized_parts = [
        normalize_for_search(part).strip(".,:;")
        for part in nome.split()
        if normalize_for_search(part).strip(".,:;") not in {"de", "da", "do", "dos", "das", "e"}
    ]
    if any(part in NOME_TOKEN_EXCLUDE for part in normalized_parts):
        return False
    if len(normalized_parts) != len(set(normalized_parts)):
        return False
    return 2 <= len(normalized_parts) <= 6


def inferir_orgao_secretaria(cargo: str) -> str:
    lowered = normalize_for_search(cargo)
    if lowered.startswith(("secretaria", "agencia", "sala")):
        return cargo
    if cargo in {"Prefeito", "Vice-prefeito", "Chefe de gabinete"}:
        return "Gabinete/Prefeitura"
    if cargo == "Contato geral":
        return "Contato geral"
    return cargo


def _montar_resultado(
    cargo: str,
    nome: str,
    emails: list[str],
    fixos: list[str],
    celulares: list[str],
    url: str,
    status: str,
    observacoes: str = "",
) -> dict[str, str]:
    return {
        COL_ORGAO: inferir_orgao_secretaria(cargo),
        COL_CARGO_AREA: cargo,
        COL_CARGO_ORGAO: cargo,
        "Nome": nome,
        "E-mail": "; ".join(emails),
        "Telefone": "; ".join(fixos),
        "Celular/WhatsApp": "; ".join(celulares),
        "Celular": "; ".join(celulares),
        "URL da fonte": url,
        COL_URL_ESPECIFICA: url,
        "Status": status,
        COL_OBSERVACOES: observacoes,
    }


def _linhas_perfil(texto: str) -> list[str]:
    linhas: list[str] = []
    for raw_line in re.sub(r"\r\n?", "\n", texto or "").split("\n"):
        line = raw_line.strip()
        if line:
            linhas.append(line)
        elif linhas and linhas[-1] != PROFILE_BLANK_LINE:
            linhas.append(PROFILE_BLANK_LINE)
    while linhas and linhas[-1] == PROFILE_BLANK_LINE:
        linhas.pop()
    return linhas


def _trecho_perfil(lines: list[str], start: int, end: int) -> str:
    return "\n".join(line for line in lines[start:end] if line != PROFILE_BLANK_LINE)


def _proxima_linha_perfil(lines: list[str], start: int) -> str:
    for line in lines[start + 1 :]:
        if line != PROFILE_BLANK_LINE:
            return line
    return ""


def _linha_anterior_perfil(lines: list[str], start: int) -> str:
    for line in reversed(lines[:start]):
        if line != PROFILE_BLANK_LINE:
            return line
    return ""


def _linha_continua_contato(line: str) -> bool:
    normalized = normalize_for_search(line).strip()
    for prefix in CONTATO_CONTINUACAO_PREFIXOS:
        if normalized == prefix:
            return True
        match = re.match(rf"^{re.escape(prefix)}\s*[:\-\u2013\u2014]\s*(.*)$", normalized)
        if match:
            suffix = match.group(1).strip()
            return not suffix or bool(extrair_emails(suffix) or extrair_telefones(suffix))
    return False


def _linha_continua_biografia(line: str, nome: str) -> bool:
    normalized_line = normalize_for_search(line)
    normalized_nome = normalize_for_search(nome)
    return bool(normalized_nome and normalized_nome in normalized_line)


def _linha_parece_secao_dados_gerais(line: str) -> bool:
    normalized = normalize_for_search(line).strip(" :-")
    return any(normalized.startswith(section) for section in SECOES_DADOS_GERAIS)


def _linha_parece_secao_subordinada(line: str) -> bool:
    normalized = normalize_for_search(line).strip(" :-")
    return any(normalized.startswith(section) for section in SECOES_SUBORDINADAS)


def _linha_parece_titulo_orgao(line: str) -> bool:
    normalized = normalize_for_search(line).strip(" :-")
    return normalized.startswith(
        (
            "secretaria municipal ",
            "secretaria de ",
            "secretaria da ",
            "secretaria do ",
            "controladoria ",
            "procuradoria ",
            "hospital municipal",
            "recursos humanos",
            "caixa de previdencia",
        )
    )


def _linha_parece_endereco(line: str) -> bool:
    normalized = normalize_for_search(line).strip(" :-")
    if any(normalized.startswith(prefix) for prefix in ENDERECO_PREFIXOS):
        return True
    return bool(re.search(r"\b\d{5}-?\d{3}\b", normalized))


def _linha_parece_credito_autoria(line: str) -> bool:
    normalized = normalize_for_search(line).strip(" :-")
    return any(re.match(rf"^{re.escape(prefix)}\b", normalized) for prefix in CREDITO_AUTORIA_PREFIXOS)


def _trecho_tem_credito_para_nome(texto: str, nome: str) -> bool:
    nome_norm = normalize_for_search(nome)
    if not nome_norm:
        return False
    normalized = normalize_for_search(texto)
    prefix_pattern = "|".join(re.escape(prefix) for prefix in CREDITO_AUTORIA_PREFIXOS)
    return bool(re.search(rf"\b(?:{prefix_pattern})\b\s*[:\-\u2013\u2014]?\s*{re.escape(nome_norm)}\b", normalized))


def _nome_aparece_apenas_em_linha_de_endereco(texto: str, nome: str) -> bool:
    nome_norm = normalize_for_search(nome)
    if not nome_norm:
        return False
    linhas_com_nome = [line for line in _linhas_nao_vazias(texto) if nome_norm in normalize_for_search(line)]
    return bool(linhas_com_nome) and all(
        _linha_parece_endereco(line) or _nome_em_contexto_de_endereco(line, nome)
        for line in linhas_com_nome
    )


def _nome_em_contexto_de_endereco(texto: str, nome: str) -> bool:
    nome_norm = normalize_for_search(nome)
    normalized = normalize_for_search(texto)
    if not nome_norm or not normalized:
        return False
    tokens = (
        "endereco",
        "endere",
        "localizacao",
        "localiza",
        "logradouro",
        "rua",
        "avenida",
        "av.",
        "av ",
        "praca",
        "rodovia",
        "travessa",
    )
    for match in re.finditer(re.escape(nome_norm), normalized):
        contexto = normalized[max(0, match.start() - 70) : match.start()]
        if any(token in contexto for token in tokens):
            return True
    return False


def _nome_em_contexto_familiar_ou_biografico(texto: str, nome: str) -> bool:
    nome_norm = normalize_for_search(nome)
    normalized = normalize_for_search(texto)
    if not nome_norm or not normalized:
        return False
    termos = (
        "esposa",
        "esposo",
        "companheira",
        "companheiro",
        "filho",
        "filha",
        "mae",
        "pai",
        "irmao",
        "irma",
    )
    for match in re.finditer(re.escape(nome_norm), normalized):
        contexto = normalized[max(0, match.start() - 80) : min(len(normalized), match.end() + 80)]
        if any(termo in contexto for termo in termos):
            return True
    return False


def _nome_antes_do_indice(texto: str, index: int) -> str:
    prefix = str(texto or "")[max(0, index - 180) : index].strip(" \t\n\r:-\u2013\u2014")
    if not prefix:
        return ""
    partes = re.split(
        r"(?:/|\b(?:home|inicio|gabinete|poder executivo|secretaria|prefeitura)\b)",
        prefix,
        flags=re.IGNORECASE,
    )
    for parte in reversed(partes):
        nome = _nome_no_trecho(parte)
        if (
            nome
            and _nome_valido(nome)
            and not _nome_aparece_apenas_em_linha_de_credito(parte, nome)
            and not _nome_em_contexto_de_endereco(parte, nome)
            and not _nome_em_contexto_familiar_ou_biografico(parte, nome)
        ):
            return nome
    return ""


def _nome_aparece_apenas_em_linha_de_credito(texto: str, nome: str) -> bool:
    nome_norm = normalize_for_search(nome)
    if not nome_norm:
        return False
    linhas_com_nome = [line for line in _linhas_nao_vazias(texto) if nome_norm in normalize_for_search(line)]
    return bool(linhas_com_nome) and all(
        _linha_parece_credito_autoria(line) or _trecho_tem_credito_para_nome(line, nome)
        for line in linhas_com_nome
    )


def _linha_parece_inicio_perfil(line: str, cargos_config: dict[str, list[str]]) -> bool:
    normalized = normalize_for_search(line).strip(" :-")
    if not normalized or len(normalized) > 140:
        return False
    if _cargo_no_inicio_da_linha(line, cargos_config):
        return True
    return normalized in {"gabinete", "prefeito", "prefeita", "vice prefeito", "vice-prefeito"} or normalized.startswith(
        (
            "secretaria de ",
            "secretaria da ",
            "secretaria do ",
            "secretaria municipal",
            "secretaria estadual",
            "departamento de ",
            "diretoria de ",
            "superintendencia de ",
            "chefia de ",
            "fundacao ",
        )
    )


def _remover_secoes_ruidosas(texto: str) -> str:
    linhas: list[str] = []
    for raw_line in re.sub(r"\r\n?", "\n", texto or "").split("\n"):
        normalized = normalize_for_search(raw_line)
        if any(normalized.startswith(section) for section in SECOES_RUIDOSAS):
            break
        linhas.append(raw_line)
    return "\n".join(linhas)


def _cargo_por_linha_curta(line: str, cargos_config: dict[str, list[str]]) -> str:
    text = str(line or "").strip(" \t:-\u2013\u2014")
    if not text or len(text) > 90 or re.search(r"[@\d.,;]", text):
        return ""

    normalized = normalize_for_search(text)
    normalized = re.sub(r"^(o|a)\s+", "", normalized)
    normalized_plain = normalized.replace("-", " ")

    for cargo_key, variacoes in cargos_config.items():
        label = CARGO_LABELS.get(cargo_key, cargo_key.replace("_", " ").title())
        candidates = {normalize_for_search(label).replace("-", " ")}
        candidates.update(
            normalize_for_search(variacao).replace("-", " ")
            for variacao in variacoes
            if not _ignorar_variacao_generica(cargo_key, variacao)
        )
        if normalized_plain in candidates:
            return label
        if label == "Prefeito" and "gabinete do prefeito" in candidates and "gabinete do prefeito" in normalized_plain:
            return label
    return ""


def _cargo_pattern(candidate: str) -> str:
    tokens = [re.escape(token) for token in re.split(r"[\s-]+", candidate) if token]
    return r"[\s-]+".join(tokens)


def _cargo_no_inicio_info(line: str, cargos_config: dict[str, list[str]]) -> tuple[str, str]:
    cargo = _cargo_por_linha_curta(line, cargos_config)
    if cargo:
        return cargo, ""

    original = str(line or "").strip()
    normalized = strip_accents(original).lower()
    article_match = re.match(r"^(o|a)\s+", normalized)
    offset = article_match.end() if article_match else 0
    normalized = normalized[offset:]
    for cargo_key, variacoes in cargos_config.items():
        label = CARGO_LABELS.get(cargo_key, cargo_key.replace("_", " ").title())
        candidates = {normalize_for_search(label)}
        candidates.update(
            normalize_for_search(variacao)
            for variacao in variacoes
            if not _ignorar_variacao_generica(cargo_key, variacao)
        )
        for candidate in candidates:
            candidate_pattern = _cargo_pattern(candidate)
            if not candidate_pattern:
                continue
            match = re.match(rf"^{candidate_pattern}\s*[,/]\s*(.*)$", normalized)
            if match:
                return label, ""
            match = re.match(rf"^{candidate_pattern}\s*[:\-\u2013\u2014]\s*(.+)$", normalized)
            if match:
                tail = original[offset + match.start(1) :].strip(" \t:-\u2013\u2014")
                return label, tail
            match = re.match(rf"^{candidate_pattern}\s+(.+)$", normalized)
            if match:
                tail = original[offset + match.start(1) :].strip(" \t:-\u2013\u2014")
                if normalize_for_search(tail).startswith(("de ", "da ", "do ", "dos ", "das ")):
                    continue
                nome_tail = _nome_da_linha(tail)
                if nome_tail:
                    return label, nome_tail
    return "", ""


def _cargo_no_inicio_da_linha(line: str, cargos_config: dict[str, list[str]]) -> str:
    cargo, _ = _cargo_no_inicio_info(line, cargos_config)
    return cargo


def _limpar_ruido_nome(candidate: str) -> str:
    value = str(candidate or "").strip(" \t:-\u2013\u2014.,")
    value = re.sub(r"^\s*(?:nome|introdu[cç][aã]o|detalhes)\s*[:\-\u2013\u2014]?\s*", "", value, flags=re.IGNORECASE)
    value = re.split(
        r"\b(?:chefe de gabinete|vice-prefeit[oa]|vice prefeit[oa]|vice|telefones?|e-?mails?|emails?|contatos?|celular|whatsapp|endere[cÃ§]o|hor[aÃ¡]rio|atendimento)\b",
        value,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0].strip(" \t:-\u2013\u2014.,")
    parts = value.split()
    while parts and normalize_for_search(parts[0].strip(".,:;")) in NOME_PREFIXOS_DESCARTAVEIS:
        parts.pop(0)
    while parts and normalize_for_search(parts[-1].strip(".,:;")) in NOME_SUFFIXOS_DESCARTAVEIS:
        parts.pop()
    return " ".join(parts).strip(" \t:-\u2013\u2014.,")


def _nome_no_trecho(value: str) -> str:
    candidate = _limpar_ruido_nome(value)
    candidate = re.split(
        r"\b(?:chefe de gabinete|vice-prefeit[oa]|vice prefeit[oa]|vice|telefones?|e-?mails?|emails?|contatos?|celular|whatsapp|endere[cç]o|hor[aá]rio|atendimento)\b",
        candidate,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0].strip(" \t:-\u2013\u2014")
    candidate = _limpar_ruido_nome(candidate)
    normalized_candidate = normalize_for_search(candidate)
    if re.match(r"^(foto|fotos|credito|creditos|imagem|imagens|autor|autoria|reportagem|redacao)\b", normalized_candidate):
        return ""
    if _nome_valido(candidate) and _parece_linha_de_nome_proprio(candidate):
        return candidate
    for found in NAME_PATTERN.finditer(candidate):
        nome = _limpar_ruido_nome(found.group(1))
        if _nome_valido(nome):
            return nome
    return ""


def _nome_da_linha(line: str) -> str:
    candidate = _limpar_ruido_nome(line)
    candidate = re.split(
        r"\b(?:chefe de gabinete|vice-prefeit[oa]|vice prefeit[oa]|vice|telefones?|e-?mails?|emails?|contatos?|celular|whatsapp|endere[cç]o|hor[aá]rio|atendimento)\b",
        candidate,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0].strip(" \t:-\u2013\u2014")
    candidate = _limpar_ruido_nome(candidate)
    if not _nome_valido(candidate):
        return ""
    found = NAME_PATTERN.fullmatch(candidate)
    if found:
        return found.group(1)
    if _parece_linha_de_nome_proprio(candidate):
        return candidate
    return ""


def _nome_em_linhas_sequenciais(lines: list[str], start: int, limit: int = 5) -> tuple[str, int]:
    partes: list[str] = []
    ultimo_index = start
    for index in range(start, min(len(lines), start + limit)):
        line = str(lines[index] or "").strip(" \t:-\u2013\u2014.,")
        if not line or line == PROFILE_BLANK_LINE:
            break
        normalized = normalize_for_search(line).strip(".,:;")
        if normalized in PARTICULAS_NOME:
            partes.append(line)
            ultimo_index = index
            continue
        if " " in line or re.search(r"[@\d]", line):
            break
        if normalized in NOME_TOKEN_EXCLUDE or normalized in NOME_SUFFIXOS_DESCARTAVEIS:
            break
        if not _parece_linha_de_nome_proprio(line):
            break
        partes.append(line)
        ultimo_index = index

    candidate = _limpar_ruido_nome(" ".join(partes))
    if len(partes) >= 2 and _nome_valido(candidate) and _parece_linha_de_nome_proprio(candidate):
        return candidate, ultimo_index
    return "", start


def _parece_linha_de_nome_proprio(candidate: str) -> bool:
    token_pattern = re.compile(r"^[A-ZÁÀÂÃÉÈÊÍÌÓÒÔÕÚÙÇ][A-Za-zÁÀÂÃÉÈÊÍÌÓÒÔÕÚÙÇáàâãéèêíìóòôõúùç']+$")
    for token in str(candidate or "").split():
        normalized = normalize_for_search(token).strip(".,:;")
        if normalized in PARTICULAS_NOME:
            continue
        if not token_pattern.match(token.strip(".,:;")):
            return False
    return True


def _fim_janela_perfil(
    lines: list[str],
    start: int,
    nome_index: int,
    nome_atual: str,
    cargo_atual: str,
    cargos_config: dict[str, list[str]],
) -> int:
    end = min(len(lines), start + 80)
    for index in range(nome_index + 1, end):
        if lines[index] == PROFILE_BLANK_LINE:
            proxima_linha = _proxima_linha_perfil(lines, index)
            if _linha_continua_contato(proxima_linha):
                continue

            trecho = _trecho_perfil(lines, start, index)
            if extrair_emails(trecho) or extrair_telefones(trecho):
                return index

            linha_anterior = _linha_anterior_perfil(lines, index)
            cargo_anterior = _cargo_no_inicio_da_linha(linha_anterior, cargos_config)
            if cargo_anterior == cargo_atual and _linha_continua_biografia(proxima_linha, nome_atual):
                continue

            return index

        normalized = normalize_for_search(lines[index])
        if _linha_parece_secao_dados_gerais(lines[index]):
            return index
        if _linha_parece_secao_subordinada(lines[index]):
            return index
        if any(normalized.startswith(section) for section in SECOES_RUIDOSAS):
            return index
        proximo_cargo = _cargo_no_inicio_da_linha(lines[index], cargos_config)
        if index > nome_index and _linha_parece_inicio_perfil(lines[index], cargos_config) and proximo_cargo != cargo_atual:
            return index
        if proximo_cargo and proximo_cargo != cargo_atual:
            return index
        if proximo_cargo and index > start + 4:
            trecho = _trecho_perfil(lines, start, index)
            if extrair_emails(trecho) or extrair_telefones(trecho):
                return index
    return end


def extrair_perfis_institucionais(
    texto: str,
    cargos_config: dict[str, list[str]],
    url: str,
) -> list[dict[str, str]]:
    linhas = _linhas_perfil(texto)
    resultados: list[dict[str, str]] = []

    for index, line in enumerate(linhas):
        if line == PROFILE_BLANK_LINE:
            continue

        cargo, nome_inline = _cargo_no_inicio_info(line, cargos_config)
        if not cargo and normalize_for_search(line).strip(" :-") == "gabinete":
            next_index = _indice_proxima_linha(linhas, index)
            if next_index is not None and _nome_da_linha(linhas[next_index]):
                cargo = "Chefe de gabinete"
        if not cargo:
            continue

        nome = _nome_no_trecho(nome_inline)
        nome_index = index
        if not nome:
            sequencial, sequencial_index = _nome_em_linhas_sequenciais(linhas, index + 1)
            if sequencial:
                nome = sequencial
                nome_index = sequencial_index
        if not nome:
            for candidate_index, candidate_line in enumerate(linhas[index + 1 : index + 5], start=index + 1):
                if candidate_line == PROFILE_BLANK_LINE:
                    continue

                proximo_cargo, proximo_nome_inline = _cargo_no_inicio_info(candidate_line, cargos_config)
                if proximo_cargo:
                    if proximo_cargo != cargo:
                        break
                    nome = _nome_no_trecho(proximo_nome_inline)
                    if nome:
                        nome_index = candidate_index
                        break
                    continue

                nome, rotulo_nome_index = _nome_apos_rotulo_responsavel(linhas, candidate_index)
                if nome:
                    nome_index = rotulo_nome_index
                    break

                nome = _nome_da_linha(candidate_line)
                if nome:
                    nome_index = candidate_index
                    break
        if not nome:
            continue

        end = _fim_janela_perfil(linhas, index, nome_index, nome, cargo, cargos_config)
        trecho = _trecho_perfil(linhas, index, end)
        emails = extrair_emails(trecho)
        telefones = extrair_telefones(trecho)
        celulares = [phone for phone in telefones if telefone_eh_celular(phone)]
        fixos = [phone for phone in telefones if phone not in celulares]
        emails, fixos, celulares = _filtrar_contatos_por_cargo(cargo, trecho, emails, fixos, celulares)
        emails, fixos, celulares = _limitar_contatos_de_homepage(cargo, url, emails, fixos, celulares)
        tem_contato = bool(emails or fixos or celulares)
        if _descartar_resultado_por_contexto(cargo, url, tem_contato):
            continue
        status = "Encontrado" if tem_contato else "Parcial"
        observacoes = "" if tem_contato else "Cargo ou nome identificado, mas sem contato direto no mesmo bloco."
        resultados.append(_montar_resultado(cargo, nome, emails, fixos, celulares, url, status, observacoes))

    return _deduplicar_resultados(resultados)


def _linhas_nao_vazias(texto: str) -> list[str]:
    return [line.strip() for line in re.sub(r"\r\n?", "\n", texto or "").split("\n") if line.strip()]


def _indice_proxima_linha(lines: list[str], start: int) -> int | None:
    for index in range(start + 1, len(lines)):
        if lines[index].strip():
            return index
    return None


def _limite_bloco_secretaria(lines: list[str], start: int) -> int:
    end = min(len(lines), start + 80)
    for index in range(start + 1, end):
        normalized = normalize_for_search(lines[index])
        if normalized == "secretarias" or normalized.startswith(("endereco", "ultimas noticias", "noticias relacionadas", "ver todas")):
            return index
        if _linha_parece_titulo_orgao(lines[index]):
            return index
        if _linha_parece_secao_subordinada(lines[index]):
            return index
    return end


def _contatos_no_intervalo(lines: list[str], start: int, end: int) -> tuple[list[str], list[str], list[str]]:
    trecho = "\n".join(lines[start:end])
    emails = extrair_emails(trecho)
    telefones = extrair_telefones(trecho)
    celulares = [phone for phone in telefones if telefone_eh_celular(phone)]
    fixos = [phone for phone in telefones if phone not in celulares]
    return emails, fixos, celulares


def _nome_apos_rotulo_secretario(lines: list[str], index: int) -> tuple[str, int]:
    line = lines[index]
    normalized = normalize_for_search(line).strip(" :-\u2013\u2014")
    if normalized in {"secretario", "secretaria", "secretario(a)"}:
        next_index = _indice_proxima_linha(lines, index)
        if next_index is None:
            return "", index
        return _nome_da_linha(lines[next_index]) or _nome_no_trecho(lines[next_index]), next_index

    match = re.match(r"^\s*secret[aá]ri[oa](?:\s*\(a\))?\s*[:\-\u2013\u2014]\s*(.*)$", line, flags=re.IGNORECASE)
    if not match:
        return "", index

    inline = _nome_no_trecho(match.group(1))
    if inline:
        return inline, index

    next_index = _indice_proxima_linha(lines, index)
    if next_index is None:
        return "", index
    return _nome_da_linha(lines[next_index]) or _nome_no_trecho(lines[next_index]), next_index


def _nome_apos_rotulo_responsavel(lines: list[str], index: int) -> tuple[str, int]:
    line = lines[index]
    normalized = normalize_for_search(line).strip(" :-")
    if not (
        normalized.startswith("respons")
        or normalized.startswith("titular")
        or normalized.startswith("autoridade administrativa")
    ):
        return "", index
    if normalized.startswith("autoridade administrativa"):
        inline_source = re.sub(
            r"^\s*autoridade\s+administrativa\s*[:\-\u2013\u2014]?\s*",
            "",
            line,
            flags=re.IGNORECASE,
        )
    elif normalized.startswith("titular"):
        inline_source = re.sub(r"^\s*titular\s*[:\-\u2013\u2014]?\s*", "", line, flags=re.IGNORECASE)
    else:
        inline_source = re.sub(r"^\s*respons\S*\s*[:\-\u2013\u2014]?\s*", "", line, flags=re.IGNORECASE)

    inline = _nome_no_trecho(inline_source)
    if inline:
        return inline, index

    next_index = _indice_proxima_linha(lines, index)
    if next_index is None:
        return "", index
    return _nome_da_linha(lines[next_index]) or _nome_no_trecho(lines[next_index]), next_index


def _linha_com_valor(texto: str, valor: str) -> str:
    valor_digits = re.sub(r"\D", "", valor or "")
    valor_norm = normalize_for_search(valor)
    for line in _linhas_nao_vazias(texto):
        line_digits = re.sub(r"\D", "", line)
        line_norm = normalize_for_search(line)
        if valor_digits and valor_digits in line_digits:
            return line
        if valor_norm and valor_norm in line_norm:
            return line
    return ""


def _filtrar_emails_por_cargo(cargo: str, emails: list[str]) -> list[str]:
    if cargo == "Prefeito":
        return [
            email
            for email in emails
            if "vice" not in email.lower()
            and not any(email.lower().startswith(prefix) for prefix in ("administra@", "contato@", "ouvidoria@", "comunicacao@", "administracao@"))
        ]
    if cargo == "Vice-prefeito":
        return [
            email
            for email in emails
            if not (("prefeito" in email.lower() or email.lower().startswith("prefeitura")) and "vice" not in email.lower())
            and (
                "vice" in email.lower()
                or not any(email.lower().startswith(prefix) for prefix in ("administra@", "contato@", "ouvidoria@", "comunicacao@", "administracao@"))
            )
        ]
    if cargo == "Chefe de gabinete":
        return [email for email in emails if "gabinete" in email.lower()]
    return emails


def _filtrar_telefones_por_cargo(cargo: str, texto: str, telefones: list[str]) -> list[str]:
    filtrados: list[str] = []
    for telefone in telefones:
        line_norm = normalize_for_search(_linha_com_valor(texto, telefone))
        if cargo == "Vice-prefeito" and "gabinete" in line_norm and "vice" not in line_norm:
            continue
        filtrados.append(telefone)
    return filtrados


def _filtrar_contatos_por_cargo(
    cargo: str,
    texto: str,
    emails: list[str],
    fixos: list[str],
    celulares: list[str],
) -> tuple[list[str], list[str], list[str]]:
    emails_filtrados = _filtrar_emails_por_cargo(cargo, emails)
    fixos_filtrados = _filtrar_telefones_por_cargo(cargo, texto, fixos)
    celulares_filtrados = _filtrar_telefones_por_cargo(cargo, texto, celulares)
    if cargo in {"Prefeito", "Vice-prefeito"} and emails and not emails_filtrados:
        fixos_filtrados = []
        celulares_filtrados = []
    if cargo == "Chefe de gabinete" and emails and len(emails_filtrados) < len(emails):
        fixos_filtrados = []
        celulares_filtrados = []
    return emails_filtrados, fixos_filtrados, celulares_filtrados


def _limitar_contatos_de_homepage(
    cargo: str,
    url: str,
    emails: list[str],
    fixos: list[str],
    celulares: list[str],
) -> tuple[list[str], list[str], list[str]]:
    total_contatos = len(emails) + len(fixos) + len(celulares)
    path = normalize_for_search(urlparse(str(url or "")).path).replace("_", "-").replace("/", " ")
    if cargo not in {"Prefeito", "Contato geral"} and _url_raiz(url) and total_contatos > 1:
        return [], [], []
    if cargo != "Contato geral" and "prefeito-e-equipe-de-governo" in path and total_contatos > 2:
        return [], [], []
    if cargo == "Prefeito" and len(fixos) > 2:
        fixos = []
    if cargo != "Contato geral" and total_contatos > 4:
        return [], [], []
    return emails, fixos, celulares


def extrair_perfis_secretaria(
    texto: str,
    cargos_config: dict[str, list[str]],
    url: str,
) -> list[dict[str, str]]:
    lines = _linhas_nao_vazias(texto)
    resultados: list[dict[str, str]] = []

    for index, line in enumerate(lines):
        normalized = normalize_for_search(line)
        if not normalized.startswith(("conheca o secretario", "conheca a secretaria")):
            continue

        nome = ""
        nome_index = index
        for candidate_index in range(index + 1, min(len(lines), index + 6)):
            nome = _nome_da_linha(lines[candidate_index])
            if nome:
                nome_index = candidate_index
                break
        if not nome:
            continue

        cargos: list[str] = []
        cargo_index = _indice_proxima_linha(lines, nome_index)
        if cargo_index is not None:
            cargos.extend(detectar_cargos(lines[cargo_index], cargos_config))
        if not cargos:
            for candidate_line in reversed(lines[max(0, index - 3) : index]):
                if "secretaria" in normalize_for_search(candidate_line):
                    cargos.extend(detectar_cargos(candidate_line, cargos_config))
        cargos = list(dict.fromkeys(cargos))
        if not cargos:
            continue

        end = _limite_bloco_secretaria(lines, index)
        emails, fixos, celulares = _contatos_no_intervalo(lines, index, end)
        for cargo in cargos:
            emails_cargo, fixos_cargo, celulares_cargo = _limitar_contatos_de_homepage(
                cargo, url, emails, [] if celulares else fixos, celulares
            )
            tem_contato_cargo = bool(emails_cargo or fixos_cargo or celulares_cargo)
            status = "Encontrado" if tem_contato_cargo else "Parcial"
            observacoes = "" if status == "Encontrado" else "Nome/cargo publicado, mas sem contato direto no bloco."
            if _descartar_resultado_por_contexto(cargo, url, tem_contato_cargo):
                continue
            resultados.append(_montar_resultado(cargo, nome, emails_cargo, fixos_cargo, celulares_cargo, url, status, observacoes))

    return _deduplicar_resultados(resultados)


def extrair_perfis_lista_secretarias(
    texto: str,
    cargos_config: dict[str, list[str]],
    url: str,
) -> list[dict[str, str]]:
    lines = _linhas_nao_vazias(texto)
    resultados: list[dict[str, str]] = []

    for index, line in enumerate(lines):
        normalized = normalize_for_search(line)
        cargos = detectar_cargos(line, cargos_config)
        if not cargos:
            continue
        titulo_orgao = _linha_parece_titulo_orgao(line) or normalized.startswith("agencia")
        titulo_area_curto = (
            len(normalized) <= 90
            and not re.search(r"[@\d.;]", line)
            and any(
                normalize_for_search(cargo)
                in {
                    "secretaria de desenvolvimento economico",
                    "secretaria de desenvolvimento",
                    "secretaria de financas/fazenda",
                    "secretaria de planejamento",
                }
                for cargo in cargos
            )
        )
        if not titulo_orgao and not titulo_area_curto:
            continue

        nome = ""
        nome_index = index
        for candidate_index in range(index + 1, min(len(lines), index + 10)):
            candidate_normalized = normalize_for_search(lines[candidate_index])
            if candidate_normalized.startswith(("secretario", "secretaria")):
                nome, nome_index = _nome_apos_rotulo_secretario(lines, candidate_index)
            elif candidate_normalized.startswith(("responsavel", "titular", "autoridade administrativa")):
                nome, nome_index = _nome_apos_rotulo_responsavel(lines, candidate_index)
            else:
                continue
            if nome:
                break
        if not nome:
            continue

        end = _limite_bloco_secretaria(lines, nome_index)
        trecho_secretaria = "\n".join(lines[index:end])
        if _nome_aparece_apenas_em_linha_de_endereco(trecho_secretaria, nome) or _nome_em_contexto_de_endereco(trecho_secretaria, nome):
            continue
        emails, fixos, celulares = _contatos_no_intervalo(lines, index, end)
        for cargo in list(dict.fromkeys(cargos)):
            emails_cargo, fixos_cargo, celulares_cargo = _limitar_contatos_de_homepage(
                cargo, url, emails, [] if celulares else fixos, celulares
            )
            tem_contato_cargo = bool(emails_cargo or fixos_cargo or celulares_cargo)
            status = "Encontrado" if tem_contato_cargo else "Parcial"
            observacoes = "" if status == "Encontrado" else "Nome/cargo publicado, mas sem contato direto no bloco."
            if _descartar_resultado_por_contexto(cargo, url, tem_contato_cargo):
                continue
            resultados.append(_montar_resultado(cargo, nome, emails_cargo, fixos_cargo, celulares_cargo, url, status, observacoes))

    return _deduplicar_resultados(resultados)


def extrair_nome_proximo(texto: str, cargos_config: dict[str, list[str]]) -> str:
    block = texto or ""

    nome_match = re.search(r"\bnome\s*[:\-]\s*([A-ZÁÀÂÃÉÈÊÍÌÓÒÔÕÚÙÇ][^\n|;,.]{4,80})", block)
    if nome_match:
        candidate = nome_match.group(1).strip()
        found = NAME_PATTERN.search(candidate)
        candidate = _nome_no_trecho(found.group(1)) if found else ""
        if (
            candidate
            and _nome_valido(candidate)
            and not _nome_aparece_apenas_em_linha_de_credito(block, candidate)
            and not _nome_em_contexto_de_endereco(block, candidate)
        ):
            return candidate

    for index, line in enumerate(_linhas_nao_vazias(block)):
        normalized = normalize_for_search(line).strip(" :-")
        if normalized.startswith(("responsavel", "titular", "autoridade administrativa")):
            nome, _nome_index = _nome_apos_rotulo_responsavel(_linhas_nao_vazias(block), index)
            if nome and _nome_valido(nome) and not _nome_aparece_apenas_em_linha_de_credito(block, nome):
                return nome

    linhas = _linhas_nao_vazias(block)
    for index, line in enumerate(linhas):
        if not _cargo_no_inicio_da_linha(line, cargos_config):
            continue
        nome, _nome_index = _nome_em_linhas_sequenciais(linhas, index + 1)
        if (
            nome
            and not _nome_aparece_apenas_em_linha_de_credito(block, nome)
            and not _nome_em_contexto_de_endereco(block, nome)
            and not _nome_em_contexto_familiar_ou_biografico(block, nome)
        ):
            return nome

    rotulo_match = re.search(
        r"(?:respons\S*|titular|autoridade administrativa)\s*[:\-\u2013\u2014]?\s*(.{4,140})",
        block,
        flags=re.IGNORECASE,
    )
    if rotulo_match:
        candidate = _nome_no_trecho(rotulo_match.group(1))
        if (
            candidate
            and _nome_valido(candidate)
            and not _nome_aparece_apenas_em_linha_de_credito(block, candidate)
            and not _nome_em_contexto_de_endereco(block, candidate)
        ):
            return candidate

    normalized_block = normalize_for_search(block)
    for cargo_key, variacoes in cargos_config.items():
        for variacao in variacoes:
            if _ignorar_variacao_generica(cargo_key, variacao):
                continue
            normalized_variacao = normalize_for_search(variacao)
            index = normalized_block.find(normalized_variacao)
            if index < 0:
                continue
            nome_anterior = _nome_antes_do_indice(block, index)
            if nome_anterior:
                return nome_anterior
            window = block[index : index + 260]
            colon_match = re.search(r"[:\-]\s*([A-ZÁÀÂÃÉÈÊÍÌÓÒÔÕÚÙÇ][^\n|;,.]{4,80})", window)
            if colon_match:
                found = NAME_PATTERN.search(colon_match.group(1))
                candidate = _nome_no_trecho(found.group(1)) if found else ""
                if (
                    candidate
                    and _nome_valido(candidate)
                    and not _nome_aparece_apenas_em_linha_de_credito(window, candidate)
                    and not _nome_em_contexto_de_endereco(window, candidate)
                    and not _nome_em_contexto_familiar_ou_biografico(window, candidate)
                ):
                    return candidate
            for found in NAME_PATTERN.finditer(window):
                candidate = _nome_no_trecho(found.group(1))
                if (
                    candidate
                    and _nome_valido(candidate)
                    and not _nome_aparece_apenas_em_linha_de_credito(window, candidate)
                    and not _nome_em_contexto_de_endereco(window, candidate)
                    and not _nome_em_contexto_familiar_ou_biografico(window, candidate)
                ):
                    return candidate

    for found in NAME_PATTERN.finditer(block[:300]):
        candidate = _nome_no_trecho(found.group(1))
        if (
            candidate
            and _nome_valido(candidate)
            and not _nome_aparece_apenas_em_linha_de_credito(block[:300], candidate)
            and not _nome_em_contexto_de_endereco(block[:300], candidate)
            and not _nome_em_contexto_familiar_ou_biografico(block[:300], candidate)
        ):
            return candidate
    return ""


def _nome_veio_de_rotulo_ou_cargo(bloco: str, nome: str, cargos_config: dict[str, list[str]]) -> bool:
    nome_norm = normalize_for_search(nome)
    if not nome_norm:
        return False
    for line in _linhas_nao_vazias(bloco):
        cargo, nome_inline = _cargo_no_inicio_info(line, cargos_config)
        if cargo and nome_inline and nome_norm in normalize_for_search(nome_inline):
            return True
        if re.search(r"\bnome\s*[:\-]", line, flags=re.IGNORECASE) and nome_norm in normalize_for_search(line):
            return True
        if re.search(r"\bsecret[aá]ri[oa](?:\s*\(a\))?\s*[:\-]", line, flags=re.IGNORECASE) and nome_norm in normalize_for_search(line):
            return True
    return False


def _bloco_de_unidade_subordinada(bloco: str) -> bool:
    normalized = normalize_for_search(bloco)
    return "responsavel" in normalized and any(
        token in normalized
        for token in (
            "departamento",
            "superintendencia",
            "diretoria",
            "divisao",
            "chefia",
            "conselho",
            "unidade",
        )
    )


def _trecho_a_partir_do_nome(bloco: str, nome: str) -> str:
    block = str(bloco or "")
    nome_norm = normalize_for_search(nome)
    if not nome_norm:
        return block
    linhas = _linhas_nao_vazias(block)
    for index, line in enumerate(linhas):
        if nome_norm in normalize_for_search(line):
            end = len(linhas)
            for next_index in range(index + 1, len(linhas)):
                normalized_next = normalize_for_search(linhas[next_index])
                if (
                    _linha_parece_secao_dados_gerais(linhas[next_index])
                    or _linha_parece_secao_subordinada(linhas[next_index])
                    or any(normalized_next.startswith(section) for section in SECOES_RUIDOSAS)
                ):
                    end = next_index
                    break
            return "\n".join(linhas[index:end])
    return block


def _contato_aparece_antes_do_cargo(bloco: str, cargos: list[str]) -> bool:
    text = str(bloco or "")
    normalized = normalize_for_search(text)
    contatos = [match.start() for match in EMAIL_PATTERN.finditer(text)]
    contatos.extend(match.start() for match in PHONE_PATTERN.finditer(text))
    if not contatos:
        return False

    cargo_positions: list[int] = []
    for cargo in cargos:
        cargo_norm = normalize_for_search(cargo).replace("-", " ")
        termos = {cargo_norm}
        if cargo == "Prefeito":
            termos.update({"prefeito", "prefeita"})
        elif cargo == "Vice-prefeito":
            termos.update({"vice prefeito", "vice prefeita"})
        elif cargo == "Chefe de gabinete":
            termos.add("chefe de gabinete")
        for termo in termos:
            pos = normalized.find(termo)
            if pos >= 0:
                cargo_positions.append(pos)
    return bool(cargo_positions and min(contatos) < min(cargo_positions))


def _bloco_tem_cargo_executivo_explicito(bloco: str, cargo: str, cargos_config: dict[str, list[str]]) -> bool:
    for line in _linhas_nao_vazias(bloco):
        if _cargo_no_inicio_da_linha(line, cargos_config) == cargo:
            return True
        normalized = normalize_for_search(line).strip(" :-")
        if cargo == "Prefeito" and normalized.startswith(("gabinete do prefeito", "gabinete da prefeita")):
            return True
        if cargo == "Vice-prefeito" and normalized.startswith(("gabinete do vice", "vice prefeito", "vice-prefeito")):
            return True
        if cargo == "Chefe de gabinete" and normalized.startswith(("chefia de gabinete", "chefe de gabinete", "gabinete")):
            return True
    return False


def _tem_contato_resultado(item: dict[str, str]) -> bool:
    return bool(item.get("E-mail") or item.get("Telefone") or item.get("Celular/WhatsApp") or item.get("Celular"))


def _registro_forte(item: dict[str, str]) -> bool:
    return item.get("Status") == "Encontrado" and bool(item.get("Nome")) and _tem_contato_resultado(item)


def _split_contatos(value: str) -> set[str]:
    return {part.strip().lower() for part in str(value or "").split(";") if part.strip()}


def _telefones_do_resultado(item: dict[str, str]) -> set[str]:
    telefones = set()
    for column in ("Telefone", "Celular/WhatsApp", "Celular"):
        telefones.update(_split_contatos(item.get(column, "")))
    return {digits for digits in (_digits(phone) for phone in telefones) if digits}


def _resultado_compartilha_contato(item: dict[str, str], emails: list[str], telefones: list[str]) -> bool:
    emails_bloco = {email.lower() for email in emails}
    if emails_bloco & _split_contatos(item.get("E-mail", "")):
        return True

    telefones_bloco = {digits for digits in (_digits(phone) for phone in telefones) if digits}
    return bool(telefones_bloco & _telefones_do_resultado(item))


def _resultado_cobre_todos_contatos(item: dict[str, str], emails: list[str], telefones: list[str]) -> bool:
    emails_bloco = {email.lower() for email in emails}
    telefones_bloco = {digits for digits in (_digits(phone) for phone in telefones) if digits}
    if not emails_bloco and not telefones_bloco:
        return False
    return emails_bloco <= _split_contatos(item.get("E-mail", "")) and telefones_bloco <= _telefones_do_resultado(item)


def _pagina_de_secretaria(url: str) -> bool:
    path = urlparse(str(url or "")).path.lower()
    normalized = path.rstrip("/") + "/"
    return "/secretaria/" in normalized or "/secretarias/" in normalized or "/secretarias-especiais/" in normalized


def _pagina_de_contatos(url: str) -> bool:
    path = urlparse(str(url or "")).path.lower().rstrip("/")
    return (
        path.endswith("/contato")
        or path.endswith("/contatos")
        or path.endswith("/fale-conosco")
        or path.endswith("/fale_conosco")
        or "/contato/" in path
        or "/contatos/" in path
        or "/fale-conosco/" in path
        or "/fale_conosco/" in path
    )


def _muitos_contatos_no_bloco(emails: list[str], telefones: list[str]) -> bool:
    return len(emails) + len(telefones) > 2


def _bloco_executivo_parece_manchete(bloco: str, cargo: str) -> bool:
    cargo_pattern = _cargo_pattern(normalize_for_search(cargo))
    original = str(bloco or "").strip()
    normalized = strip_accents(original).lower()
    match = re.match(rf"^{cargo_pattern}\s+(.+)$", normalized)
    if not match:
        return False
    tail = original[match.start(1) :].strip()
    found = NAME_PATTERN.match(tail)
    if not found or not _nome_valido(found.group(1)):
        return False
    return not bool(_nome_da_linha(tail))


def _bloco_tem_prefeito_explicito(bloco: str) -> bool:
    for line in _linhas_nao_vazias(bloco):
        normalized = normalize_for_search(line)
        if re.match(r"^(prefeito|prefeita)\s*($|[:\-\u2013\u2014])", normalized):
            return True
    return False


def _nome_agencia_desenvolvimento_valido(nome: str) -> bool:
    normalized = normalize_for_search(nome)
    return any(
        termo in normalized
        for termo in (
            "agencia de desenvolvimento",
            "sala do empreendedor",
            "casa do empreendedor",
            "banco do povo",
        )
    )


def _cargo_eh_agencia_desenvolvimento(cargo: str) -> bool:
    normalized = normalize_for_search(cargo)
    return "desenvolvimento" in normalized and ("agencia" in normalized or "sala" in normalized)


def _deduplicar_resultados(resultados: list[dict[str, str]]) -> list[dict[str, str]]:
    strong_keys = {
        (item.get("URL da fonte", ""), item.get(COL_CARGO_ORGAO, ""))
        for item in resultados
        if _registro_forte(item)
    }
    valid_name_keys = {
        (item.get("URL da fonte", ""), item.get(COL_CARGO_ORGAO, ""))
        for item in resultados
        if str(item.get("Nome", "")).strip() and _nome_valido(str(item.get("Nome", "")))
    }

    deduplicados: list[dict[str, str]] = []
    vistos: set[tuple[str, ...]] = set()
    for item in resultados:
        item = dict(item)
        key = (item.get("URL da fonte", ""), item.get(COL_CARGO_ORGAO, ""))
        if key in strong_keys and not _registro_forte(item):
            continue

        nome = str(item.get("Nome", "") or "").strip()
        if nome and not _nome_valido(nome):
            if not _tem_contato_resultado(item) or key in valid_name_keys:
                continue
            item["Nome"] = ""

        item_key = (
            item.get(COL_CARGO_ORGAO, ""),
            item.get("Nome", ""),
            item.get("E-mail", ""),
            item.get("Telefone", ""),
            item.get("Celular/WhatsApp", ""),
            item.get("URL da fonte", ""),
            item.get("Status", ""),
        )
        if item_key in vistos:
            continue
        vistos.add(item_key)
        deduplicados.append(item)
    return deduplicados


def _merge_contato_texto(atual: str, novo: str) -> str:
    partes = [part.strip() for part in str(atual or "").split(";") if part.strip()]
    for part in str(novo or "").split(";"):
        part = part.strip()
        if part and part not in partes:
            partes.append(part)
    return "; ".join(partes)


def _mesclar_resultados_complementares(resultados: list[dict[str, str]]) -> list[dict[str, str]]:
    mesclados: list[dict[str, str]] = []
    for item in resultados:
        cargo = item.get(COL_CARGO_ORGAO, "")
        url = item.get("URL da fonte", "")
        nome = item.get("Nome", "")
        destino = None
        for existente in mesclados:
            if existente.get(COL_CARGO_ORGAO, "") != cargo or existente.get("URL da fonte", "") != url:
                continue
            nome_existente = existente.get("Nome", "")
            if nome_existente and not nome and not _url_especifica_para_mescla(cargo, url):
                continue
            if not nome or not nome_existente or nome == nome_existente:
                destino = existente
                break
        if destino is None:
            mesclados.append(dict(item))
            continue

        if not destino.get("Nome") and nome:
            destino["Nome"] = nome
        for column in ("E-mail", "Telefone", "Celular/WhatsApp", "Celular"):
            destino[column] = _merge_contato_texto(destino.get(column, ""), item.get(column, ""))
        if _tem_contato_resultado(destino):
            destino["Status"] = "Encontrado"
            destino[COL_OBSERVACOES] = ""
        elif destino.get("Status") != "Encontrado":
            destino["Status"] = item.get("Status", destino.get("Status", "Parcial"))
            destino[COL_OBSERVACOES] = destino.get(COL_OBSERVACOES) or item.get(COL_OBSERVACOES, "")
    return mesclados


def _url_especifica_para_mescla(cargo: str, url: str) -> bool:
    path = normalize_for_search(urlparse(str(url or "")).path).replace("-", " ")
    cargo_norm = normalize_for_search(cargo).replace("-", " ")
    if cargo == "Prefeito":
        return "prefeito" in path and "vice prefeito" not in path
    if cargo == "Vice-prefeito":
        return "vice prefeito" in path
    if cargo == "Chefe de gabinete":
        return "chefe de gabinete" in path
    return cargo_norm and cargo_norm in path


def _url_raiz(url: str) -> bool:
    path = urlparse(str(url or "")).path.strip("/")
    return path in {"", "index.php", "index.html", "home", "portal"}


def _url_incompativel_com_cargo(cargo: str, url: str) -> bool:
    raw_url = normalize_for_search(str(url or ""))
    path = normalize_for_search(urlparse(str(url or "")).path).replace("_", "-").replace("/", " ")
    cargo_norm = normalize_for_search(cargo)
    if cargo != "Contato geral" and "carta-servicos" in path:
        return True
    if cargo != "Contato geral" and "cartaservicos" in path:
        return True
    if cargo != "Contato geral" and "legislacao" in path:
        return True
    if cargo != "Contato geral" and any(token in path for token in ("leis", "sileg")):
        return True
    if cargo != "Contato geral" and any(token in raw_url for token in ("download?type=txt", ".pdf")):
        return True
    if (
        cargo != "Contato geral"
        and any(token in path for token in ("servico", "servicos"))
        and "carta-de-servico orgao" not in path
        and not ("desenvolvimento" in cargo_norm and "desenvolvimento" in path)
    ):
        return True
    if cargo != "Contato geral" and "igrejinha.rs.gov.br" in raw_url and "secretarias.php" in raw_url:
        return True
    if cargo == "Prefeito" and "vice" in path and "prefeito-e-vice" not in path and "prefeitoevice" not in path:
        return True
    if cargo == "Prefeito" and ("chefe-de-gabinete" in path or "especialgabinete" in raw_url):
        return True
    if cargo == "Prefeito" and "contas-do-prefeito" in raw_url:
        return True
    if cargo == "Prefeito" and any(token in raw_url for token in ("/prefeitos", "cidade/prefeitos")):
        return True
    if cargo == "Vice-prefeito" and "primeira-dama" in path:
        return True
    if cargo == "Vice-prefeito" and "manaus.am.gov.br/prefeitura/prefeito" in raw_url:
        return True
    if cargo in CARGOS_EXECUTIVOS:
        if any(token in path for token in ("fale-com-o-prefeito", "contato", "assessor-de-imprensa")):
            return True
        if any(
            token in path or token in raw_url
            for token in (
                "cmei",
                "creche",
                "escola",
                "educacao",
                "estagio",
                "professor",
                "professora",
            )
        ):
            return True
        contexto_executivo = any(token in path for token in ("prefeito", "vice", "gabinete", "equipe", "gestores"))
        if any(token in path for token in ("assessor", "procuradoria")):
            return True
        if "assistencia" in path and not contexto_executivo:
            return True
        if "secretaria" in path and not contexto_executivo:
            return True
        if "secretaria.php" in raw_url and not contexto_executivo:
            return True
        if "secretarias.php" in raw_url and not contexto_executivo:
            return True
        if "secretariaview" in path and not contexto_executivo:
            return True
        if any(token in path for token in ("mobilidade", "pdu", "unidades")) and not contexto_executivo:
            return True
        if any(token in path for token in ("departamento index", "departamento view")) and not contexto_executivo:
            return True
        contexto_administrativo = any(token in path for token in ("administracao", "recursos-humanos", " rh", "rh "))
        if contexto_administrativo and not contexto_executivo:
            return True
    if "planejamento" in cargo_norm and "loanda.pr.gov.br" in raw_url and "secretariaview/?id=22" in raw_url:
        return True
    if (
        "planejamento" in cargo_norm
        and "planejamento" not in path
        and any(token in path for token in ("assistencia", "cultura", "educacao", "esporte", "saude", "sauacutede", "sauacutedep"))
    ):
        return True
    if (
        _cargo_eh_agencia_desenvolvimento(cargo)
        and any(token in path for token in ("gabinete", "prefeito", "vice"))
        and not any(token in path for token in ("banco-do-povo", "casa-do-empreendedor", "desenvolvimento", "empreendedor"))
    ):
        return True
    if (
        _cargo_eh_agencia_desenvolvimento(cargo)
        and not any(token in path for token in ("banco-do-povo", "casa-do-empreendedor", "desenvolvimento", "empreendedor"))
        and any(token in path for token in ("assistencia", "cultura", "educacao", "esporte", "financas", "saude", "sauacutede", "sauacutedep", "secretaria"))
    ):
        return True
    if (
        "desenvolvimento economico" in cargo_norm
        and "secretariaview" in path
        and not any(token in path for token in ("desenvolvimento", "industria", "comercio", "empreendedor", "trabalho"))
    ):
        return True
    if cargo_norm == "secretaria de desenvolvimento" and any(token in path for token in ("smmadu", "sdsh")):
        return True
    if (
        "desenvolvimento economico" in cargo_norm
        and not any(token in path for token in ("desenvolvimento", "industria", "comercio", "empreendedor", "trabalho"))
        and any(
        token in path
        for token in (
            "assistencia",
            "contabilidade",
            "cultura",
            "educacao",
            "esporte",
            "financas",
            "gabinete",
            "infraestrutura",
            "mulheres",
            "obras",
            "social",
            "viacao",
        )
    )
    ):
        return True
    if ("financas" in cargo_norm or "fazenda" in cargo_norm) and any(token in path for token in ("cultura", "esporte", "educacao")):
        return True
    return False


def _descartar_resultado_por_contexto(cargo: str, url: str, tem_contato: bool) -> bool:
    if _url_incompativel_com_cargo(cargo, url):
        return True
    path = normalize_for_search(urlparse(str(url or "")).path).replace("_", "-").replace("/", " ")
    if (
        _cargo_eh_agencia_desenvolvimento(cargo)
        and not tem_contato
        and not any(token in path for token in ("banco-do-povo", "casa-do-empreendedor", "desenvolvimento", "empreendedor"))
    ):
        return True
    return cargo != "Contato geral" and not tem_contato and _url_raiz(url)


def extrair_contatos_de_texto(
    texto: str,
    cargos_config: dict[str, list[str]] | None = None,
    url: str = "",
) -> list[dict[str, str]]:
    cargos_config = cargos_config or carregar_cargos()
    texto = _remover_secoes_ruidosas(texto)
    perfis_secretaria = extrair_perfis_secretaria(texto, cargos_config, url)
    perfis_secretaria.extend(extrair_perfis_lista_secretarias(texto, cargos_config, url))
    if perfis_secretaria:
        return _deduplicar_resultados(perfis_secretaria)

    estruturados = extrair_perfis_institucionais(texto, cargos_config, url)
    estruturados_fortes = [item for item in estruturados if _registro_forte(item)]
    executivos_fortes = [
        item
        for item in estruturados_fortes
        if item.get(COL_CARGO_ORGAO) in CARGOS_EXECUTIVOS
    ]
    cargos_executivos_fortes = {item.get(COL_CARGO_ORGAO, "") for item in executivos_fortes}
    resultados: list[dict[str, str]] = list(estruturados)

    for bloco in dividir_blocos(texto):
        emails = extrair_emails(bloco)
        telefones = extrair_telefones(bloco)
        celulares = [phone for phone in telefones if telefone_eh_celular(phone)]
        fixos = [phone for phone in telefones if phone not in celulares]
        cargos_detectados = detectar_cargos(bloco, cargos_config)
        if "Vice-prefeito" in cargos_detectados and "Prefeito" in cargos_detectados and not _bloco_tem_prefeito_explicito(bloco):
            cargos_detectados = [cargo for cargo in cargos_detectados if cargo != "Prefeito"]
        if cargos_detectados and _muitos_contatos_no_bloco(emails, telefones):
            cargos_detectados = []
        bloco_duplica_estruturado_forte = any(
            _resultado_cobre_todos_contatos(item, emails, telefones)
            for item in estruturados_fortes
        )
        bloco_duplica_executivo_forte = any(
            _resultado_cobre_todos_contatos(item, emails, telefones)
            for item in executivos_fortes
        )
        cargos = [
            cargo
            for cargo in cargos_detectados
            if not (
                cargo in CARGOS_EXECUTIVOS
                and (cargo in cargos_executivos_fortes or bloco_duplica_executivo_forte)
            )
        ]
        nome = extrair_nome_proximo(bloco, cargos_config) if cargos else ""
        if nome and _nome_aparece_apenas_em_linha_de_endereco(bloco, nome):
            nome = ""
        if nome and any(cargo not in CARGOS_EXECUTIVOS for cargo in cargos):
            if not _nome_veio_de_rotulo_ou_cargo(bloco, nome, cargos_config):
                nome = ""
        if not nome and any(cargo in CARGOS_EXECUTIVOS for cargo in cargos) and _bloco_de_unidade_subordinada(bloco):
            cargos = [cargo for cargo in cargos if cargo not in CARGOS_EXECUTIVOS]
        if not nome and any(cargo in CARGOS_EXECUTIVOS for cargo in cargos) and _contato_aparece_antes_do_cargo(bloco, cargos):
            cargos = [cargo for cargo in cargos if cargo not in CARGOS_EXECUTIVOS]
        if not nome and any(cargo in CARGOS_EXECUTIVOS for cargo in cargos):
            cargos = [
                cargo
                for cargo in cargos
                if cargo not in CARGOS_EXECUTIVOS or _bloco_tem_cargo_executivo_explicito(bloco, cargo, cargos_config)
            ]
            if not cargos:
                cargos_detectados = []
        if nome:
            trecho_nome = _trecho_a_partir_do_nome(bloco, nome)
            if not (extrair_emails(trecho_nome) or extrair_telefones(trecho_nome)):
                emails = []
                telefones = []
                celulares = []
                fixos = []
        if estruturados_fortes and cargos and not nome:
            continue
        if cargos:
            cargos_validos = [
                cargo
                for cargo in cargos
                if not (
                    cargo in CARGOS_EXECUTIVOS
                    and not nome
                    and _bloco_executivo_parece_manchete(bloco, cargo)
                )
            ]
            if cargos and not cargos_validos:
                cargos_detectados = []
            cargos = cargos_validos

        if cargos_detectados and not cargos:
            continue
        if not cargos and not cargos_detectados and (emails or telefones):
            if bloco_duplica_estruturado_forte:
                continue
            cargos = ["Contato geral"]

        if not cargos:
            continue

        tem_contato = bool(emails or fixos or celulares)
        if not tem_contato and not nome:
            continue

        for cargo in cargos:
            emails_cargo, fixos_cargo, celulares_cargo = _filtrar_contatos_por_cargo(
                cargo, bloco, emails, fixos, celulares
            )
            emails_cargo, fixos_cargo, celulares_cargo = _limitar_contatos_de_homepage(
                cargo, url, emails_cargo, fixos_cargo, celulares_cargo
            )
            if celulares_cargo:
                fixos_cargo = []
            if cargo != "Contato geral" and not nome and not emails_cargo and not celulares_cargo and fixos_cargo:
                fixos_cargo = []
            tem_contato_cargo = bool(emails_cargo or fixos_cargo or celulares_cargo)
            contato_geral = cargo == "Contato geral"
            if _descartar_resultado_por_contexto(cargo, url, tem_contato_cargo):
                continue
            if _cargo_eh_agencia_desenvolvimento(cargo) and nome and not _nome_agencia_desenvolvimento_valido(nome):
                nome = ""
            if _cargo_eh_agencia_desenvolvimento(cargo) and not nome:
                if not emails_cargo:
                    continue
                fixos_cargo = []
                celulares_cargo = []
                tem_contato_cargo = bool(emails_cargo)
            if (
                _cargo_eh_agencia_desenvolvimento(cargo)
                and nome
                and not tem_contato_cargo
                and not _nome_agencia_desenvolvimento_valido(nome)
            ):
                continue
            status = "Encontrado" if tem_contato_cargo and not contato_geral else "Parcial"
            observacoes = ""
            if contato_geral:
                observacoes = "Contato geral sem associação clara a cargo específico."
            elif not tem_contato_cargo:
                observacoes = "Cargo ou nome identificado, mas sem contato direto no mesmo bloco."

            resultados.append(_montar_resultado(cargo, nome, emails_cargo, fixos_cargo, celulares_cargo, url, status, observacoes))

    resultados = _deduplicar_resultados(_mesclar_resultados_complementares(resultados))
    if _pagina_de_secretaria(url) or _pagina_de_contatos(url):
        return [item for item in resultados if item.get(COL_CARGO_ORGAO) == "Contato geral"]
    return resultados


def extrair_contatos_paginas(
    paginas: Iterable[PaginaColetada],
    cargos_config: dict[str, list[str]] | None = None,
) -> list[dict[str, str]]:
    cargos_config = cargos_config or carregar_cargos()
    resultados: list[dict[str, str]] = []
    for pagina in paginas:
        resultados.extend(extrair_contatos_de_texto(pagina.texto, cargos_config, pagina.url))
    return resultados
