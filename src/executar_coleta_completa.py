from __future__ import annotations

import argparse
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd

from src.carregar_municipios import carregar_municipios
from src.filtrar_municipios import filtrar_municipios
from src.gerar_excel import gerar_excel
from src.main import executar_pipeline
from src.utils import project_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Executa a coleta completa por lotes de UF e consolida o Excel final.")
    parser.add_argument(
        "--input",
        dest="input_path",
        default=str(project_path("data", "input", "municipios_ibge_escopo_congelado_com_sites.csv")),
        help="Base congelada com sites oficiais preenchidos/revisados.",
    )
    parser.add_argument(
        "--output",
        dest="output_path",
        default=str(project_path("data", "output", "resultado_final_point_c_completo.xlsx")),
        help="Excel consolidado final.",
    )
    parser.add_argument(
        "--lotes-dir",
        dest="lotes_dir",
        default=str(project_path("data", "output", "lotes")),
        help="Diretório para Excel parcial de cada UF.",
    )
    parser.add_argument("--ufs", nargs="*", help="Lista opcional de UFs a processar.")
    parser.add_argument("--sem-playwright", action="store_true", help="Desativa uso opcional de Playwright nos lotes.")
    parser.add_argument("--sem-estaduais", action="store_true", help="Desativa fontes configuradas de governos estaduais.")
    parser.add_argument("--forcar", action="store_true", help="Reprocessa lotes mesmo que já existam.")
    parser.add_argument("--workers-ufs", type=int, default=1, help="Quantidade de UFs processadas em paralelo.")
    parser.add_argument("--chunk-size", type=int, default=0, help="Divide cada UF em partes menores com checkpoint.")
    return parser.parse_args()


def listar_ufs_no_escopo(input_path: str | Path) -> list[str]:
    municipios = carregar_municipios(input_path)
    filtrados = filtrar_municipios(municipios)
    return sorted(str(uf).upper() for uf in filtrados["UF"].dropna().unique() if str(uf).strip())


def lote_path(lotes_dir: str | Path, uf: str) -> Path:
    return Path(lotes_dir) / f"resultado_{str(uf).upper()}.xlsx"


def lote_concluido(path: str | Path) -> bool:
    file = Path(path)
    if not file.exists():
        return False
    try:
        sheets = pd.ExcelFile(file).sheet_names
    except Exception:
        return False
    return "Dados" in sheets or "Resultado consolidado" in sheets


def _args_lote(input_path: Path, output_path: Path, uf: str, sem_playwright: bool, sem_estaduais: bool) -> argparse.Namespace:
    return argparse.Namespace(
        input_path=str(input_path),
        output_path=str(output_path),
        dry_run=False,
        somente_filtrar=False,
        limite=None,
        uf=uf,
        municipio=None,
        sem_playwright=sem_playwright,
        sem_estaduais=sem_estaduais,
    )


def _executar_lote_subprocess(input_path: Path, output_path: Path, uf: str, sem_playwright: bool, sem_estaduais: bool) -> Path:
    cmd = [
        sys.executable,
        "-m",
        "src.main",
        "--input",
        str(input_path),
        "--output",
        str(output_path),
        "--uf",
        uf,
    ]
    if sem_playwright:
        cmd.append("--sem-playwright")
    if sem_estaduais:
        cmd.append("--sem-estaduais")

    log_path = output_path.with_suffix(".log")
    err_path = output_path.with_suffix(".err.log")
    with log_path.open("w", encoding="utf-8") as stdout, err_path.open("w", encoding="utf-8") as stderr:
        completed = subprocess.run(cmd, cwd=project_path(), stdout=stdout, stderr=stderr, text=True)
    if completed.returncode != 0:
        raise RuntimeError(f"Lote {uf} falhou com código {completed.returncode}. Veja {err_path}.")
    return output_path


def _read_base_chunks(input_path: Path) -> pd.DataFrame:
    if input_path.suffix.lower() in {".xlsx", ".xls"}:
        return pd.read_excel(input_path)
    return pd.read_csv(input_path, sep=None, engine="python")


def _uf_column(df: pd.DataFrame) -> str:
    for column in df.columns:
        if str(column).strip().lower() == "uf":
            return str(column)
    raise ValueError("Coluna UF não encontrada na base de entrada.")


def _chunk_paths(base_dir: Path, uf: str, index: int) -> tuple[Path, Path]:
    chunk_dir = base_dir / uf
    chunk_dir.mkdir(parents=True, exist_ok=True)
    return chunk_dir / f"input_{uf}_part{index:03d}.csv", chunk_dir / f"resultado_{uf}_part{index:03d}.xlsx"


