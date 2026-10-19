// Descobrir: um perfil por vez, em cartões. Arrastar para a direita curte; para a esquerda, pula.
import { Heart, MapPin, MoreHorizontal, RotateCcw, SlidersHorizontal, Sparkles, X } from "lucide-react";
import { animate, AnimatePresence, motion, useMotionValue, useTransform } from "motion/react";
import { useCallback, useEffect, useRef, useState } from "react";
import { useAvisos } from "../componentes/avisos";
import { AnelAfinidade, FotoProtegida, MenuSeguranca } from "../componentes/perfil";
import { Avatar, Botao, BotaoIcone, Chip, Esqueleto, Folha, Interruptor, Segmentado, Vazio } from "../componentes/ui";
import { api, apiCompleta, type Catalogo, carregarCatalogo, ErroApi } from "../lib/api";
import { irPara } from "../lib/roteador";
import type { Candidato, Ordem, ResultadoCurtida } from "../lib/tipos";
import { descreverDistancia, juntarClasses } from "../lib/util";

const ORDENS: [Ordem, string][] = [["compatibilidade", "Compatíveis"], ["afinidade", "Parecidos"], ["recentes", "Recentes"]];

// Ficam enquanto o app está aberto (voltar para Descobrir mantém a escolha).
let ordemSalva: Ordem = "compatibilidade";
const filtrosSalvos = { comFoto: false, ativosSemana: false };

function CartaoCandidato({ c, catalogo, noTopo, aoDecidir, aoMenu }: {
  c: Candidato; catalogo: Catalogo; noTopo: boolean;
  aoDecidir: (curtir: boolean) => void; aoMenu: () => void;
}) {
  const x = useMotionValue(0);
  const giro = useTransform(x, [-240, 240], [-12, 12]);
  const curtir = useTransform(x, [30, 120], [0, 1]);
  const pular = useTransform(x, [-120, -30], [1, 0]);
  const { perfil, compatibilidade: compat, fotos } = c;
  const comuns = new Set(compat.tags_em_comum);
  const rotulo = (s: string) => catalogo.rotulo.get(s) ?? s;
  const distancia = descreverDistancia(compat.distancia_km);
  const foto = fotos[0];

  return (
    <motion.article
      className={juntarClasses(
        "absolute inset-0 flex flex-col overflow-hidden rounded-[28px] border border-borda bg-superficie shadow-cartao",
        noTopo ? "cursor-grab active:cursor-grabbing" : "pointer-events-none",
      )}
      style={noTopo ? { x, rotate: giro } : undefined}
      drag={noTopo ? "x" : false}
      dragSnapToOrigin
      dragElastic={0.6}
      onDragEnd={(_, info) => {
        if (info.offset.x > 110 || info.velocity.x > 600) aoDecidir(true);
        else if (info.offset.x < -110 || info.velocity.x < -600) aoDecidir(false);
      }}
      initial={noTopo ? { scale: 0.96, opacity: 0, y: 12 } : false}
      animate={noTopo ? { scale: 1, opacity: 1, y: 0 } : { scale: 0.94, opacity: 0.7, y: 18 }}
      exit={{ opacity: 0, transition: { duration: 0.18 } }}
      aria-label={`Perfil de ${perfil.nome_exibicao}`}
    >
      <div className="relative h-[46%] shrink-0">
        {foto ? (
          <FotoProtegida foto={foto} className="size-full" />
        ) : (
          <div className="gradiente-marca flex size-full items-center justify-center">
            <Avatar nome={perfil.nome_exibicao} tamanho={96} />
          </div>
        )}
        <div className="pointer-events-none absolute inset-x-0 bottom-0 h-28 bg-gradient-to-t from-black/70 to-transparent" />
        <div className="absolute inset-x-0 bottom-0 flex items-end justify-between gap-3 p-4 text-white">
          <div className="min-w-0">
            <h2 className="truncate text-[26px] font-bold leading-tight">{perfil.nome_exibicao}</h2>
            <p className="flex items-center gap-1.5 text-sm text-white/85">
              {rotulo(perfil.genero)}
              {distancia && <><span aria-hidden>·</span><MapPin className="size-3.5" aria-hidden />{distancia}</>}
            </p>
          </div>
          <AnelAfinidade valor={compat.score_mutuo} tamanho={58} claro />
        </div>
        {noTopo && (
          <>
            <motion.span style={{ opacity: curtir }} className="absolute left-5 top-5 -rotate-12 rounded-xl border-4 border-ok px-3 py-1 text-2xl font-black uppercase tracking-wider text-ok">Curtir</motion.span>
            <motion.span style={{ opacity: pular }} className="absolute right-5 top-5 rotate-12 rounded-xl border-4 border-white px-3 py-1 text-2xl font-black uppercase tracking-wider text-white">Pular</motion.span>
          </>
        )}
        <BotaoIcone rotulo="Mais opções" onClick={aoMenu} className="absolute right-3 top-3 bg-black/35 text-white backdrop-blur hover:bg-black/50">
          <MoreHorizontal className="size-5" />
        </BotaoIcone>
      </div>

      <div className="sem-barra flex-1 space-y-4 overflow-y-auto p-5">
        {compat.tags_em_comum.length > 0 && (
          <p className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-sm font-semibold text-acento-texto">
            <Sparkles className="size-4" aria-hidden />
            {compat.tags_em_comum.length} {compat.tags_em_comum.length === 1 ? "interesse" : "interesses"} em comum
            {compat.similaridade > 0 && <span className="w-full pl-6 font-normal text-suave">gostos {compat.similaridade}% parecidos</span>}
          </p>
        )}
        {perfil.bio && <p className="text-[15px] leading-relaxed">{perfil.bio}</p>}
        {perfil.quero.length > 0 && (
          <div>
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-suave">Quer</h3>
            <div className="flex flex-wrap gap-1.5">{perfil.quero.map((s) => <Chip key={s} destaque={comuns.has(s)}>{rotulo(s)}</Chip>)}</div>
          </div>
        )}
        {perfil.curioso.length > 0 && (
          <div>
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-suave">Curiosidade</h3>
            <div className="flex flex-wrap gap-1.5">{perfil.curioso.map((s) => <Chip key={s} destaque={comuns.has(s)}>{rotulo(s)}</Chip>)}</div>
          </div>
        )}
      </div>
    </motion.article>
  );
}

