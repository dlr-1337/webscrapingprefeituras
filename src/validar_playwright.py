from __future__ import annotations

import argparse
from datetime import datetime

from src.coletar_paginas import _baixar_com_playwright, html_para_texto


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Valida o fallback Playwright em uma URL real sem bloquear a coleta.")
    parser.add_argument("--url", default="https://www.gov.br/", help="URL pública para teste operacional.")
    parser.add_argument("--timeout", type=int, default=20, help="Timeout em segundos.")
    return parser.parse_args()


def validar_playwright(url: str, timeout: int = 20) -> dict[str, object]:
    html, status, observacoes, final_url, status_http, content_type, metodo = _baixar_com_playwright(url, timeout)
    texto = html_para_texto(html)
    return {
        "url": url,
        "url_final": final_url,
        "status": status,
        "http": status_http,
        "content_type": content_type,
        "metodo": metodo,
        "gerou_texto": bool(texto),
        "observacoes": observacoes,
        "data_hora": datetime.now().isoformat(timespec="seconds"),
    }


def main() -> None:
    args = parse_args()
    result = validar_playwright(args.url, args.timeout)
    print(f"URL: {result['url']}")
    print(f"URL final: {result['url_final']}")
    print(f"Status: {result['status']}")
    print(f"HTTP: {result['http']}")
    print(f"Método: {result['metodo']}")
    print(f"Gerou texto: {'Sim' if result['gerou_texto'] else 'Não'}")
    print(f"Observações: {result['observacoes']}")


if __name__ == "__main__":
    main()
