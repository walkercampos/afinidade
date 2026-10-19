// Perfil: pedidos para ver as fotos, fotos, localização aproximada e o formulário de interesses.
import { Camera, Check, EyeOff, MapPin, Plus, Trash2 } from "lucide-react";
import { type FormEvent, useEffect, useRef, useState } from "react";
import { useAvisos } from "../componentes/avisos";
import { AreaTexto, Avatar, Botao, CabecalhoTela, CarregandoTela, Campo, Cartao, Interruptor, Nota, Seletor, TituloSecao } from "../componentes/ui";
import { api, type Catalogo, carregarCatalogo, ErroApi } from "../lib/api";
import { irPara } from "../lib/roteador";
import type { Foto, ItemCatalogo, PerfilProprio, SolicitacaoAcesso, TagsInteresses } from "../lib/tipos";
import { useCarregar } from "../lib/useCarregar";
import { distanciaDoIndice, indiceDaDistancia, juntarClasses, nomeDaCategoria, PARADAS_DISTANCIA, rotuloDistancia } from "../lib/util";

type Nivel = keyof TagsInteresses;
const NIVEIS: [Nivel, string, string][] = [
  ["quero", "Quero", "border-ok bg-ok-suave text-ok"],
  ["curioso", "Curioso", "border-violeta bg-violeta-suave text-violeta"],
  ["limite_absoluto", "Limite", "border-perigo bg-perigo/10 text-perigo"],
];
const MAX_FOTOS = 3;


function SecaoPedidos() {
  const { avisar } = useAvisos();
  const { dados: pedidos, setDados } = useCarregar(() => api<SolicitacaoAcesso[]>("/fotos/solicitacoes"));
  if (!pedidos?.length) return null;

  async function responder(id: string, aprovar: boolean) {
    await api(`/fotos/solicitacoes/${id}`, { metodo: "POST", corpo: { aprovar } });
    setDados(pedidos!.filter((p) => p.visualizador.id !== id));
    avisar(aprovar ? "Acesso liberado" : "Pedido negado");
  }

  return (
    <Cartao className="border-acento/40">
      <TituloSecao>Pedidos para ver suas fotos</TituloSecao>
      <ul className="space-y-3">
        {pedidos.map(({ visualizador: v }) => (
          <li key={v.id} className="flex items-center gap-3">
            <Avatar nome={v.nome_exibicao} tamanho={40} />
            <span className="flex-1 font-medium">{v.nome_exibicao}</span>
            <Botao pequeno variante="secundario" onClick={() => responder(v.id, false)}>Negar</Botao>
            <Botao pequeno onClick={() => responder(v.id, true)}>Aprovar</Botao>
          </li>
        ))}
      </ul>
    </Cartao>
  );
}

function SecaoFotos() {
  const { avisar, confirmar } = useAvisos();
  const { dados: fotos, recarregar } = useCarregar(() => api<Foto[]>("/fotos"));
  const arquivo = useRef<HTMLInputElement>(null);
  const [enviando, setEnviando] = useState(false);

  async function enviar(f: File | undefined) {
    if (!f) return;
    setEnviando(true);
    try { await api("/fotos", { metodo: "POST", arquivo: f }); avisar("Foto enviada"); } catch (e) { avisar((e as Error).message); }
    setEnviando(false);
    if (arquivo.current) arquivo.current.value = "";
    recarregar();
  }

  async function remover(id: string) {
    if (!(await confirmar({ titulo: "Remover esta foto?", texto: "Ela some do seu perfil na hora.", confirmar: "Remover", perigo: true }))) return;
    await api(`/fotos/${id}`, { metodo: "DELETE" });
    recarregar();
  }

  return (
    <Cartao>
      <TituloSecao>Suas fotos</TituloSecao>
      <div className="grid grid-cols-3 gap-2.5">
        {Array.from({ length: MAX_FOTOS }, (_, i) => {
          const f = fotos?.[i];
          if (f) {
            return (
              <div key={f.id} className="group relative aspect-[3/4] overflow-hidden rounded-2xl bg-superficie-2">
                <img src={f.url} alt={`Sua foto ${i + 1}`} className="size-full object-cover" />
                <button type="button" aria-label="Remover foto" onClick={() => remover(f.id)}
                  className="absolute right-1.5 top-1.5 flex size-8 items-center justify-center rounded-full bg-black/55 text-white backdrop-blur transition hover:bg-black/75">
                  <Trash2 className="size-4" />
                </button>
              </div>
            );
          }
          const proxima = i === (fotos?.length ?? 0);
          return (
            <button key={`vazio-${i}`} type="button" disabled={!proxima || enviando} onClick={() => arquivo.current?.click()}
              aria-label="Adicionar foto"
              className="flex aspect-[3/4] flex-col items-center justify-center gap-1 rounded-2xl border-2 border-dashed border-borda text-suave transition hover:border-acento hover:text-acento-texto disabled:opacity-40">
              {proxima ? <Plus className="size-6" /> : <Camera className="size-5" />}
              {proxima && <span className="text-xs font-medium">{enviando ? "Enviando…" : "Adicionar"}</span>}
            </button>
          );
        })}
      </div>
      <input ref={arquivo} type="file" accept="image/jpeg,image/png,image/webp" hidden onChange={(e) => enviar(e.target.files?.[0])} />
      <Nota className="mt-3">
        Localização, modelo do celular e outros dados escondidos na foto são apagados no envio. Quem você não autorizar vê só uma versão borrada.
      </Nota>
    </Cartao>
  );
}

