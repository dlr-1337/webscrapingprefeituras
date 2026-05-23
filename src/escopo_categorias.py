from __future__ import annotations

from dataclasses import dataclass

from src.utils import normalize_for_search


FONTE_TERRITORIAL_URL = "https://sidra.ibge.gov.br/tabela/6579"


@dataclass(frozen=True, slots=True)
class CategoriaEscopo:
    label: str
    orgao_secretaria: str
    cargo_area: str


CATEGORIA_IDENTIFICACAO = CategoriaEscopo(
    label="Município/Capital e UF",
    orgao_secretaria="Município/Capital",
    cargo_area="Município/Capital e UF",
)

CATEGORIAS_DE_COLETA = (
    CategoriaEscopo("Prefeito", "Gabinete/Prefeitura", "Prefeito"),
    CategoriaEscopo("Vice-prefeito", "Gabinete/Prefeitura", "Vice-prefeito"),
    CategoriaEscopo("Chefe de gabinete", "Gabinete/Prefeitura", "Chefe de gabinete"),
    CategoriaEscopo(
        "Desenvolvimento econômico",
        "Secretaria de Desenvolvimento Econômico",
        "Desenvolvimento econômico",
    ),
    CategoriaEscopo("Desenvolvimento", "Secretaria de Desenvolvimento", "Desenvolvimento"),
    CategoriaEscopo("Finanças/Fazenda", "Secretaria de Finanças/Fazenda", "Finanças/Fazenda"),
    CategoriaEscopo("Planejamento", "Secretaria de Planejamento", "Planejamento"),
    CategoriaEscopo(
        "Agências municipais de desenvolvimento",
        "Agência municipal de desenvolvimento",
        "Agências municipais de desenvolvimento",
    ),
)

CATEGORIAS_OBRIGATORIAS = (CATEGORIA_IDENTIFICACAO, *CATEGORIAS_DE_COLETA)
CATEGORIAS_POR_LABEL = {categoria.label: categoria for categoria in CATEGORIAS_OBRIGATORIAS}


def labels_categorias_obrigatorias() -> list[str]:
    return [categoria.label for categoria in CATEGORIAS_OBRIGATORIAS]


def categoria_por_label(label: str) -> CategoriaEscopo:
    return CATEGORIAS_POR_LABEL[label]


def classificar_categoria_resultado(resultado: dict[str, object]) -> str:
    texto = normalize_for_search(
        " ".join(
            str(resultado.get(campo, ""))
            for campo in ("Cargo/Área", "Cargo/Órgão", "Órgão/Secretaria")
        )
    )
    texto_sem_hifen = texto.replace("-", " ")

    if not texto:
        return ""
    if "municipio/capital" in texto or "municipio capital" in texto_sem_hifen:
        return "Município/Capital e UF"
    if "vice prefeito" in texto_sem_hifen or "vice prefeita" in texto_sem_hifen:
        return "Vice-prefeito"
    if "chefe de gabinete" in texto:
        return "Chefe de gabinete"
    if "desenvolvimento economico" in texto:
        return "Desenvolvimento econômico"
    if "financas" in texto or "fazenda" in texto:
        return "Finanças/Fazenda"
    if "planejamento" in texto:
        return "Planejamento"
    if (
        ("agencia" in texto and "desenvolvimento" in texto)
        or "sala do empreendedor" in texto
        or "casa do empreendedor" in texto
        or "banco do povo" in texto
        or "agencia/sala de desenvolvimento" in texto
    ):
        return "Agências municipais de desenvolvimento"
    if "secretaria de desenvolvimento" in texto or texto == "desenvolvimento":
        return "Desenvolvimento"
    if "prefeito" in texto or "prefeita" in texto:
        return "Prefeito"
    return ""