/** Tela comemorativa quando a curtida é recíproca. */
function NovaConexao({ c, aoFechar }: { c: Candidato | null; aoFechar: () => void }) {
  return (
    <AnimatePresence>
      {c && (
        <motion.div className="gradiente-marca fixed inset-0 z-40 flex flex-col items-center justify-center px-8 text-center text-white"
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} role="dialog" aria-modal="true" aria-label="É uma conexão">
          {Array.from({ length: 14 }, (_, i) => (
            <motion.span key={i} aria-hidden className="absolute text-white/70"
              style={{ left: `${(i * 37) % 100}%`, top: "60%" }}
              initial={{ y: 0, opacity: 0, scale: 0.6 }}
              animate={{ y: -320 - (i % 4) * 60, opacity: [0, 1, 0], scale: 1 }}
              transition={{ duration: 2.2, delay: i * 0.08, ease: "easeOut" }}>
              <Heart className="size-5 fill-current" />
            </motion.span>
          ))}
          <motion.div initial={{ scale: 0.6, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} transition={{ type: "spring", stiffness: 260, damping: 18, delay: 0.1 }}>
            <div className="mb-8 flex items-center justify-center">
              <span className="rounded-full border-4 border-white/80 shadow-2xl"><Avatar nome="Você" tamanho={104} /></span>
              <span className="-ml-6 rounded-full border-4 border-white/80 shadow-2xl"><Avatar nome={c.perfil.nome_exibicao} tamanho={104} url={c.fotos[0]?.nitida ? c.fotos[0].url : undefined} /></span>
            </div>
            <h2 className="text-4xl font-black tracking-tight">É uma conexão!</h2>
            <p className="mx-auto mt-3 max-w-xs text-white/90">Você e {c.perfil.nome_exibicao} curtiram um ao outro. Agora vocês já podem conversar.</p>
          </motion.div>
          <div className="mt-10 w-full max-w-xs space-y-3">
            <button type="button" onClick={() => irPara(`chat/${c.perfil.id}`)}
              className="min-h-12 w-full rounded-full bg-white font-semibold text-acento shadow-xl transition hover:scale-[1.02]">
              Mandar mensagem
            </button>
            <button type="button" onClick={aoFechar} className="min-h-12 w-full rounded-full font-semibold text-white/90 hover:bg-white/10">
              Continuar descobrindo
            </button>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

export function TelaDescobrir() {
  const { avisar } = useAvisos();
  const [ordem, setOrdem] = useState<Ordem>(ordemSalva);
  const [filtros, setFiltros] = useState(filtrosSalvos);
  const [catalogo, setCatalogo] = useState<Catalogo | null>(null);
  const [fila, setFila] = useState<Candidato[] | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [jaViu, setJaViu] = useState(false);
  const [conexao, setConexao] = useState<Candidato | null>(null);
  const [menu, setMenu] = useState(false);
  const [ajustes, setAjustes] = useState(false);
  const cursor = useRef<string | null>(null);
  const buscando = useRef(false);
  const geracao = useRef(0);

  const buscar = useCallback(async (reiniciar: boolean) => {
    if (buscando.current && !reiniciar) return;
    const minha = reiniciar ? ++geracao.current : geracao.current;
    buscando.current = true;
    const params = new URLSearchParams({ limite: "20", ordem });
    if (filtros.comFoto) params.set("com_foto", "true");
    if (filtros.ativosSemana) params.set("ativos_dias", "7");
    if (!reiniciar && cursor.current) params.set("cursor", cursor.current);
    try {
      const [cat, { dados, cabecalhos }] = await Promise.all([
        carregarCatalogo(), apiCompleta<Candidato[]>(`/descobrir?${params}`),
      ]);
      if (minha !== geracao.current) return;
      setCatalogo(cat);
      cursor.current = cabecalhos.get("X-Proximo-Cursor");
      setFila((f) => (reiniciar || !f ? dados : [...f, ...dados.filter((d) => !f.some((x) => x.perfil.id === d.perfil.id))]));
      setErro(null);
    } catch (e) {
      if (e instanceof ErroApi && e.status === 409) return irPara("perfil"); // ainda sem perfil
      if (e instanceof ErroApi && (e.status === 401 || e.status === 403)) return;
      setErro((e as Error).message);
    } finally {
      buscando.current = false;
    }
  }, [ordem, filtros]);

  useEffect(() => {
    ordemSalva = ordem;
    Object.assign(filtrosSalvos, filtros);
    setFila(null);
    buscar(true);
  }, [buscar]);

  // Perto do fim da fila, já busca a próxima página.
  useEffect(() => {
    if (fila && fila.length < 3 && cursor.current) buscar(false);
  }, [fila, buscar]);

  const atual = fila?.[0];

  function tirarDoTopo() {
    setJaViu(true);
    setFila((f) => (f ? f.slice(1) : f));
  }

  async function decidir(curtir: boolean) {
    if (!atual) return;
    tirarDoTopo();
    if (!curtir) return;
    try {
      const r = await api<ResultadoCurtida>(`/perfis/${atual.perfil.id}/curtir`, { metodo: "POST" });
      if (r.conexao) setConexao(atual);
      else avisar("Curtida enviada");
    } catch (e) {
      avisar((e as Error).message);
    }
  }

  async function botao(curtir: boolean) {
    // anima o cartão saindo antes de decidir, como no gesto
    const el = document.querySelector<HTMLElement>("[data-topo]");
    if (el) await animate(el, { x: curtir ? 420 : -420, rotate: curtir ? 14 : -14 }, { duration: 0.28 });
    decidir(curtir);
  }

  const ajustesAtivos = Number(filtros.comFoto) + Number(filtros.ativosSemana);

  return (
    <div>
      <div className="mb-4 flex items-center gap-3">
        <h1 className="flex-1 text-[28px] font-bold tracking-tight">Descobrir</h1>
        <BotaoIcone rotulo="Filtros" onClick={() => setAjustes(true)} className="relative bg-superficie-2">
          <SlidersHorizontal className="size-5" />
          {ajustesAtivos > 0 && <span className="absolute -right-0.5 -top-0.5 flex size-5 items-center justify-center rounded-full bg-acento text-[11px] font-bold text-white">{ajustesAtivos}</span>}
        </BotaoIcone>
      </div>
      <Segmentado rotulo="Ordenar por" valor={ordem} aoMudar={setOrdem} opcoes={ORDENS} />

      <div className="relative mt-4 h-[clamp(360px,calc(100dvh-430px),600px)] md:h-[clamp(420px,calc(100dvh-300px),620px)]">
        {erro ? (
          <Vazio icone={<RotateCcw className="size-9" />} titulo="Não deu para carregar" acao={<Botao onClick={() => buscar(true)}>Tentar de novo</Botao>}>{erro}</Vazio>
        ) : !fila || !catalogo ? (
          <Esqueleto className="absolute inset-0 rounded-[28px]" />
        ) : atual ? (
          <AnimatePresence initial={false}>
            {fila.slice(0, 2).reverse().map((c, i, lista) => {
              const noTopo = i === lista.length - 1;
              return (
                <div key={c.perfil.id} className="absolute inset-0" data-topo={noTopo ? "" : undefined}>
                  <CartaoCandidato c={c} catalogo={catalogo} noTopo={noTopo} aoDecidir={decidir} aoMenu={() => setMenu(true)} />
                </div>
              );
            })}
          </AnimatePresence>
        ) : (
          <Vazio icone={<Sparkles className="size-9" />} titulo={jaViu ? "Você viu todo mundo por enquanto" : "Ninguém compatível por enquanto"}
            acao={<Botao variante="secundario" onClick={() => (jaViu ? buscar(true) : irPara("perfil"))}>{jaViu ? "Procurar de novo" : "Ajustar meu perfil"}</Botao>}>
            {jaViu ? "Volte mais tarde para ver quem chegou." : "Ajuste seus interesses e a distância, ou volte mais tarde."}
          </Vazio>
        )}
      </div>

      {atual && (
        <div className="mt-5 flex items-center justify-center gap-6">
          <button type="button" aria-label="Pular" onClick={() => botao(false)}
            className="flex size-16 items-center justify-center rounded-full border border-borda bg-superficie text-suave shadow-cartao transition hover:scale-105 hover:text-texto active:scale-95">
            <X className="size-7" strokeWidth={2.4} />
          </button>
          <button type="button" aria-label="Curtir" onClick={() => botao(true)}
            className="gradiente-marca flex size-[72px] items-center justify-center rounded-full text-white shadow-[0_12px_32px_-8px_rgb(225_29_72/0.7)] transition hover:scale-105 active:scale-95">
            <Heart className="size-8 fill-current" />
          </button>
        </div>
      )}

      {atual && (
        <MenuSeguranca aberto={menu} aoFechar={() => setMenu(false)} perfilId={atual.perfil.id} nome={atual.perfil.nome_exibicao}
          comFotosBorradas={atual.fotos.some((f) => !f.nitida)} aoRemover={tirarDoTopo} />
      )}

      <Folha aberta={ajustes} aoFechar={() => setAjustes(false)} titulo="Filtros">
        <div className="divide-y divide-borda">
          <Interruptor rotulo="Só com foto" ligado={filtros.comFoto} aoMudar={(v) => setFiltros({ ...filtros, comFoto: v })} />
          <Interruptor rotulo="Ativos esta semana" ligado={filtros.ativosSemana} aoMudar={(v) => setFiltros({ ...filtros, ativosSemana: v })} />
        </div>
        <p className="mt-4 text-sm text-suave">A distância máxima fica no seu perfil.</p>
        <Botao className="mt-5" cheio onClick={() => setAjustes(false)}>Pronto</Botao>
      </Folha>

      <NovaConexao c={conexao} aoFechar={() => setConexao(null)} />
    </div>
  );
}
