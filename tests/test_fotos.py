import io

from PIL import Image

from app import fotos


def _jpeg_com_gps(tamanho=(800, 600), cor=(200, 30, 90)) -> bytes:
    img = Image.new("RGB", tamanho, cor)
    for x in range(0, tamanho[0], 20):  # detalhe para a versão borrada ter o que perder
        for y in range(tamanho[1]):
            img.putpixel((x, y), (255, 255, 255))
    exif = Image.Exif()
    exif[0x010F] = "FabricanteDoCelular"  # Make
    exif[0x8825] = {1: "S", 2: (23.0, 33.0, 1.8), 3: "W", 4: (46.0, 38.0, 0.0)}  # GPSInfo
    saida = io.BytesIO()
    img.save(saida, "JPEG", exif=exif)
    return saida.getvalue()


def _enviar(p, dados, tipo="image/jpeg"):
    return p.post("/api/fotos", content=dados, headers={"Content-Type": tipo})


def test_processamento_remove_metadados_e_borra():
    original = _jpeg_com_gps()
    assert b"FabricanteDoCelular" in original
    nitida, borrada, sha = fotos.processar(original)
    for versao in (nitida, borrada):
        img = Image.open(io.BytesIO(versao))
        assert img.format == "WEBP" and not img.getexif() and b"FabricanteDoCelular" not in versao
    assert max(Image.open(io.BytesIO(borrada)).size) == fotos.LADO_BORRADA
    assert len(sha) == 64


def test_rejeita_arquivos_invalidos(pessoa):
    p = pessoa()
    assert _enviar(p, b"nao sou imagem").status_code == 422
    assert _enviar(p, b"GIF89a", "image/gif").status_code == 415
    grande = Image.new("RGB", (6000, 5000))  # 30 MP > limite
    saida = io.BytesIO()
    grande.save(saida, "PNG")
    assert _enviar(p, saida.getvalue(), "image/png").status_code == 422


def test_limite_de_fotos_e_duplicata(pessoa):
    p = pessoa()
    ids = [_enviar(p, _jpeg_com_gps(cor=(i * 40, 0, 0))).json()["id"] for i in range(3)]
    assert len(set(ids)) == 3
    assert _enviar(p, _jpeg_com_gps(cor=(0, 0, 255))).status_code == 409
    # Reenviar uma foto que já existe devolve a mesma (idempotente pelo hash)
    assert _enviar(p, _jpeg_com_gps(cor=(0, 0, 0))).json()["id"] == ids[0]
    assert p.delete(f"/api/fotos/{ids[0]}").status_code == 204
    assert len(p.get("/api/fotos").json()) == 2


def test_foto_cifrada_no_banco(pessoa, db):
    p = pessoa()
    foto = _enviar(p, _jpeg_com_gps()).json()
    nitida, borrada = db.fetchrow("SELECT nitida, borrada FROM fotos WHERE id = $1::uuid", foto["id"])
    assert not nitida.startswith(b"RIFF") and not borrada.startswith(b"RIFF")  # RIFF = cabeçalho WebP


def test_nitida_so_com_autorizacao_do_dono(pessoa):
    dono = pessoa("mulher-cis", ["homem-cis"], quero=["latex"])
    curioso = pessoa("homem-cis", ["mulher-cis"], quero=["latex"])
    foto = _enviar(dono, _jpeg_com_gps()).json()
    url = foto["url"]

    nitida = dono.get(url).content
    borrada = curioso.get(url).content
    assert nitida != borrada and len(borrada) < len(nitida)
    assert curioso.get(f"/api/perfis/{dono.id}/fotos").json()[0]["nitida"] is False

    # O visualizador só consegue PEDIR; não há como se autoaprovar
    assert curioso.post(f"/api/perfis/{dono.id}/fotos/solicitar").json() == {"status": "pendente"}
    assert curioso.post(f"/api/fotos/solicitacoes/{dono.id}", json={"aprovar": True}).status_code == 404
    assert curioso.get(url).content == borrada

    [pedido] = dono.get("/api/fotos/solicitacoes").json()
    assert pedido["visualizador"]["id"] == curioso.id
    assert dono.post(f"/api/fotos/solicitacoes/{curioso.id}", json={"aprovar": True}).status_code == 204
    assert curioso.get(url).content == nitida
    card = next(c for c in curioso.get("/api/descobrir").json() if c["perfil"]["id"] == dono.id)
    assert card["fotos"][0]["nitida"] is True

    # Revogar volta a entregar só a borrada, e um pedido negado não pode ser refeito
    dono.post(f"/api/fotos/solicitacoes/{curioso.id}", json={"aprovar": False})
    assert curioso.get(url).content == borrada
    assert curioso.post(f"/api/perfis/{dono.id}/fotos/solicitar").json() == {"status": "negado"}


def test_bloqueio_esconde_ate_a_borrada(pessoa):
    dono = pessoa()
    outro = pessoa()
    url = _enviar(dono, _jpeg_com_gps()).json()["url"]
    dono.post(f"/api/perfis/{outro.id}/bloquear")
    assert outro.get(url).status_code == 404
    r = dono.get(url)
    assert r.headers["cache-control"].startswith("no-store") and r.headers["content-type"] == "image/webp"
