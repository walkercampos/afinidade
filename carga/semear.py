"""Popula um banco SÓ PARA TESTE DE CARGA com N contas prontas para usar o app.

    DATABASE_URL=postgresql://.../afinidade_carga JWT_SECRET=... python -m carga.semear 30000

Cada conta já tem termos aceitos, idade verificada, perfil e localização na Grande São Paulo;
as contas 2k e 2k+1 são uma conexão (curtida mútua), para o chat funcionar. Os tokens de sessão
vão para carga/.tokens.json (fora do git), que o k6 lê.

Proteção: só roda fora de produção e num banco cujo nome termina em "_carga". Nunca aponte
para um banco com pessoas de verdade.
"""

import asyncio
import json
import os
import random
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse
from uuid import UUID, uuid5

import asyncpg

from app.geo import codificar
from app.security import emitir_token
from app.termos import VERSAO_ATUAL

ARQUIVO_TOKENS = Path(__file__).resolve().parent / ".tokens.json"
PROVEDOR_CARGA = "carga"
PREFIXO = "carga_"
_NAMESPACE = UUID("6f1c2a3e-0000-4000-8000-00000000ca76")
# Grande São Paulo, aproximado: o bastante para todo mundo ter gente perto na descoberta.
LAT, LON, RAIO_GRAUS = -23.55, -46.63, 0.35


class DestinoProibido(Exception):
    pass


def conferir_destino(dsn: str, ambiente: str) -> str:
    """Devolve o nome do banco se for seguro semear; senão levanta DestinoProibido."""
    if ambiente.strip().lower() in {"", "producao", "produção", "production", "prod"}:
        raise DestinoProibido("AMBIENTE precisa ser diferente de produção (ex.: AMBIENTE=dev)")
    nome = urlparse(dsn).path.lstrip("/")
    if not nome.endswith("_carga"):
        raise DestinoProibido(f"o banco precisa terminar em '_carga' (recebido: {nome or 'vazio'})")
    return nome


def id_da_conta(i: int) -> UUID:
    """Id estável: rodar de novo gera as mesmas contas."""
    return uuid5(_NAMESPACE, f"{PREFIXO}{i}")


def par_de(i: int) -> int:
    """A conexão de cada conta: 0↔1, 2↔3, ... A última de um total ímpar fica sem par (-1)."""
    return i + 1 if i % 2 == 0 else i - 1


def gerar_contas(n: int, generos: list[int], tags: list[int], semente: int = 42) -> list[dict]:
    """Contas e perfis determinísticos (mesma semente, mesmo resultado)."""
    if n < 2:
        raise ValueError("são precisas pelo menos 2 contas")
    aleatorio = random.Random(semente)  # noqa: S311 (dados de teste, não é segredo)
    contas = []
    for i in range(n):
        lat = LAT + aleatorio.uniform(-RAIO_GRAUS, RAIO_GRAUS)
        lon = LON + aleatorio.uniform(-RAIO_GRAUS, RAIO_GRAUS)
        embaralhadas = aleatorio.sample(tags, k=min(6, len(tags)))
        contas.append(
            {
                "id": id_da_conta(i),
                "handle": f"{PREFIXO}{i:06d}",
                "genero_id": aleatorio.choice(generos),
                # Busca por todos os gêneros: maximiza candidatos, o pior caso para a descoberta.
                "busca_por": list(generos),
                "tags_quero": sorted(embaralhadas[:3]),
                "tags_curioso": sorted(embaralhadas[3:5]),
                "tags_limite": sorted(embaralhadas[5:6]),
                "geohash": codificar(lat, lon),
                "lat": round(lat, 2),
                "lon": round(lon, 2),
                "par": par_de(i) if par_de(i) < n else -1,
            }
        )
    return contas


async def semear(dsn: str, segredo: str, n: int, expira_min: int = 24 * 60) -> dict:
    con = await asyncpg.connect(dsn)
    try:
        generos = [r["id"] for r in await con.fetch("SELECT id FROM generos ORDER BY id")]
        tags = [r["id"] for r in await con.fetch("SELECT id FROM tags ORDER BY id")]
        contas = gerar_contas(n, generos, tags)
        async with con.transaction():
            await con.execute("DELETE FROM contas WHERE handle LIKE 'carga\\_%'")
            agora = datetime.now(UTC)
            await con.copy_records_to_table(
                "contas",
                columns=[
                    "id",
                    "handle",
                    "adulto_confirmado_em",
                    "consentimento_em",
                    "termos_versao",
                    "termos_aceitos_em",
                    "idade_verificada_em",
                    "idade_provedor",
                ],
                records=[
                    (c["id"], c["handle"], agora, agora, VERSAO_ATUAL, agora, agora, PROVEDOR_CARGA) for c in contas
                ],
            )
            await con.copy_records_to_table(
                "perfis",
                columns=[
                    "conta_id",
                    "nome_exibicao",
                    "genero_id",
                    "busca_por",
                    "tags_quero",
                    "tags_curioso",
                    "tags_limite",
                    "geohash",
                    "lat_aprox",
                    "lon_aprox",
                ],
                records=[
                    (
                        c["id"],
                        f"Pessoa {i}",
                        c["genero_id"],
                        c["busca_por"],
                        c["tags_quero"],
                        c["tags_curioso"],
                        c["tags_limite"],
                        c["geohash"],
                        c["lat"],
                        c["lon"],
                    )
                    for i, c in enumerate(contas)
                ],
            )
            curtidas = [(c["id"], contas[c["par"]]["id"]) for c in contas if c["par"] >= 0]
            await con.copy_records_to_table("curtidas", columns=["de_id", "para_id"], records=curtidas)
        await con.execute("ANALYZE contas; ANALYZE perfis; ANALYZE curtidas")
    finally:
        await con.close()

    usuarios = [
        {
            "token": emitir_token(c["id"], 0, segredo, expira_min),
            "par": str(contas[c["par"]]["id"]) if c["par"] >= 0 else None,
        }
        for c in contas
    ]
    return {"total": n, "usuarios": usuarios}


def main(argv: list[str]) -> int:
    n = int(argv[1]) if len(argv) > 1 else 30_000
    dsn = os.environ["DATABASE_URL"]
    try:
        banco = conferir_destino(dsn, os.environ.get("AMBIENTE", "producao"))
    except DestinoProibido as e:
        print(f"Recusado: {e}", file=sys.stderr)
        return 2
    inicio = time.monotonic()
    dados = asyncio.run(semear(dsn, os.environ["JWT_SECRET"], n))
    ARQUIVO_TOKENS.write_text(json.dumps(dados))
    ARQUIVO_TOKENS.chmod(0o600)
    print(f"{n} contas em {banco} em {time.monotonic() - inicio:.1f}s; tokens em {ARQUIVO_TOKENS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
