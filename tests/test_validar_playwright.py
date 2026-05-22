from src import validar_playwright as modulo


def test_validar_playwright_registra_sucesso(monkeypatch):
    def fake_baixar(url, timeout):
        return "<html><body>Portal público</body></html>", "Encontrado", "", url, 200, "text/html", "playwright"

    monkeypatch.setattr(modulo, "_baixar_com_playwright", fake_baixar)

    result = modulo.validar_playwright("https://www.gov.br/", timeout=1)

    assert result["status"] == "Encontrado"
    assert result["http"] == 200
    assert result["gerou_texto"] is True


def test_validar_playwright_registra_indisponibilidade(monkeypatch):
    def fake_baixar(url, timeout):
        return "", "Necessita validação manual", "Playwright indisponível.", url, None, "", "playwright"

    monkeypatch.setattr(modulo, "_baixar_com_playwright", fake_baixar)

    result = modulo.validar_playwright("https://www.gov.br/", timeout=1)

    assert result["status"] == "Necessita validação manual"
    assert result["gerou_texto"] is False
    assert "indisponível" in result["observacoes"]
