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


def _criar_lote_com_estadual(path):
    resultado = pd.DataFrame(
        [
            {
                "UF": "SP",
                "Município/Capital": "Campinas",
                "Município": "Campinas",
                "Esfera": "Municipal",
                "Cargo/Área": "Município/Capital e UF",
                "Status": "Encontrado",
                "URL da fonte": "https://campinas.sp.gov.br/",
            },
            {
                "UF": "SP",
                "Município/Capital": "Governo do Estado de São Paulo",
                "Município": "Governo do Estado de São Paulo",
                "Esfera": "Estadual",
                "Cargo/Área": "Município/Capital e UF",
                "Status": "Encontrado",
                "URL da fonte": "https://www.saopaulo.sp.gov.br/",
            },
        ]
    )
    municipios = pd.DataFrame(
        [
            {
                "UF": "SP",
                "Município/Capital": "Campinas",
                "Município": "Campinas",
                "Esfera": "Municipal",
                "Status geral": "Encontrado",
            },
            {
                "UF": "SP",
                "Município/Capital": "Governo do Estado de São Paulo",
                "Município": "Governo do Estado de São Paulo",
                "Esfera": "Estadual",
                "Status geral": "Encontrado",
            },
        ]
    )
    fontes = pd.DataFrame(
        [
            {
                "UF": "SP",
                "Município/Capital": "Campinas",
                "Município": "Campinas",
                "Esfera": "Municipal",
                "URL consultada": "https://campinas.sp.gov.br/",
            },
            {
                "UF": "SP",
                "Município/Capital": "Governo do Estado de São Paulo",
                "Município": "Governo do Estado de São Paulo",
                "Esfera": "Estadual",
                "URL consultada": "https://www.saopaulo.sp.gov.br/",
            },
        ]
    )
    gerar_excel(resultado, municipios, pd.DataFrame(), path, fontes)


def test_consolidar_lotes_une_planilhas_por_uf(tmp_path):
    lotes_dir = tmp_path / "lotes"
    lotes_dir.mkdir()
    _criar_lote(lotes_dir / "resultado_SP.xlsx", "SP", "Campinas")
    _criar_lote(lotes_dir / "resultado_RJ.xlsx", "RJ", "Niterói")

    output = completo.consolidar_lotes(lotes_dir, tmp_path / "final.xlsx")

    dados = pd.read_excel(output, sheet_name="Dados")
    assert set(dados["UF"]) == {"SP", "RJ"}
    assert len(dados) == 2


def test_consolidar_lotes_sem_estaduais_filtra_checkpoints_antigos(tmp_path):
    lotes_dir = tmp_path / "lotes"
    lotes_dir.mkdir()
    _criar_lote_com_estadual(lotes_dir / "resultado_SP.xlsx")

    output = completo.consolidar_lotes(lotes_dir, tmp_path / "final.xlsx", sem_estaduais=True)

    for sheet in ("Dados", "Municípios pesquisados", "Fontes e Log"):
        dados = pd.read_excel(output, sheet_name=sheet)
        assert set(dados["Esfera"].dropna()) == {"Municipal"}


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


def test_chunk_size_funciona_em_execucao_sequencial(tmp_path, monkeypatch):
    input_path = tmp_path / "municipios.csv"
    input_path.write_text(
        "municipio,uf,estado,populacao,capital,site_oficial\n"
        "Campinas,SP,Sao Paulo,1200000,false,https://campinas.sp.gov.br/\n"
        "Limeira,SP,Sao Paulo,300000,false,https://limeira.sp.gov.br/\n",
        encoding="utf-8",
    )
    lotes_dir = tmp_path / "lotes"
    chamadas = []

    def fake_executar_lote_em_chunks(
        input_file,
        output_path,
        uf,
        sem_playwright,
        sem_estaduais,
        chunk_size,
        forcar=False,
        sem_busca_web_sites=False,
    ):
        chamadas.append((uf, chunk_size, forcar))
        _criar_lote(output_path, uf, "Campinas")
        return output_path

    monkeypatch.setattr(completo, "_executar_lote_em_chunks", fake_executar_lote_em_chunks)

    output = completo.executar_coleta_completa(
        input_path,
        tmp_path / "final.xlsx",
        lotes_dir,
        sem_playwright=True,
        sem_estaduais=True,
        workers_ufs=1,
        chunk_size=1,
    )

    assert chamadas == [("SP", 1, False)]
    dados = pd.read_excel(output, sheet_name="Dados")
    assert set(dados["UF"]) == {"SP"}


def test_forcar_reprocessa_chunks_existentes(tmp_path, monkeypatch):
    input_path = tmp_path / "municipios.csv"
    input_path.write_text(
        "municipio,uf,estado,populacao,capital,site_oficial\n"
        "Campinas,SP,Sao Paulo,1200000,false,https://campinas.sp.gov.br/\n"
        "Limeira,SP,Sao Paulo,300000,false,https://limeira.sp.gov.br/\n",
        encoding="utf-8",
    )
    output_path = tmp_path / "lotes" / "resultado_SP.xlsx"
    chunks_dir = output_path.parent / "chunks" / "SP"
    chunks_dir.mkdir(parents=True)
    _criar_lote(chunks_dir / "resultado_SP_part001.xlsx", "SP", "Antigo1")
    _criar_lote(chunks_dir / "resultado_SP_part002.xlsx", "SP", "Antigo2")
    _criar_lote(chunks_dir / "resultado_SP_part003.xlsx", "SP", "Antigo3")
    chamadas = []

    def fake_executar_lote_subprocess(
        input_file,
        chunk_output,
        uf,
        sem_playwright,
        sem_estaduais,
        sem_busca_web_sites=False,
    ):
        chamadas.append(chunk_output.name)
        _criar_lote(chunk_output, uf, chunk_output.stem)
        return chunk_output

    monkeypatch.setattr(completo, "_executar_lote_subprocess", fake_executar_lote_subprocess)

    output = completo._executar_lote_em_chunks(
        input_path,
        output_path,
        "SP",
        sem_playwright=True,
        sem_estaduais=True,
        chunk_size=1,
        forcar=True,
    )

    assert chamadas == ["resultado_SP_part001.xlsx", "resultado_SP_part002.xlsx"]
    dados = pd.read_excel(output, sheet_name="Dados")
    assert set(dados["Município"]) == {"resultado_SP_part001", "resultado_SP_part002"}
