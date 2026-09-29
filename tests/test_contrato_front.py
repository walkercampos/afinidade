"""Contrato front ↔ API: toda chamada que o front faz existe na API, com o mesmo método.

Ideia do full-stack-fastapi-template (cliente gerado a partir do OpenAPI), adaptada a um front
sem build: em vez de gerar o cliente, conferimos que o front não chama rotas que não existem
(ou que mudaram de nome/método). Pega front e back desencontrados antes do deploy.
"""

import re
from pathlib import Path

JS = Path(__file__).resolve().parent.parent / "static" / "js"

# api("/caminho", { metodo: "POST" ... }) · fetch(`/api/caminho...`) · new WebSocket(`.../api/ws`)
_API = re.compile(r"""api\(\s*[`"'](/[^`"']*)[`"']\s*(?:,\s*\{([^}]*)\})?""")
_FETCH = re.compile(r"""fetch\(\s*[`"']/api(/[^`"'?]*)[^`"']*[`"']\s*(?:,\s*\{([^}]*)\})?""")


def _metodo(opcoes: str | None, chave: str) -> str:
    m = re.search(chave + r"""\s*:\s*["'](\w+)["']""", opcoes or "")
    return (m.group(1) if m else "GET").upper()


def _chamadas_do_front() -> set[tuple[str, str]]:
    chamadas = set()
    for arquivo in JS.rglob("*.js"):
        codigo = arquivo.read_text()
        for caminho, opcoes in _API.findall(codigo):
            chamadas.add((_metodo(opcoes, "metodo"), caminho))
        for caminho, opcoes in _FETCH.findall(codigo):
            chamadas.add((_metodo(opcoes, "method"), caminho))
    return chamadas


def _como_regex(caminho_openapi: str) -> re.Pattern:
    return re.compile("^" + re.sub(r"\\\{[^}]+\\\}", "[^/]+", re.escape(caminho_openapi)) + "$")


def test_toda_chamada_do_front_existe_na_api(client):
    rotas = [
        (metodo.upper(), _como_regex(caminho.removeprefix("/api")))
        for caminho, metodos in client.app.openapi()["paths"].items()
        for metodo in metodos
    ]
    chamadas = _chamadas_do_front()
    assert len(chamadas) > 30, "o leitor de chamadas parou de encontrar o código do front"

    def normalizar(caminho: str) -> str:
        # `${x}` vira um segmento qualquer; a query string não faz parte da rota
        return re.sub(r"\$\{[^}]+\}", "X", caminho).split("?")[0]

    faltando = sorted(
        f"{metodo} {caminho}"
        for metodo, caminho in chamadas
        if not any(m == metodo and padrao.match(normalizar(caminho)) for m, padrao in rotas)
    )
    assert faltando == [], f"o front chama rotas que a API não tem: {faltando}"
