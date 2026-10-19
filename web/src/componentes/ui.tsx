// Peças básicas de interface. Só usam os tokens de index.css (nada de cores soltas).
import { ChevronDown, Loader2, X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import {
  type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes,
  type TextareaHTMLAttributes, useEffect, useId,
} from "react";
import { iniciais, juntarClasses } from "../lib/util";

type Variante = "primario" | "secundario" | "perigo" | "fantasma" | "suave";

const VARIANTES: Record<Variante, string> = {
  primario: "bg-acento text-white shadow-[0_6px_20px_-6px_rgb(225_29_72/0.6)] hover:brightness-110 active:brightness-95",
  secundario: "bg-superficie-2 text-texto hover:bg-borda",
  perigo: "bg-perigo text-white hover:brightness-110",
  fantasma: "bg-transparent text-acento-texto hover:bg-acento-suave",
  suave: "bg-acento-suave text-acento-texto hover:brightness-95",
};

interface PropsBotao extends ButtonHTMLAttributes<HTMLButtonElement> {
  variante?: Variante;
  carregando?: boolean;
  icone?: ReactNode;
  cheio?: boolean;
  pequeno?: boolean;
}

export function Botao({ variante = "primario", carregando, icone, cheio, pequeno, className, children, disabled, ...resto }: PropsBotao) {
  return (
    <button
      type="button"
      {...resto}
      disabled={disabled || carregando}
      className={juntarClasses(
        "inline-flex items-center justify-center gap-2 rounded-full font-semibold transition select-none",
        "disabled:opacity-50 disabled:pointer-events-none",
        pequeno ? "min-h-10 px-4 text-sm" : "min-h-12 px-6 text-[15px]",
        cheio && "w-full",
        VARIANTES[variante],
        className,
      )}
    >
      {carregando ? <Loader2 className="size-4 animate-spin" aria-hidden /> : icone}
      {children}
    </button>
  );
}

export function BotaoIcone({ rotulo, className, children, ...resto }: ButtonHTMLAttributes<HTMLButtonElement> & { rotulo: string }) {
  return (
    <button
      type="button"
      aria-label={rotulo}
      title={rotulo}
      {...resto}
      className={juntarClasses(
        "inline-flex size-11 items-center justify-center rounded-full text-texto transition hover:bg-superficie-2 disabled:opacity-50",
        className,
      )}
    >
      {children}
    </button>
  );
}

export function Cartao({ className, children, ...resto }: { className?: string; children: ReactNode } & React.HTMLAttributes<HTMLElement>) {
  return (
    <section {...resto} className={juntarClasses("rounded-cartao border border-borda bg-superficie p-5 shadow-cartao", className)}>
      {children}
    </section>
  );
}

export function TituloSecao({ children, acao }: { children: ReactNode; acao?: ReactNode }) {
  return (
    <div className="mb-3 flex items-center justify-between gap-3">
      <h2 className="text-[17px] font-semibold tracking-tight">{children}</h2>
      {acao}
    </div>
  );
}

export function Nota({ children, className }: { children: ReactNode; className?: string }) {
  return <p className={juntarClasses("text-sm leading-relaxed text-suave", className)}>{children}</p>;
}

export function CabecalhoTela({ titulo, subtitulo, acao }: { titulo: string; subtitulo?: string; acao?: ReactNode }) {
  return (
    <header className="mb-5 flex items-end justify-between gap-4">
      <div>
        <h1 className="text-[28px] font-bold leading-tight tracking-tight">{titulo}</h1>
        {subtitulo && <p className="mt-1 text-sm text-suave">{subtitulo}</p>}
      </div>
      {acao}
    </header>
  );
}

const CLASSE_CAMPO =
  "w-full rounded-2xl border border-transparent bg-superficie-2 px-4 py-3 text-[16px] outline-none transition "
  + "placeholder:text-suave focus:border-acento focus:bg-superficie";

interface PropsRotulo { rotulo: string; dica?: ReactNode }

export function Campo({ rotulo, dica, className, ...resto }: InputHTMLAttributes<HTMLInputElement> & PropsRotulo) {
  const id = useId();
  return (
    <div className={juntarClasses("space-y-1.5", className)}>
      <label htmlFor={id} className="block text-sm font-medium">{rotulo}</label>
      <input id={id} {...resto} className={CLASSE_CAMPO} />
      {dica && <p className="text-xs leading-relaxed text-suave">{dica}</p>}
    </div>
  );
}

export function AreaTexto({ rotulo, dica, className, ...resto }: TextareaHTMLAttributes<HTMLTextAreaElement> & PropsRotulo) {
  const id = useId();
  return (
    <div className={juntarClasses("space-y-1.5", className)}>
      <label htmlFor={id} className="block text-sm font-medium">{rotulo}</label>
      <textarea id={id} rows={3} {...resto} className={juntarClasses(CLASSE_CAMPO, "resize-none")} />
      {dica && <p className="text-xs leading-relaxed text-suave">{dica}</p>}
    </div>
  );
}

export function Seletor({ rotulo, dica, className, children, ...resto }: SelectHTMLAttributes<HTMLSelectElement> & PropsRotulo) {
  const id = useId();
  return (
    <div className={juntarClasses("space-y-1.5", className)}>
      <label htmlFor={id} className="block text-sm font-medium">{rotulo}</label>
      <div className="relative">
        <select id={id} {...resto} className={juntarClasses(CLASSE_CAMPO, "appearance-none pr-11")}>{children}</select>
        <ChevronDown className="pointer-events-none absolute right-4 top-1/2 size-5 -translate-y-1/2 text-suave" aria-hidden />
      </div>
      {dica && <p className="text-xs leading-relaxed text-suave">{dica}</p>}
    </div>
  );
}

export function Marcar({ marcado, aoMudar, children, nome }: { marcado: boolean; aoMudar: (v: boolean) => void; children: ReactNode; nome?: string }) {
  return (
    <label className="flex cursor-pointer items-start gap-3 rounded-2xl p-1 text-sm leading-relaxed">
      <input
        type="checkbox"
        name={nome}
        checked={marcado}
        onChange={(e) => aoMudar(e.target.checked)}
        className="mt-0.5 size-5 shrink-0 cursor-pointer accent-[var(--acento)]"
      />
      <span>{children}</span>
    </label>
  );
}

/** Interruptor (liga/desliga) acessível. */
export function Interruptor({ ligado, aoMudar, rotulo, descricao }: { ligado: boolean; aoMudar: (v: boolean) => void; rotulo: string; descricao?: ReactNode }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={ligado}
      onClick={() => aoMudar(!ligado)}
      className="flex w-full items-center justify-between gap-4 rounded-2xl py-2 text-left"
    >
      <span>
        <span className="block font-medium">{rotulo}</span>
        {descricao && <span className="mt-0.5 block text-sm text-suave">{descricao}</span>}
      </span>
      <span className={juntarClasses("relative h-7 w-12 shrink-0 rounded-full transition", ligado ? "bg-acento" : "bg-borda")}>
        <span className={juntarClasses("absolute top-0.5 size-6 rounded-full bg-white shadow transition-all", ligado ? "left-[22px]" : "left-0.5")} />
      </span>
    </button>
  );
}