def _executar_lote_em_chunks(
    input_path: Path,
    output_path: Path,
    uf: str,
    sem_playwright: bool,
    sem_estaduais: bool,
    chunk_size: int,
) -> Path:
    df = _read_base_chunks(input_path)
    uf_col = _uf_column(df)
    uf_df = df[df[uf_col].astype(str).str.upper() == uf.upper()].reset_index(drop=True)
    if uf_df.empty or len(uf_df) <= chunk_size:
        return _executar_lote_subprocess(input_path, output_path, uf, sem_playwright, sem_estaduais)

    chunks_base = output_path.parent / "chunks"
    chunk_outputs: list[Path] = []
    for start in range(0, len(uf_df), chunk_size):
        index = start // chunk_size + 1
        chunk_input, chunk_output = _chunk_paths(chunks_base, uf.upper(), index)
        chunk_outputs.append(chunk_output)
        if lote_concluido(chunk_output):
            continue
        uf_df.iloc[start : start + chunk_size].to_csv(chunk_input, index=False, encoding="utf-8")
        incluir_estadual_no_chunk = index == 1 and not sem_estaduais
        _executar_lote_subprocess(
            chunk_input,
            chunk_output,
            uf,
            sem_playwright,
            sem_estaduais=not incluir_estadual_no_chunk,
        )

    return consolidar_lotes(chunks_base / uf.upper(), output_path)


def _read_sheet(path: Path, preferred: str, fallback: str | None = None) -> pd.DataFrame:
    sheets = pd.ExcelFile(path).sheet_names
    if preferred in sheets:
        return pd.read_excel(path, sheet_name=preferred)
    if fallback and fallback in sheets:
        return pd.read_excel(path, sheet_name=fallback)
    return pd.DataFrame()


def consolidar_lotes(lotes_dir: str | Path, output_path: str | Path) -> Path:
    lote_files = sorted(Path(lotes_dir).glob("resultado_*.xlsx"))
    resultados: list[pd.DataFrame] = []
    municipios: list[pd.DataFrame] = []
    pendencias: list[pd.DataFrame] = []
    fontes_log: list[pd.DataFrame] = []

    for file in lote_files:
        if not lote_concluido(file):
            continue
        resultados.append(_read_sheet(file, "Dados", "Resultado consolidado"))
        municipios.append(_read_sheet(file, "Municípios pesquisados"))
        pendencias.append(_read_sheet(file, "Pendências"))
        fontes_log.append(_read_sheet(file, "Fontes e Log"))

    resultado_df = pd.concat(resultados, ignore_index=True) if resultados else pd.DataFrame()
    municipios_df = pd.concat(municipios, ignore_index=True) if municipios else pd.DataFrame()
    pendencias_df = pd.concat(pendencias, ignore_index=True) if pendencias else pd.DataFrame()
    fontes_df = pd.concat(fontes_log, ignore_index=True) if fontes_log else pd.DataFrame()

    return gerar_excel(resultado_df, municipios_df, pendencias_df, output_path, fontes_df)


def executar_coleta_completa(
    input_path: str | Path,
    output_path: str | Path,
    lotes_dir: str | Path,
    ufs: list[str] | None = None,
    sem_playwright: bool = False,
    sem_estaduais: bool = False,
    forcar: bool = False,
    workers_ufs: int = 1,
    chunk_size: int = 0,
) -> Path:
    input_file = Path(input_path)
    lotes_path = Path(lotes_dir)
    lotes_path.mkdir(parents=True, exist_ok=True)

    ufs_alvo = [uf.upper() for uf in (ufs or listar_ufs_no_escopo(input_file))]
    pendentes: list[tuple[str, Path]] = []
    for uf in ufs_alvo:
        partial = lote_path(lotes_path, uf)
        if not forcar and lote_concluido(partial):
            print(f"Lote {uf} já concluído, pulando: {partial}")
            continue
        pendentes.append((uf, partial))

    if workers_ufs <= 1:
        for uf, partial in pendentes:
            print(f"Executando lote {uf}: {partial}")
            executar_pipeline(_args_lote(input_file, partial, uf, sem_playwright, sem_estaduais))
    else:
        with ThreadPoolExecutor(max_workers=workers_ufs) as executor:
            futures = {
                executor.submit(
                    _executar_lote_em_chunks if chunk_size > 0 else _executar_lote_subprocess,
                    input_file,
                    partial,
                    uf,
                    sem_playwright,
                    sem_estaduais,
                    *([chunk_size] if chunk_size > 0 else []),
                ): (uf, partial)
                for uf, partial in pendentes
            }
            for future in as_completed(futures):
                uf, partial = futures[future]
                try:
                    future.result()
                    print(f"Lote {uf} concluído: {partial}")
                except Exception as exc:
                    print(f"Lote {uf} falhou: {exc}")
                    raise

    return consolidar_lotes(lotes_path, output_path)


def main() -> None:
    args = parse_args()
    output = executar_coleta_completa(
        args.input_path,
        args.output_path,
        args.lotes_dir,
        ufs=args.ufs,
        sem_playwright=args.sem_playwright,
        sem_estaduais=args.sem_estaduais,
        forcar=args.forcar,
        workers_ufs=args.workers_ufs,
        chunk_size=args.chunk_size,
    )
    print(f"Resultado completo consolidado: {output}")


if __name__ == "__main__":
    main()
