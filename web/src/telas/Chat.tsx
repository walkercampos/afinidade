// Chat efêmero: cada mensagem some um tempo depois de lida (24 h por padrão), para os dois
// lados. O prazo é combinado entre as duas pessoas: uma propõe, a outra confirma, e o novo
// prazo vale para as mensagens enviadas a partir daí.
import { ArrowLeft, CalendarHeart, Check, CheckCheck, Infinity as Nunca, MoreVertical, SendHorizontal, ShieldCheck, Timer, Trash2 } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { type FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { useAvisos } from "../componentes/avisos";
import { MenuSeguranca } from "../componentes/perfil";
import { Avatar, Botao, BotaoIcone, CarregandoTela, Folha, Nota } from "../componentes/ui";
import { api } from "../lib/api";
import { irPara } from "../lib/roteador";
import { conectarAvisos } from "../lib/tempoReal";
import type { Conversa, Mensagem, PrazoConversa } from "../lib/tipos";
import { descreverPrazo, formatarRestante, juntarClasses, msAte, rotuloPrazo } from "../lib/util";

// Com o canal em tempo real aberto, a busca periódica vira só uma reserva.
const INTERVALO_SEM_AVISOS_MS = 3000;
const INTERVALO_COM_AVISOS_MS = 20000;

function useAgora(intervalo = 1000) {
  const [agora, setAgora] = useState(Date.now());
  useEffect(() => {
    const t = setInterval(() => setAgora(Date.now()), intervalo);
    return () => clearInterval(t);
  }, [intervalo]);
  return agora;
}

function Balao({ m, agora }: { m: Mensagem; agora: number }) {
  const hora = new Date(m.criado_em).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
  const resta = m.expira_em ? msAte(m.expira_em, agora) : null;
  return (
    <motion.li layout initial={{ opacity: 0, y: 8, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, scale: 0.9 }}
      className={juntarClasses("flex", m.minha ? "justify-end" : "justify-start")}>
      <div className={juntarClasses(
        "max-w-[80%] rounded-[22px] px-4 py-2.5 shadow-sm",
        m.minha ? "gradiente-marca rounded-br-md text-white" : "rounded-bl-md border border-borda bg-superficie",
      )}>
        <p className="whitespace-pre-wrap break-words text-[15px] leading-snug">{m.texto}</p>
        <p className={juntarClasses("mt-1 flex items-center justify-end gap-1 text-[11px]", m.minha ? "text-white/80" : "text-suave")}>
          {resta != null && (
            <span className="mr-1 inline-flex items-center gap-0.5" title="Tempo até a mensagem sumir">
              <Timer className="size-3" aria-hidden /> some em {formatarRestante(resta)}
            </span>
          )}
          {m.ttl_minutos === null && <span className="mr-1 inline-flex items-center gap-0.5"><Nunca className="size-3" aria-hidden /> não some</span>}
          {hora}
          {m.minha && (m.lida_em ? <CheckCheck className="size-3.5" aria-label="lida" /> : <Check className="size-3.5" aria-label="não lida" />)}
        </p>
      </div>
    </motion.li>
  );
}

function PainelPrazo({ prazo, nome, outroId, aoMudar }: { prazo: PrazoConversa; nome: string; outroId: string; aoMudar: (p: PrazoConversa) => void }) {
  const { avisar } = useAvisos();
  const opcoes = prazo.opcoes.filter((o) => o !== prazo.ttl_minutos);
  const [escolha, setEscolha] = useState<number | null | undefined>(opcoes[0]);

  async function acao(chamar: () => Promise<PrazoConversa | null>, mensagem?: string) {
    try {
      aoMudar((await chamar()) ?? (await api<PrazoConversa>(`/conversas/${outroId}/prazo`)));
      if (mensagem) avisar(mensagem);
    } catch (e) { avisar((e as Error).message); }
  }
  const desistirOuRecusar = () => acao(() => api(`/conversas/${outroId}/prazo/proposta`, { metodo: "DELETE" }));
  const p = prazo.proposta;

  return (
    <div className="space-y-4">
      <div className="flex items-start gap-3 rounded-2xl bg-superficie-2 p-4">
        <ShieldCheck className="mt-0.5 size-5 shrink-0 text-ok" aria-hidden />
        <p className="text-sm leading-relaxed">Mensagens cifradas no servidor. {descreverPrazo(prazo.ttl_minutos)}</p>
      </div>
      <Nota>Mudar o prazo precisa das duas pessoas e vale só para as mensagens enviadas depois.</Nota>
      {!p ? (
        <>
          <div className="grid grid-cols-2 gap-2">
            {opcoes.map((o) => (
              <button key={String(o)} type="button" onClick={() => setEscolha(o)} aria-pressed={escolha === o}
                className={juntarClasses(
                  "min-h-11 rounded-2xl border px-3 text-sm font-medium transition",
                  escolha === o ? "border-acento bg-acento-suave text-acento-texto" : "border-borda hover:bg-superficie-2",
                )}>
                {o == null ? "Nunca somem" : rotuloPrazo(o)}
              </button>
            ))}
          </div>
          <Botao cheio disabled={escolha === undefined}
            onClick={() => acao(() => api(`/conversas/${outroId}/prazo`, { metodo: "POST", corpo: { ttl_minutos: escolha } }), "Proposta enviada")}>
            Propor a {nome}
          </Botao>
        </>
      ) : p.minha ? (
        <div className="space-y-3 rounded-2xl border border-borda p-4">
          <p className="text-sm">Você propôs <strong>{rotuloPrazo(p.ttl_minutos)}</strong>. Esperando {nome} confirmar.</p>
          <Botao variante="secundario" cheio onClick={desistirOuRecusar}>Desistir</Botao>
        </div>
      ) : (
        <div className="space-y-3 rounded-2xl border border-acento p-4">
          <p className="text-sm">{nome} propôs mudar para <strong>{rotuloPrazo(p.ttl_minutos)}</strong>. Vale para as próximas mensagens.</p>
          <div className="flex gap-2">
            <Botao variante="secundario" cheio onClick={desistirOuRecusar}>Recusar</Botao>
            <Botao cheio onClick={() => acao(() => api(`/conversas/${outroId}/prazo/confirmar`, { metodo: "POST" }), "Prazo novo combinado.")}>Aceitar</Botao>
          </div>
        </div>
      )}
    </div>
  );
}

export function TelaChat({ outroId }: { outroId: string | null }) {
  const { avisar, confirmar } = useAvisos();
  const [conversa, setConversa] = useState<Conversa | null>(null);
  const [mensagens, setMensagens] = useState<Mensagem[]>([]);
  const [prazo, setPrazo] = useState<PrazoConversa | null>(null);
  const [texto, setTexto] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [painel, setPainel] = useState<"nenhum" | "prazo" | "opcoes" | "seguranca">("nenhum");
  const fim = useRef<HTMLDivElement>(null);
  const agora = useAgora();

  const ultimaSincronia = useRef(0);
  const sincronizar = useCallback(async () => {
    if (!outroId || document.hidden) return; // não marca como lida o que ninguém está vendo
    const minha = ++ultimaSincronia.current;
    const [lista, p] = await Promise.all([
      api<Mensagem[]>(`/conversas/${outroId}/mensagens?limite=100`),
      api<PrazoConversa>(`/conversas/${outroId}/prazo`),
    ]);
    // Uma busca antiga que termina depois (ex.: a periódica, durante "apagar") não pode
    // trazer de volta o que já saiu da tela.
    if (minha !== ultimaSincronia.current) return;
    setMensagens(lista);
    setPrazo(p);
  }, [outroId]);

  useEffect(() => {
    if (!outroId) { irPara("conexoes"); return; }
    let ativo = true;
    api<Conversa[]>("/conversas").then((lista) => {
      if (!ativo) return;
      const c = lista.find((x) => x.perfil.id === outroId);
      if (!c) irPara("conexoes");
      else setConversa(c);
    }).catch(() => {});
    sincronizar().catch(() => {});

    const avisos = conectarAvisos((aviso) => { if (aviso.conversa === outroId) sincronizar().catch(() => {}); });
    let ultimaBusca = Date.now();
    const busca = setInterval(() => {
      const intervalo = avisos.conectado() ? INTERVALO_COM_AVISOS_MS : INTERVALO_SEM_AVISOS_MS;
      if (Date.now() - ultimaBusca < intervalo) return;
      ultimaBusca = Date.now();
      sincronizar().catch(() => {});
    }, 1000);
    return () => { ativo = false; clearInterval(busca); avisos.fechar(); };
  }, [outroId, sincronizar]);

  const visiveis = mensagens.filter((m) => !m.expira_em || msAte(m.expira_em, agora) > 0);
  useEffect(() => { fim.current?.scrollIntoView({ block: "end", behavior: "smooth" }); }, [visiveis.length]);

  async function enviar(e: FormEvent) {
    e.preventDefault();
    if (!texto.trim() || !outroId) return;
    setEnviando(true);
    try {
      const m = await api<Mensagem>(`/conversas/${outroId}/mensagens`, { metodo: "POST", corpo: { texto } });
      setTexto("");
      ultimaSincronia.current++; // descarta uma busca em andamento, que ainda não tem esta mensagem
      setMensagens((l) => [...l, m]);
    } catch (e) { avisar((e as Error).message); } finally { setEnviando(false); }
  }

  async function apagarMinhas() {
    setPainel("nenhum");
    const sim = await confirmar({ titulo: "Apagar suas mensagens?", texto: "Apaga agora, para os dois lados, todas as mensagens que você enviou nesta conversa.", confirmar: "Apagar", perigo: true });
    if (!sim) return;
    await api(`/conversas/${outroId}/mensagens`, { metodo: "DELETE" });
    await sincronizar();
    avisar("Suas mensagens foram apagadas");
  }

  if (!conversa || !prazo) return <CarregandoTela />;
  const nome = conversa.perfil.nome_exibicao;

  return (
    <div className="flex min-h-[calc(100dvh-13rem)] flex-col md:min-h-[calc(100dvh-10rem)]">
      <div className="sticky top-[68px] z-10 -mx-4 mb-3 flex items-center gap-2 border-b border-borda bg-fundo/90 px-2 py-2 backdrop-blur">
        <BotaoIcone rotulo="Voltar" onClick={() => irPara("conexoes")}><ArrowLeft className="size-5" /></BotaoIcone>
        <Avatar nome={nome} tamanho={40} />
        <div className="min-w-0 flex-1">
          <p className="truncate font-semibold leading-tight">{nome}</p>
          <button type="button" onClick={() => setPainel("prazo")} className="inline-flex items-center gap-1 text-xs font-medium text-acento-texto">
            <Timer className="size-3" aria-hidden />
            {prazo.ttl_minutos == null ? "mensagens não somem" : `somem ${rotuloPrazo(prazo.ttl_minutos)} após lidas`}
            {prazo.proposta && !prazo.proposta.minha && <span className="ml-1 rounded-full bg-acento px-1.5 text-[10px] text-white">proposta</span>}
          </button>
        </div>
        <BotaoIcone rotulo="Opções da conversa" onClick={() => setPainel("opcoes")}><MoreVertical className="size-5" /></BotaoIcone>
      </div>

      <ol className="flex-1 space-y-2" aria-live="polite">
        {visiveis.length === 0 && (
          <li className="py-16 text-center">
            <p className="font-semibold">Comece a conversa com {nome}</p>
            <Nota className="mt-1">{descreverPrazo(prazo.ttl_minutos)}</Nota>
          </li>
        )}
        <AnimatePresence initial={false}>
          {visiveis.map((m) => <Balao key={m.id} m={m} agora={agora} />)}
        </AnimatePresence>
      </ol>
      <div ref={fim} />

      <form onSubmit={enviar}
        className="sticky bottom-[84px] z-10 -mx-4 mt-4 flex items-end gap-2 bg-gradient-to-t from-fundo via-fundo to-transparent px-4 pb-2 pt-4 md:bottom-4">
        <textarea
          value={texto}
          onChange={(e) => setTexto(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); enviar(e); } }}
          rows={1}
          maxLength={2000}
          aria-label="Mensagem"
          placeholder="Mensagem"
          className="max-h-32 min-h-12 flex-1 resize-none rounded-[24px] border border-borda bg-superficie px-4 py-3 text-[16px] outline-none shadow-cartao focus:border-acento"
        />
        <button type="submit" aria-label="Enviar" disabled={!texto.trim() || enviando}
          className="gradiente-marca flex size-12 shrink-0 items-center justify-center rounded-full text-white shadow-lg transition active:scale-95 disabled:opacity-40">
          <SendHorizontal className="size-5" />
        </button>
      </form>

      <Folha aberta={painel === "prazo"} aoFechar={() => setPainel("nenhum")} titulo="Prazo das mensagens">
        <PainelPrazo prazo={prazo} nome={nome} outroId={conversa.perfil.id} aoMudar={setPrazo} />
      </Folha>
      <Folha aberta={painel === "opcoes"} aoFechar={() => setPainel("nenhum")} titulo={nome}>
        <div className="space-y-2">
          <Botao variante="secundario" cheio icone={<Timer className="size-4" />} onClick={() => setPainel("prazo")}>Prazo das mensagens</Botao>
          <Botao variante="secundario" cheio icone={<CalendarHeart className="size-4" />} onClick={() => irPara(`encontros/${conversa.perfil.id}`)}>Encontro seguro</Botao>
          <Botao variante="secundario" cheio icone={<Trash2 className="size-4" />} onClick={apagarMinhas}>Apagar as minhas mensagens</Botao>
          <Botao variante="secundario" cheio icone={<ShieldCheck className="size-4" />} onClick={() => setPainel("seguranca")}>Bloquear ou denunciar</Botao>
        </div>
      </Folha>
      <MenuSeguranca aberto={painel === "seguranca"} aoFechar={() => setPainel("nenhum")} perfilId={conversa.perfil.id} nome={nome}
        comMensagens aoRemover={() => irPara("conexoes")} />
    </div>
  );
}