function SecaoLocalizacao({ perfil, aoMudar }: { perfil: PerfilProprio; aoMudar: () => void }) {
  const { avisar } = useAvisos();
  const ativa = Boolean(perfil.localizacao.regiao);
  const [indice, setIndice] = useState(indiceDaDistancia(perfil.localizacao.distancia_max_km));
  const [buscando, setBuscando] = useState(false);
  const valor = distanciaDoIndice(indice);

  async function salvarDistancia() {
    await api("/perfil/distancia", { metodo: "PUT", corpo: { distancia_max_km: valor } });
    avisar(`Distância salva: ${rotuloDistancia(valor).toLowerCase()}`);
  }

  function usarLocalizacao() {
    if (!navigator.geolocation) return avisar("Seu navegador não oferece localização.");
    setBuscando(true);
    navigator.geolocation.getCurrentPosition(async ({ coords }) => {
      try {
        await api("/perfil/localizacao", { metodo: "PUT", corpo: { lat: coords.latitude, lon: coords.longitude, distancia_max_km: valor } });
        avisar("Localização aproximada salva");
        aoMudar();
      } finally { setBuscando(false); }
    }, () => { setBuscando(false); avisar("Não foi possível obter a localização."); }, { enableHighAccuracy: false, maximumAge: 600000 });
  }

  return (
    <Cartao>
      <TituloSecao acao={ativa && <span className="inline-flex items-center gap-1 rounded-full bg-ok-suave px-2.5 py-1 text-xs font-semibold text-ok"><Check className="size-3.5" />Ativa</span>}>
        Localização
      </TituloSecao>
      <Nota>O app guarda só um quadrado de ~5 km; sua posição exata é descartada. Os outros veem apenas “até N km”.</Nota>
      <div className={juntarClasses("mt-5", !ativa && "opacity-50")}>
        <div className="mb-2 flex items-baseline justify-between">
          <label htmlFor="distancia" className="text-sm font-medium">Distância máxima</label>
          <output htmlFor="distancia" className="text-sm font-semibold text-acento-texto">{rotuloDistancia(valor)}</output>
        </div>
        <input id="distancia" type="range" min={0} max={PARADAS_DISTANCIA.length - 1} step={1} value={indice} disabled={!ativa}
          aria-valuetext={rotuloDistancia(valor)}
          onChange={(e) => setIndice(Number(e.target.value))} onPointerUp={salvarDistancia} onKeyUp={salvarDistancia}
          className="w-full accent-[var(--acento)]" />
        <Nota className="mt-1">
          {ativa ? "Vale para os dois lados: quem escolheu um raio menor também decide." : "Ative a localização para escolher uma distância."}
        </Nota>
      </div>
      <div className="mt-5 flex gap-2">
        {ativa && (
          <Botao variante="secundario" onClick={async () => { await api("/perfil/localizacao", { metodo: "DELETE" }); aoMudar(); }}>Remover</Botao>
        )}
        <Botao className="flex-1" icone={<MapPin className="size-4" />} carregando={buscando} onClick={usarLocalizacao}>
          {ativa ? "Atualizar minha região" : "Usar minha localização"}
        </Botao>
      </div>
    </Cartao>
  );
}