/** Controle segmentado (abas pequenas). */
export function Segmentado<T extends string>({ opcoes, valor, aoMudar, rotulo }: {
  opcoes: [T, string][]; valor: T; aoMudar: (v: T) => void; rotulo: string;
}) {
  return (
    <div role="tablist" aria-label={rotulo} className="flex rounded-full bg-superficie-2 p-1">
      {opcoes.map(([v, texto]) => (
        <button
          key={v}
          type="button"
          role="tab"
          aria-selected={v === valor}
          onClick={() => aoMudar(v)}
          className={juntarClasses(
            "relative min-h-10 flex-1 rounded-full px-3 text-sm font-semibold transition",
            v === valor ? "text-texto" : "text-suave hover:text-texto",
          )}
        >
          {v === valor && (
            <motion.span layoutId={`seg-${rotulo}`} className="absolute inset-0 rounded-full bg-superficie shadow-cartao"
              transition={{ type: "spring", stiffness: 500, damping: 40 }} />
          )}
          <span className="relative">{texto}</span>
        </button>
      ))}
    </div>
  );
}

export function Chip({ children, destaque, className }: { children: ReactNode; destaque?: boolean; className?: string }) {
  return (
    <span className={juntarClasses(
      "inline-flex items-center rounded-full px-3 py-1.5 text-[13px] font-medium",
      destaque ? "bg-acento-suave text-acento-texto" : "bg-superficie-2 text-texto",
      className,
    )}>
      {children}
    </span>
  );
}

