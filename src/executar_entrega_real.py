from __future__ import annotations

import argparse
from pathlib import Path

from src.executar_coleta_completa import executar_coleta_completa
from src.utils import project_path
from src.validar_fontes_oficiais import validar_planilha
from src.validar_resultados import auditar_planilha_final


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Executa coleta completa, auditoria e validacao rigorosa das fontes oficiais."
    )
    parser.add_argument(
        "--input",
        dest="input_path",
        default=str(project_path("data", "input", "municipios_ibge_escopo_congelado_com_sites.csv")),
        help="Base congelada com sites oficiais preenchidos/revisados.",
    )
    parser.add_argument(
        "--output",
        dest="output_path",
        default=str(project_path("data", "output", "resultado_final_revalidado_visualmente.xlsx")),
        help="Excel final consolidado.",
    )
    parser.add_argument(
        "--lotes-dir",
        dest="lotes_dir",
        default=str(project_path("data", "output", "lotes_revalidacao")),
        help="Diretorio de checkpoints por UF/chunk.",
    )
    parser.add_argument("--ufs", nargs="*", help="Lista opcional de UFs a processar.")
    parser.add_argument("--forcar", action="store_true", help="Reprocessa lotes ja existentes.")
    parser.add_argument("--workers-ufs", type=int, default=1, help="Quantidade de UFs em paralelo.")
    parser.add_argument("--chunk-size", type=int, default=10, help="Municipios por checkpoint dentro de cada UF.")
    parser.add_argument("--sem-estaduais", action="store_true", help="Desativa fontes estaduais configuradas.")
    parser.add_argument("--timeout-validacao", type=int, default=30, help="Timeout por URL na validacao.")
    parser.add_argument(
        "--validacao-output",
        default=str(project_path("data", "output", "validacao_fontes_revalidado_visualmente.xlsx")),
        help="Relatorio da validacao visual/estrutural.",
    )
    parser.add_argument(
        "--auditoria-output",
        default=str(project_path("data", "output", "auditoria_revalidado_visualmente.xlsx")),
        help="Relatorio da auditoria de completude.",
    )
    return parser.parse_args()


def executar(args: argparse.Namespace) -> Path:
    output = executar_coleta_completa(
        args.input_path,
        args.output_path,
        args.lotes_dir,
        ufs=args.ufs,
        sem_playwright=False,
        sem_estaduais=args.sem_estaduais,
        forcar=args.forcar,
        workers_ufs=args.workers_ufs,
        chunk_size=args.chunk_size,
    )

    auditoria = auditar_planilha_final(output, args.input_path)
    auditoria_path = Path(args.auditoria_output)
    auditoria_path.parent.mkdir(parents=True, exist_ok=True)
    auditoria.to_excel(auditoria_path, index=False)
    if not auditoria.empty:
        print(f"Auditoria encontrou {len(auditoria)} divergencia(s): {auditoria_path}")
        raise SystemExit(1)

    validacao = validar_planilha(output, max_linhas=0, timeout=args.timeout_validacao)
    validacao_path = Path(args.validacao_output)
    validacao_path.parent.mkdir(parents=True, exist_ok=True)
    validacao.to_excel(validacao_path, index=False)
    divergencias = validacao[validacao["Status validação"] == "Divergente"]
    nao_validados = validacao[validacao["Status validação"] == "Não validado"]
    if not divergencias.empty or not nao_validados.empty:
        print(
            "Validação encontrou "
            f"{len(divergencias)} divergencia(s) e {len(nao_validados)} fonte(s) nao validada(s): {validacao_path}"
        )
        raise SystemExit(1)

    print(f"Entrega real aprovada: {output}")
    print(f"Auditoria: {auditoria_path}")
    print(f"Validação: {validacao_path}")
    return output


def main() -> None:
    executar(parse_args())


if __name__ == "__main__":
    main()
