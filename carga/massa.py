"""Massa de teste para desenvolvimento: N pessoas variadas para a descoberta ter quem mostrar.

    DATABASE_URL=postgresql://matchmaking:matchmaking@localhost:5432/matchmaking AMBIENTE=dev \\
        python -m carga.massa 200 --curtir seu_apelido

Diferente de carga/semear.py (contas iguais, feitas para medir desempenho), aqui cada pessoa tem
apelido, bio, gênero, quem busca, interesses e cidade sorteados, como numa base de verdade. Todas
já têm termos aceitos e idade verificada; parte delas se curte entre si e, com --curtir, parte
já curtiu a sua conta (curtir de volta vira conexão na hora).

Proteção: só roda fora de produção e num banco desta máquina (localhost ou o contêiner "db" do
docker compose). Rodar de novo apaga e recria só as contas "massa_*".
"""

import asyncio
import os
import random
import sys
import time
import unicodedata
from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse
from uuid import UUID, uuid5

import asyncpg

from app.geo import codificar
from app.termos import VERSAO_ATUAL

PREFIXO = "massa_"
PROVEDOR = "massa"
_NAMESPACE = UUID("6f1c2a3e-0000-4000-8000-0000000a55a0")
HOSTS_LOCAIS = {"localhost", "127.0.0.1", "::1", "db"}

APELIDOS = [
    "Ana",
    "Bia",
    "Cadu",
    "Dani",
    "Duda",
    "Edu",
    "Fabi",
    "Fê",
    "Gabi",
    "Gui",
    "Helô",
    "Igor",
    "Isa",
    "Jader",
    "Jô",
    "Juju",
    "Kaká",
    "Léo",
    "Lia",
    "Lu",
    "Malu",
    "Mar",
    "Mel",
    "Nanda",
    "Nico",
    "Pati",
    "Pedro",
    "Rafa",
    "Rê",
    "Rick",
    "Sam",
    "Sol",
    "Tati",
    "Téo",
    "Thi",
    "Val",
    "Vic",
    "Yuri",
    "Zé",
    "Alê",
    "Bruno",
    "Caio",
    "Carol",
    "Clara",
    "Davi",
    "Elis",
    "Flor",
    "Hugo",
    "Ivy",
    "Jun",
    "Kim",
    "Lara",
    "Lipe",
    "Manu",
    "Noah",
    "Otto",
    "Paty",
    "Quel",
    "Rô",
    "Sasha",
    "Tom",
    "Vavá",
    "Will",
    "Yas",
    "Zoe",
    "Ariel",
    "Biel",
    "Cris",
]
CASAIS = ["Rafa & Bia", "Léo & Mar", "Gui & Lu", "Tati & Edu", "Sol & Kim", "Duda & Téo", "Vic & Sam"]

ABERTURAS = [
    "Gosto de conversa boa antes de qualquer coisa.",
    "Recém-chegada na cidade, quero conhecer gente nova.",
    "Discrição e respeito em primeiro lugar.",
    "Curioso(a) e sem pressa.",
    "Combinados claros, sem joguinho.",
    "Noturno(a), meio artista, meio nerd.",
    "Vida corrida, mas sempre arrumo tempo para o que vale a pena.",
    "Sou de poucas palavras aqui, prefiro conversar.",
    "Casal leve e bem resolvido.",
    "Explorando com calma o que me faz bem.",
]
GOSTOS = [
    "Café coado e vinil.",
    "Trilha no fim de semana.",
    "Cinema de rua e pipoca doce.",
    "Cozinho bem, juro.",
    "Viagens de última hora.",
    "Livros de ficção científica.",
    "Shows pequenos.",
    "Bar com mesa na calçada.",
    "Yoga de manhã, samba à noite.",
    "Séries até tarde.",
    "Fotografia analógica.",
    "Praia fora de temporada.",
]
FECHOS = [
    "Me chama!",
    "Se a afinidade bater, a gente conversa.",
    "Sem fotos de rosto por enquanto.",
    "Respondo com calma.",
    "Bora trocar ideia?",
    "",
    "",
]

# Cidades com peso (mais gente em SP): a descoberta mostra quem está perto e quem está longe.
CIDADES = [
    ("São Paulo", -23.55, -46.63, 0.25, 50),
    ("Rio de Janeiro", -22.91, -43.21, 0.15, 15),
    ("Belo Horizonte", -19.92, -43.94, 0.10, 8),
    ("Curitiba", -25.43, -49.27, 0.10, 7),
    ("Porto Alegre", -30.03, -51.23, 0.10, 6),
    ("Salvador", -12.97, -38.50, 0.10, 5),
    ("Recife", -8.05, -34.88, 0.08, 4),
    ("Brasília", -15.79, -47.88, 0.12, 5),
]