export function Avatar({ nome, tamanho = 44, url }: { nome: string; tamanho?: number; url?: string }) {
  return (
    <span
      className="gradiente-marca inline-flex shrink-0 items-center justify-center overflow-hidden rounded-full font-semibold text-white"
      style={{ width: tamanho, height: tamanho, fontSize: tamanho * 0.38 }}
      aria-hidden
    >
      {url ? <img src={url} alt="" className="size-full object-cover" /> : iniciais(nome)}
    </span>
  );
}

export function Esqueleto({ className }: { className?: string }) {
  return <div className={juntarClasses("animate-pulse rounded-2xl bg-superficie-2", className)} />;
}

export function CarregandoTela() {
  return (
    <div className="space-y-4" aria-busy="true" aria-label="Carregando">
      <Esqueleto className="h-9 w-40" />
      <Esqueleto className="h-48 w-full rounded-cartao" />
      <Esqueleto className="h-28 w-full rounded-cartao" />
    </div>
  );
}

export function Vazio({ icone, titulo, children, acao }: { icone: ReactNode; titulo: string; children?: ReactNode; acao?: ReactNode }) {
  return (
    <div className="flex flex-col items-center px-6 py-14 text-center">
      <div className="mb-5 flex size-20 items-center justify-center rounded-full bg-acento-suave text-acento-texto">{icone}</div>
      <h2 className="text-lg font-semibold">{titulo}</h2>
      {children && <p className="mt-2 max-w-xs text-sm leading-relaxed text-suave">{children}</p>}
      {acao && <div className="mt-6">{acao}</div>}
    </div>
  );
}

/** Folha que sobe de baixo (no celular) ou diálogo centralizado (no computador). */
export function Folha({ aberta, aoFechar, titulo, children }: { aberta: boolean; aoFechar: () => void; titulo: string; children: ReactNode }) {
  useEffect(() => {
    if (!aberta) return;
    const anterior = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = anterior; };
  }, [aberta]);

  return (
    <AnimatePresence>
      {aberta && (
        <div className="fixed inset-0 z-40 flex items-end justify-center md:items-center" role="dialog" aria-modal="true" aria-label={titulo}>
          <motion.div className="absolute inset-0 bg-black/45" onClick={aoFechar}
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} />
          <motion.div
            className="seguro-baixo relative max-h-[88dvh] w-full overflow-y-auto rounded-t-[28px] bg-superficie p-5 pb-8 shadow-2xl md:max-w-md md:rounded-[28px]"
            initial={{ y: 40, opacity: 0 }} animate={{ y: 0, opacity: 1 }} exit={{ y: 40, opacity: 0 }}
            transition={{ type: "spring", stiffness: 420, damping: 36 }}
          >
            <div className="mx-auto mb-3 h-1.5 w-10 rounded-full bg-borda md:hidden" aria-hidden />
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold">{titulo}</h2>
              <BotaoIcone rotulo="Fechar" onClick={aoFechar} className="-mr-2"><X className="size-5" /></BotaoIcone>
            </div>
            {children}
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}
