"""Fotos protegidas: processamento no servidor, blur irreversível e controle de acesso."""
import hashlib
import io
import warnings
from uuid import UUID

from PIL import Image, ImageFilter, ImageOps, UnidentifiedImageError

from .cripto import Cifrador

MAX_BYTES = 5 * 1024 * 1024
MAX_FOTOS_POR_CONTA = 3
LADO_MAX = 1080
LADO_BORRADA = 360
FORMATOS_ACEITOS = {"JPEG", "PNG", "WEBP"}
# Proteção contra "bombas de descompressão" (arquivo pequeno que vira uma imagem gigante):
# checamos o tamanho declarado ANTES de decodificar os pixels.
MAX_PIXELS = 25_000_000
Image.MAX_IMAGE_PIXELS = MAX_PIXELS


class ImagemInvalida(ValueError):
    pass


def processar(dados: bytes) -> tuple[bytes, bytes, str]:
    """Devolve (nítida, borrada, sha256 da nítida), ambas em WebP e sem nenhum metadado.

    - Aplica a orientação do EXIF e depois descarta TODO o EXIF (inclui GPS, modelo do
      aparelho, data) copiando só os pixels para uma imagem nova.
    - A borrada nasce de uma miniatura de 24 px ampliada e desfocada: não há como
      reconstruir a original a partir dela.
    """
    if len(dados) > MAX_BYTES:
        raise ImagemInvalida("Imagem maior que 5 MB")
    try:
        with warnings.catch_warnings():
            # Entre 1x e 2x o limite o Pillow só avisa; aqui qualquer excesso é erro.
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            original = Image.open(io.BytesIO(dados))
        with original:
            if original.format not in FORMATOS_ACEITOS:
                raise ImagemInvalida("Formato não suportado (use JPEG, PNG ou WebP)")
            if original.width * original.height > MAX_PIXELS:
                raise ImagemInvalida("Resolução grande demais")
            imagem = ImageOps.exif_transpose(original).convert("RGB")
    except (UnidentifiedImageError, Image.DecompressionBombError, Image.DecompressionBombWarning, OSError) as e:
        raise ImagemInvalida("Arquivo de imagem inválido") from e

    imagem.thumbnail((LADO_MAX, LADO_MAX))
    limpa = Image.new("RGB", imagem.size)
    limpa.paste(imagem)

    miniatura = limpa.copy()
    miniatura.thumbnail((24, 24))
    escala = LADO_BORRADA / max(limpa.size)
    tamanho_borrada = (max(1, round(limpa.width * escala)), max(1, round(limpa.height * escala)))
    borrada = miniatura.resize(tamanho_borrada, Image.BILINEAR).filter(ImageFilter.GaussianBlur(12))

    nitida_bytes, borrada_bytes = _webp(limpa, 82), _webp(borrada, 60)
    return nitida_bytes, borrada_bytes, hashlib.sha256(nitida_bytes).hexdigest()


def _webp(imagem: Image.Image, qualidade: int) -> bytes:
    saida = io.BytesIO()
    imagem.save(saida, "WEBP", quality=qualidade)
    return saida.getvalue()


def _contexto(foto_id: UUID, versao: str) -> bytes:
    return f"foto|{versao}|".encode() + foto_id.bytes


# ---------- banco ----------

async def salvar(con, cifrador: Cifrador, conta: UUID, nitida: bytes, borrada: bytes, sha: str):
    """None se a conta já tem o máximo de fotos. Enviar a mesma foto de novo devolve a existente."""
    async with con.transaction():
        await con.execute("SELECT 1 FROM contas WHERE id = $1 FOR UPDATE", conta)  # serializa uploads da conta
        existente = await con.fetchrow("SELECT id, hash FROM fotos WHERE conta_id = $1 AND hash = $2", conta, sha)
        if existente:
            return existente
        if await con.fetchval("SELECT count(*) FROM fotos WHERE conta_id = $1", conta) >= MAX_FOTOS_POR_CONTA:
            return None
        foto_id = await con.fetchval("SELECT gen_random_uuid()")
        return await con.fetchrow(
            "INSERT INTO fotos (id, conta_id, hash, nitida, borrada) VALUES ($1, $2, $3, $4, $5) RETURNING id, hash",
            foto_id, conta, sha,
            cifrador.cifrar_bytes(nitida, _contexto(foto_id, "nitida")),
            cifrador.cifrar_bytes(borrada, _contexto(foto_id, "borrada")),
        )


async def listar_de(con, conta: UUID):
    return await con.fetch("SELECT id, hash, conta_id FROM fotos WHERE conta_id = $1 ORDER BY criado_em", conta)


async def listar_de_varias(con, contas: list[UUID]):
    return await con.fetch(
        "SELECT id, hash, conta_id FROM fotos WHERE conta_id = ANY($1::uuid[]) ORDER BY criado_em", contas
    )


async def apagar(con, conta: UUID, foto_id: UUID) -> bool:
    return await con.execute("DELETE FROM fotos WHERE id = $1 AND conta_id = $2", foto_id, conta) != "DELETE 0"


async def donos_que_liberaram(con, visualizador: UUID, donos: list[UUID]) -> set[UUID]:
    linhas = await con.fetch(
        """SELECT dono_id FROM acessos_fotos
           WHERE visualizador_id = $1 AND dono_id = ANY($2::uuid[]) AND status = 'aprovado'""",
        visualizador, donos,
    )
    return {l["dono_id"] for l in linhas}


async def ler_imagem(con, cifrador: Cifrador, foto_id: UUID, *, nitida: bool) -> bytes | None:
    coluna = "nitida" if nitida else "borrada"
    blob = await con.fetchval(f"SELECT {coluna} FROM fotos WHERE id = $1", foto_id)
    return None if blob is None else cifrador.decifrar_bytes(blob, _contexto(foto_id, coluna))


async def dono_da_foto(con, foto_id: UUID) -> UUID | None:
    return await con.fetchval("SELECT conta_id FROM fotos WHERE id = $1", foto_id)


async def solicitar(con, dono: UUID, visualizador: UUID) -> str:
    """Cria o pedido. Um pedido negado não pode ser refeito (evita insistência)."""
    return await con.fetchval(
        """INSERT INTO acessos_fotos (dono_id, visualizador_id) VALUES ($1, $2)
           ON CONFLICT (dono_id, visualizador_id) DO UPDATE SET status = acessos_fotos.status
           RETURNING status""",
        dono, visualizador,
    )


async def pendentes(con, dono: UUID):
    return await con.fetch(
        """SELECT a.visualizador_id, a.status, a.criado_em FROM acessos_fotos a
           JOIN contas c ON c.id = a.visualizador_id AND c.situacao = 'ativa'
           WHERE a.dono_id = $1 AND a.status = 'pendente' ORDER BY a.criado_em""",
        dono,
    )


async def responder(con, dono: UUID, visualizador: UUID, aprovar: bool) -> bool:
    """Aprova/nega um pedido, ou revoga (aprovar=False) um acesso já concedido."""
    status = await con.execute(
        """UPDATE acessos_fotos SET status = $3, respondido_em = now()
           WHERE dono_id = $1 AND visualizador_id = $2""",
        dono, visualizador, "aprovado" if aprovar else "negado",
    )
    return status != "UPDATE 0"