class DestinoProibido(Exception):
    pass


def conferir_destino(dsn: str, ambiente: str) -> str:
    """Devolve o nome do banco se for seguro criar a massa; senão levanta DestinoProibido."""
    if ambiente.strip().lower() in {"", "producao", "produção", "production", "prod"}:
        raise DestinoProibido("AMBIENTE precisa ser diferente de produção (ex.: AMBIENTE=dev)")
    url = urlparse(dsn)
    if (url.hostname or "") not in HOSTS_LOCAIS:
        raise DestinoProibido(f"o banco precisa ser local (localhost ou db), recebido: {url.hostname or 'vazio'}")
    nome = url.path.lstrip("/")
    if not nome:
        raise DestinoProibido("informe o nome do banco na DATABASE_URL")
    return nome


def id_da_pessoa(i: int) -> UUID:
    """Id estável: rodar de novo gera as mesmas pessoas."""
    return uuid5(_NAMESPACE, f"{PREFIXO}{i}")


def _slug(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return "".join(c for c in sem_acento.lower() if c.isalnum())[:14] or "pessoa"


def _bio(aleatorio: random.Random) -> str:
    partes = [
        aleatorio.choice(ABERTURAS),
        *aleatorio.sample(GOSTOS, k=aleatorio.randint(1, 2)),
        aleatorio.choice(FECHOS),
    ]
    return " ".join(p for p in partes if p)


def gerar_pessoas(n: int, generos: list[tuple[int, str]], tags: list[int], semente: int = 7) -> list[dict]:
    """Pessoas determinísticas (mesma semente, mesmo resultado) que respeitam as regras do banco."""
    if n < 2:
        raise ValueError("são precisas pelo menos 2 pessoas")
    if len(tags) < 4:
        raise ValueError("o catálogo precisa de pelo menos 4 interesses")
    aleatorio = random.Random(semente)  # noqa: S311 (dados de teste, não é segredo)
    ids_genero = [g for g, _ in generos]
    casal = next((g for g, slug in generos if slug == "casal"), None)
    pesos = [c[4] for c in CIDADES]
    agora = datetime.now(UTC)
    pessoas = []
    for i in range(n):
        genero = aleatorio.choice(ids_genero)
        nome = aleatorio.choice(CASAIS) if genero == casal else aleatorio.choice(APELIDOS)
        busca = sorted(aleatorio.sample(ids_genero, k=aleatorio.randint(1, min(3, len(ids_genero)))))
        k = min(len(tags), aleatorio.randint(4, 9))
        escolhidas = aleatorio.sample(tags, k=k)
        n_quero = max(1, round(k * 0.5))
        n_curioso = max(1, round(k * 0.3))
        sem_local = aleatorio.random() < 0.15
        cidade = aleatorio.choices(CIDADES, weights=pesos)[0]
        lat = cidade[1] + aleatorio.uniform(-cidade[3], cidade[3])
        lon = cidade[2] + aleatorio.uniform(-cidade[3], cidade[3])
        pessoas.append(
            {
                "id": id_da_pessoa(i),
                "handle": f"{PREFIXO}{_slug(nome)}_{i:03d}"[:30],
                "nome": nome,
                "bio": _bio(aleatorio) if aleatorio.random() < 0.85 else None,
                "genero_id": genero,
                "busca_por": busca,
                "tags_quero": sorted(escolhidas[:n_quero]),
                "tags_curioso": sorted(escolhidas[n_quero : n_quero + n_curioso]),
                "tags_limite": sorted(escolhidas[n_quero + n_curioso :]),
                "geohash": None if sem_local else codificar(lat, lon),
                "lat": None if sem_local else round(lat, 2),
                "lon": None if sem_local else round(lon, 2),
                "distancia_max_km": aleatorio.choice([None, 10, 25, 50, 100, 300]),
                "visivel": aleatorio.random() < 0.95,
                "ativo_em": agora - timedelta(minutes=aleatorio.randint(0, 30 * 24 * 60)),
            }
        )
    return pessoas


def gerar_curtidas(pessoas: list[dict], semente: int = 7, alvo: UUID | None = None) -> list[tuple[UUID, UUID]]:
    """Curtidas entre a massa (0 a 6 por pessoa) e, com `alvo`, ~40% já curtiram essa conta."""
    aleatorio = random.Random(semente + 1)  # noqa: S311
    ids = [p["id"] for p in pessoas]
    curtidas = set()
    for de in ids:
        for para in aleatorio.sample(ids, k=min(len(ids), aleatorio.randint(0, 6))):
            if para != de:
                curtidas.add((de, para))
    if alvo is not None:
        curtidas.update((de, alvo) for de in ids if de != alvo and aleatorio.random() < 0.4)
    return sorted(curtidas)


async def criar_massa(dsn: str, n: int, curtir: str | None = None) -> dict:
    con = await asyncpg.connect(dsn)
    try:
        generos = [(r["id"], r["slug"]) for r in await con.fetch("SELECT id, slug FROM generos ORDER BY id")]
        tags = [r["id"] for r in await con.fetch("SELECT id FROM tags ORDER BY id")]
        colunas_perfis = {
            r["column_name"]
            for r in await con.fetch("SELECT column_name FROM information_schema.columns WHERE table_name = 'perfis'")
        }
        alvo = None
        if curtir:
            alvo = await con.fetchval("SELECT id FROM contas WHERE handle = $1", curtir.strip().lower())
            if alvo is None:
                raise DestinoProibido(f"não existe conta com o apelido '{curtir}'")
        pessoas = gerar_pessoas(n, generos, tags)
        curtidas = gerar_curtidas(pessoas, alvo=alvo)
        agora = datetime.now(UTC)
        async with con.transaction():
            await con.execute("DELETE FROM contas WHERE handle LIKE 'massa\\_%'")
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
                records=[(p["id"], p["handle"], agora, agora, VERSAO_ATUAL, agora, agora, PROVEDOR) for p in pessoas],
            )
            colunas = [
                "conta_id",
                "nome_exibicao",
                "bio",
                "genero_id",
                "busca_por",
                "tags_quero",
                "tags_curioso",
                "tags_limite",
                "geohash",
                "lat_aprox",
                "lon_aprox",
                "visivel",
                "ativo_em",
            ]
            chaves = [
                "id",
                "nome",
                "bio",
                "genero_id",
                "busca_por",
                "tags_quero",
                "tags_curioso",
                "tags_limite",
                "geohash",
                "lat",
                "lon",
                "visivel",
                "ativo_em",
            ]
            if "distancia_max_km" in colunas_perfis:
                colunas.append("distancia_max_km")
                chaves.append("distancia_max_km")
            await con.copy_records_to_table(
                "perfis",
                columns=colunas,
                records=[tuple(p[k] for k in chaves) for p in pessoas],
            )
            await con.copy_records_to_table("curtidas", columns=["de_id", "para_id"], records=curtidas)
        await con.execute("ANALYZE contas; ANALYZE perfis; ANALYZE curtidas")
        conexoes = await con.fetchval(
            """SELECT count(*) FROM curtidas a JOIN curtidas b ON a.de_id = b.para_id AND a.para_id = b.de_id
               WHERE a.de_id < a.para_id AND a.de_id IN (SELECT id FROM contas WHERE handle LIKE 'massa\\_%')"""
        )
    finally:
        await con.close()
    return {
        "pessoas": n,
        "curtidas": len(curtidas),
        "conexoes": conexoes,
        "curtiram_voce": sum(1 for _, para in curtidas if para == alvo) if alvo else 0,
    }


def main(argv: list[str]) -> int:
    args = argv[1:]
    curtir = None
    if "--curtir" in args:
        i = args.index("--curtir")
        curtir = args[i + 1] if i + 1 < len(args) else None
        args = args[:i] + args[i + 2 :]
    n = int(args[0]) if args else 200
    dsn = os.environ["DATABASE_URL"]
    try:
        banco = conferir_destino(dsn, os.environ.get("AMBIENTE", "producao"))
        inicio = time.monotonic()
        r = asyncio.run(criar_massa(dsn, n, curtir))
    except DestinoProibido as e:
        print(f"Recusado: {e}", file=sys.stderr)
        return 2
    extra = f"; {r['curtiram_voce']} já curtiram @{curtir}" if curtir else ""
    print(
        f"{r['pessoas']} pessoas em {banco} ({r['curtidas']} curtidas, {r['conexoes']} conexões entre elas{extra})"
        f" em {time.monotonic() - inicio:.1f}s"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
