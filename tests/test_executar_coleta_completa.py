import pandas as pd

from src import executar_coleta_completa as completo
from src.gerar_excel import gerar_excel


def _criar_lote(path, uf, municipio):
    resultado = pd.DataFrame(
        [
            {
                "UF": uf,
                "Município/Capital": municipio,
                "Município": municipio,
                "Esfera": "Municipal",
                "Cargo/Área": "Contato geral",
                "Status": "Parcial",
                "URL da fonte": f"https://{municipio.lower()}.test/",
            }
        ]
    )
    municipios = pd.DataFrame(
        [
            {
                "UF": uf,
                "Município/Capital": municipio,
                "Município": municipio,
                "Esfera": "Municipal",
                "Status geral": "Parcial",
            }
        ]
    )
    gerar_excel(resultado, municipios, pd.DataFrame(), path)


def test_consolidar_lotes_une_planilhas_por_uf(tmp_path):
    lotes_dir = tmp_path / "lotes"
    lotes_dir.mkdir()
    _criar_lote(lotes_dir / "resultado_SP.xlsx", "SP", "Campinas")
    _criar_lote(lotes_dir / "resultado_RJ.xlsx", "RJ", "Niterói")

    output = completo.consolidar_lotes(lotes_dir, tmp_path / "final.xlsx")

    dados = pd.read_excel(output, sheet_name="Dados")
    assert set(dados["UF"]) == {"SP", "RJ"}
    assert len(dados) == 2


def test_executar_coleta_completa_retoma_lote_existente(tmp_path, monkeypatch):
    input_path = tmp_path / "municipios.csv"
    input_path.write_text(
        "municipio,uf,estado,populacao,capital,site_oficial\n"
        "Campinas,SP,São Paulo,1200000,false,https://campinas.sp.gov.br/\n"
        "Niterói,RJ,Rio de Janeiro,500000,false,https://niteroi.rj.gov.br/\n",
        encoding="utf-8",
    )
    lotes_dir = tmp_path / "lotes"
    lotes_dir.mkdir()
    _criar_lote(lotes_dir / "resultado_SP.xlsx", "SP", "Campinas")
    chamadas = []

    def fake_executar_pipeline(args):
        chamadas.append(args.uf)
        _criar_lote(args.output_path, args.uf, "Niterói")
        return args.output_path

    monkeypatch.setattr(completo, "executar_pipeline", fake_executar_pipeline)

    output = completo.executar_coleta_completa(
        input_path,
        tmp_path / "final.xlsx",
        lotes_dir,
        sem_playwright=True,
        sem_estaduais=True,
    )

    assert chamadas == ["RJ"]
    dados = pd.read_excel(output, sheet_name="Dados")
    assert set(dados["UF"]) == {"SP", "RJ"}
