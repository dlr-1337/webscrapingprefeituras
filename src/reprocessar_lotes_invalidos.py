from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import unicodedata
from pathlib import Path

import pandas as pd

from src.executar_coleta_completa import consolidar_lotes
from src.extrair_contatos import _nome_valido, _url_incompativel_com_cargo
from src.main import _nome_representa_localidade


def _norm(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii")
    return text.lower().strip()


def _colmap(df: pd.DataFrame) -> dict[str, str]:
    return {_norm(column): column for column in df.columns}


def _cell(row: pd.Series, column: str) -> str:
    value = row.get(column, "")
    return "" if pd.isna(value) else str(value).strip()


def _hard_url_incompatibility(url: str) -> bool:
    normalized = _norm(url)
    return any(
        token in normalized
        for token in (
            ".pdf",
            "carta servicos",
            "download type txt",
            "educacao",
            "departamento index",
            "departamento view",
            "leis municipais",
            "manaus.am.gov.br/prefeitura/prefeito",
            "mobilidade",
            "pdu",
            "unidades",
            "/prefeitos",
            "cidade/prefeitos",
        )
    )


def _invalid_rows(workbook: Path) -> list[dict[str, object]]:
    df = pd.read_excel(workbook, sheet_name="Dados")
    cols = _colmap(df)
    rows: list[dict[str, object]] = []

    for index, row in df.iterrows():
        cargo = _cell(row, cols["cargo/area"])
        status = _norm(_cell(row, cols["status"]))
        if _norm(cargo) == "municipio/capital e uf" or status not in {"encontrado", "parcial"}:
            continue

        nome = _cell(row, cols["nome"])
        url = _cell(row, cols["url da fonte"])
        tem_dado_publicado = any(
            _cell(row, cols[campo])
            for campo in ("nome", "e-mail", "telefone", "celular/whatsapp", "celular")
            if campo in cols
        )
        reasons: list[str] = []

        if not tem_dado_publicado:
            reasons.append("sem_dado_publicado")
        if nome and not _nome_valido(nome):
            reasons.append("nome_invalido")
        if nome and _nome_representa_localidade(nome, row):
            reasons.append("localidade")
        if _url_incompativel_com_cargo(cargo, url) and (reasons or _hard_url_incompatibility(url)):
            reasons.append("url_incompativel")

        if reasons:
            rows.append(
                {
                    "row": index + 2,
                    "uf": _cell(row, cols["uf"]).upper(),
                    "municipio": _cell(row, cols["municipio/capital"]),
                    "cargo": cargo,
                    "status": _cell(row, cols["status"]),
                    "nome": nome,
                    "url": url,
                    "reasons": reasons,
                }
            )
    return rows


def _output_for_input(path: Path) -> Path:
    if path.parent.parent.name == "chunks":
        return path.with_name(path.name.replace("input_", "resultado_").replace(".csv", ".xlsx"))
    uf = path.stem.split("_")[-1].upper()
    return Path("data/output/lotes_revalidacao") / f"resultado_{uf}.xlsx"


def _input_has_target(path: Path, targets: set[tuple[str, str]]) -> bool:
    try:
        df = pd.read_csv(path)
    except Exception:
        return False
    cols = _colmap(df)
    uf_col = cols.get("uf")
    municipio_col = cols.get("municipio") or cols.get("municipio/capital")
    if not uf_col or not municipio_col:
        return False
    return any((str(row[uf_col]).upper(), _norm(row[municipio_col])) in targets for _, row in df.iterrows())


def _select_inputs(invalid_rows: list[dict[str, object]], lotes_dir: Path) -> list[Path]:
    targets = {(str(row["uf"]).upper(), _norm(row["municipio"])) for row in invalid_rows}
    return _select_inputs_for_targets(targets, lotes_dir)


def _select_inputs_for_targets(targets: set[tuple[str, str]], lotes_dir: Path) -> list[Path]:
    ufs_with_chunks = {path.parent.name.upper() for path in (lotes_dir / "chunks").glob("*/input_*.csv")}
    selected: set[Path] = set()

    for path in sorted(lotes_dir.glob("**/input*.csv")):
        if "inputs_validacao_uf" in path.parts:
            uf = path.stem.split("_")[-1].upper()
            if uf in ufs_with_chunks or (lotes_dir / f"input_{uf}.csv").exists():
                continue
        if _input_has_target(path, targets):
            selected.add(path)

    return sorted(selected)


def _run_jobs(jobs: list[Path], log_dir: Path, max_parallel: int) -> list[dict[str, object]]:
    queue = list(jobs)
    running: list[dict[str, object]] = []
    failures: list[dict[str, object]] = []
    completed = 0
    total = len(jobs)
    index = 0

    while queue or running:
        while queue and len(running) < max_parallel:
            input_path = queue.pop(0)
            output_path = _output_for_input(input_path)
            index += 1
            log_base = log_dir / f"{index:03d}_{input_path.stem}"
            stdout = open(f"{log_base}.out", "w", encoding="utf-8")
            stderr = open(f"{log_base}.err", "w", encoding="utf-8")
            cmd = [
                sys.executable,
                "-m",
                "src.main",
                "--input",
                str(input_path),
                "--output",
                str(output_path),
                "--sem-estaduais",
            ]
            print(f"START {index}/{total} {input_path} -> {output_path}", flush=True)
            proc = subprocess.Popen(cmd, stdout=stdout, stderr=stderr)
            running.append(
                {
                    "index": index,
                    "input": input_path,
                    "process": proc,
                    "stdout": stdout,
                    "stderr": stderr,
                }
            )

        time.sleep(5)
        still_running: list[dict[str, object]] = []
        for item in running:
            proc = item["process"]
            assert isinstance(proc, subprocess.Popen)
            return_code = proc.poll()
            if return_code is None:
                still_running.append(item)
                continue

            item["stdout"].close()
            item["stderr"].close()
            if return_code == 0:
                completed += 1
                print(f"DONE {item['index']} {item['input']}", flush=True)
            else:
                failures.append({"input": str(item["input"]), "return_code": return_code})
                print(f"FAILED {item['index']} rc={return_code} {item['input']}", flush=True)

        running = still_running
        print(f"PROGRESS done={completed} failed={len(failures)} running={len(running)} queued={len(queue)}", flush=True)

    return failures


def _consolidate(jobs: list[Path], lotes_dir: Path, final_workbook: Path) -> None:
    ufs: set[str] = set()
    for job in jobs:
        if job.parent.parent.name == "chunks":
            ufs.add(job.parent.name.upper())
        else:
            ufs.add(job.stem.split("_")[-1].upper())

    for uf in sorted(ufs):
        chunk_dir = lotes_dir / "chunks" / uf
        if chunk_dir.exists():
            consolidar_lotes(chunk_dir, lotes_dir / f"resultado_{uf}.xlsx", sem_estaduais=True)
            print(f"CONSOLIDATED_UF {uf}", flush=True)

    consolidar_lotes(lotes_dir, final_workbook, sem_estaduais=True)
    print("CONSOLIDATED_FINAL", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Reprocessa lotes com nomes institucionais falsos ja detectados.")
    parser.add_argument("--workbook", default="data/output/resultado_final_revalidado_visualmente.xlsx")
    parser.add_argument("--lotes-dir", default="data/output/lotes_revalidacao")
    parser.add_argument("--log-dir", required=True)
    parser.add_argument("--max-parallel", type=int, default=4)
    parser.add_argument(
        "--target",
        action="append",
        default=[],
        metavar="UF:MUNICIPIO",
        help="Municipio adicional para reprocessar, mesmo sem invalidez semantica detectada.",
    )
    parser.add_argument(
        "--targets-csv",
        help="CSV com colunas uf e municipio para reprocessar; se houver site_inferido, usa apenas linhas preenchidas.",
    )
    args = parser.parse_args()

    workbook = Path(args.workbook)
    lotes_dir = Path(args.lotes_dir)
    log_dir = Path(args.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    invalid_rows = _invalid_rows(workbook)
    extra_targets: set[tuple[str, str]] = set()
    for target in args.target:
        if ":" not in target:
            raise SystemExit(f"Alvo invalido: {target}. Use UF:Municipio.")
        uf, municipio = target.split(":", 1)
        extra_targets.add((uf.strip().upper(), _norm(municipio)))
    if args.targets_csv:
        targets_df = pd.read_csv(args.targets_csv)
        cols = _colmap(targets_df)
        uf_col = cols.get("uf")
        municipio_col = cols.get("municipio") or cols.get("municipio/capital")
        site_col = cols.get("site_inferido")
        if not uf_col or not municipio_col:
            raise SystemExit("--targets-csv precisa ter colunas uf e municipio.")
        for _, row in targets_df.iterrows():
            if site_col and not _cell(row, site_col):
                continue
            extra_targets.add((str(row[uf_col]).strip().upper(), _norm(row[municipio_col])))

    jobs = sorted(set(_select_inputs(invalid_rows, lotes_dir)) | set(_select_inputs_for_targets(extra_targets, lotes_dir)))
    (log_dir / "invalid_rows.json").write_text(json.dumps(invalid_rows, ensure_ascii=False, indent=2), encoding="utf-8")
    (log_dir / "extra_targets.json").write_text(
        json.dumps(sorted([{"uf": uf, "municipio_norm": municipio} for uf, municipio in extra_targets], key=lambda item: (item["uf"], item["municipio_norm"])), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (log_dir / "jobs.json").write_text(json.dumps([str(job) for job in jobs], ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"INVALID_ROWS {len(invalid_rows)}", flush=True)
    print(f"JOBS {len(jobs)}", flush=True)
    for job in jobs:
        print(f"JOB {job}", flush=True)

    failures = _run_jobs(jobs, log_dir, args.max_parallel)
    (log_dir / "failed.json").write_text(json.dumps(failures, ensure_ascii=False, indent=2), encoding="utf-8")
    if failures:
        print(f"FAILED_TOTAL {len(failures)}", flush=True)
        return 1

    _consolidate(jobs, lotes_dir, workbook)
    print("REPROCESS_COMPLETE", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