/** Para cada interesse, um de três níveis (ou nenhum). Os limites nunca aparecem para ninguém. */
function SeletorInteresses({ tags, valor, aoMudar }: { tags: ItemCatalogo[]; valor: Map<string, Nivel>; aoMudar: (m: Map<string, Nivel>) => void }) {
  const grupos = new Map<string, ItemCatalogo[]>();
  for (const t of tags) {
    const g = nomeDaCategoria(t.categoria);
    grupos.set(g, [...(grupos.get(g) ?? []), t]);
  }
  const alternar = (slug: string, nivel: Nivel) => {
    const novo = new Map(valor);
    if (novo.get(slug) === nivel) novo.delete(slug); else novo.set(slug, nivel);
    aoMudar(novo);
  };
  return (
    <div className="space-y-6">
      {[...grupos].map(([grupo, itens]) => (
        <div key={grupo}>
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-suave">{grupo}</h3>
          <ul className="divide-y divide-borda">
            {itens.map((t) => (
              <li key={t.slug} className="flex flex-wrap items-center justify-between gap-x-3 gap-y-2 py-2.5">
                <span className="text-[15px]">{t.rotulo}</span>
                <span className="flex gap-1.5" role="group" aria-label={t.rotulo}>
                  {NIVEIS.map(([nivel, texto, cores]) => {
                    const ativo = valor.get(t.slug) === nivel;
                    return (
                      <button key={nivel} type="button" aria-pressed={ativo} onClick={() => alternar(t.slug, nivel)}
                        className={juntarClasses(
                          "min-h-9 rounded-full border px-3 text-xs font-semibold transition",
                          ativo ? cores : "border-borda text-suave hover:text-texto",
                        )}>
                        {texto}
                      </button>
                    );
                  })}
                </span>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}

function FormPerfil({ catalogo, atual, aoSalvar }: { catalogo: Catalogo; atual: PerfilProprio | null; aoSalvar: () => void }) {
  const { avisar } = useAvisos();
  const [nome, setNome] = useState(atual?.nome_exibicao ?? "");
  const [bio, setBio] = useState(atual?.bio ?? "");
  const [genero, setGenero] = useState(atual?.genero ?? "");
  const [busca, setBusca] = useState<string[]>(atual?.busca_por ?? []);
  const [visivel, setVisivel] = useState(atual ? atual.visivel : true);
  const [niveis, setNiveis] = useState(() => {
    const m = new Map<string, Nivel>();
    if (atual) for (const [nivel] of NIVEIS) for (const s of atual.tags_interesses[nivel]) m.set(s, nivel);
    return m;
  });
  const [salvando, setSalvando] = useState(false);

  async function salvar(e: FormEvent) {
    e.preventDefault();
    if (!busca.length) return avisar("Escolha pelo menos um gênero que você busca.");
    const tags: TagsInteresses = { quero: [], curioso: [], limite_absoluto: [] };
    for (const [slug, nivel] of niveis) tags[nivel].push(slug);
    setSalvando(true);
    try {
      await api("/perfil", { metodo: "PUT", corpo: { nome_exibicao: nome, bio: bio || null, genero, busca_por: busca, tags_interesses: tags, visivel } });
      avisar("Perfil salvo");
      aoSalvar();
    } catch (e) { avisar((e as Error).message); } finally { setSalvando(false); }
  }

  return (
    <form onSubmit={salvar} className="space-y-4">
      <Cartao className="space-y-4">
        <TituloSecao>Sobre você</TituloSecao>
        <Campo rotulo="Nome de exibição" required maxLength={40} value={nome} onChange={(e) => setNome(e.target.value)} />
        <AreaTexto rotulo="Bio" maxLength={500} value={bio} onChange={(e) => setBio(e.target.value)}
          dica="Evite o que identifique você: nome real, local de trabalho, @ de outras redes." />
        <Seletor rotulo="Seu gênero" required value={genero} onChange={(e) => setGenero(e.target.value)}>
          <option value="">Selecione…</option>
          {catalogo.generos.map((g) => <option key={g.slug} value={g.slug}>{g.rotulo}</option>)}
        </Seletor>
        <fieldset>
          <legend className="mb-2 text-sm font-medium">Você busca</legend>
          <div className="flex flex-wrap gap-2">
            {catalogo.generos.map((g) => {
              const ativo = busca.includes(g.slug);
              return (
                <button key={g.slug} type="button" aria-pressed={ativo}
                  onClick={() => setBusca(ativo ? busca.filter((s) => s !== g.slug) : [...busca, g.slug])}
                  className={juntarClasses(
                    "inline-flex min-h-10 items-center gap-1.5 rounded-full border px-4 text-sm font-medium transition",
                    ativo ? "border-acento bg-acento-suave text-acento-texto" : "border-borda hover:bg-superficie-2",
                  )}>
                  {ativo && <Check className="size-4" />}{g.rotulo}
                </button>
              );
            })}
          </div>
        </fieldset>
      </Cartao>

      <Cartao>
        <TituloSecao>Interesses</TituloSecao>
        <Nota className="mb-4">
          <strong className="text-ok">Quero</strong> = pratica e gosta · <strong className="text-violeta">Curioso</strong> = aberto(a) a explorar ·{" "}
          <strong className="text-perigo">Limite</strong> = nunca. Seus limites não aparecem para ninguém: servem só para esconder pessoas incompatíveis.
        </Nota>
        <SeletorInteresses tags={catalogo.tags} valor={niveis} aoMudar={setNiveis} />
      </Cartao>

      <Cartao>
        <Interruptor rotulo="Perfil visível na descoberta" ligado={visivel} aoMudar={setVisivel}
          descricao={visivel ? "Outras pessoas podem encontrar você." : <span className="inline-flex items-center gap-1"><EyeOff className="size-3.5" /> Ninguém novo vê você agora.</span>} />
      </Cartao>

      <div className="sticky bottom-[88px] z-10 md:bottom-4">
        <Botao type="submit" cheio carregando={salvando} className="shadow-xl">{atual ? "Salvar perfil" : "Criar perfil"}</Botao>
      </div>
    </form>
  );
}

export function TelaPerfil() {
  const { dados, erro, recarregar } = useCarregar(async () => {
    const catalogo = await carregarCatalogo();
    let perfil: PerfilProprio | null = null;
    try { perfil = await api<PerfilProprio>("/perfil"); } catch (e) { if (!(e instanceof ErroApi && e.status === 404)) throw e; }
    return { catalogo, perfil };
  });
  const [chave, setChave] = useState(0);
  useEffect(() => { if (dados) setChave((c) => c + 1); }, [dados]);

  if (erro) return <Nota>{erro}</Nota>;
  if (!dados) return <CarregandoTela />;
  const { catalogo, perfil } = dados;

  if (!perfil) {
    return (
      <div>
        <CabecalhoTela titulo="Crie seu perfil" subtitulo="Leva dois minutos. Você pode mudar tudo depois." />
        <FormPerfil catalogo={catalogo} atual={null} aoSalvar={() => irPara("descobrir")} />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="mb-2 flex items-center gap-4">
        <Avatar nome={perfil.nome_exibicao} tamanho={64} />
        <div className="min-w-0">
          <h1 className="truncate text-[28px] font-bold leading-tight tracking-tight">{perfil.nome_exibicao}</h1>
          <p className="text-sm text-suave">{catalogo.rotulo.get(perfil.genero) ?? perfil.genero} · {perfil.visivel ? "visível" : "oculto"}</p>
        </div>
      </div>
      <SecaoPedidos />
      <SecaoFotos />
      <SecaoLocalizacao key={`loc-${chave}`} perfil={perfil} aoMudar={recarregar} />
      <FormPerfil key={`form-${chave}`} catalogo={catalogo} atual={perfil} aoSalvar={recarregar} />
    </div>
  );
}
