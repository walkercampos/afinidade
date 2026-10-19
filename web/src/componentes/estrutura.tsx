// Moldura do app: topo com a marca, barra de abas (embaixo no celular, no topo no computador)
// e o botão de pânico, que fica em todas as telas.
import { CalendarHeart, Compass, MessageCircle, Settings, UserRound, X } from "lucide-react";
import type { ReactNode } from "react";
import { MODO_DEMO } from "../lib/api";
import { useDiscreto } from "../lib/discricao";
import { acionarPanico } from "../lib/panico";
import { irPara } from "../lib/roteador";
import { juntarClasses } from "../lib/util";

const ABAS = [
  { rota: "descobrir", rotulo: "Descobrir", Icone: Compass },
  { rota: "conexoes", rotulo: "Conexões", Icone: MessageCircle },
  { rota: "encontros", rotulo: "Encontros", Icone: CalendarHeart },
  { rota: "perfil", rotulo: "Perfil", Icone: UserRound },
  { rota: "conta", rotulo: "Conta", Icone: Settings },
];

export function Marca({ grande }: { grande?: boolean }) {
  const discreto = useDiscreto();
  if (discreto) return <span className={juntarClasses("font-bold tracking-tight", grande ? "text-3xl" : "text-xl")}>Notas</span>;
  return (
    <span className="inline-flex items-center gap-2">
      <span className={juntarClasses("gradiente-marca inline-flex items-center justify-center rounded-[30%] text-white shadow-lg", grande ? "size-12" : "size-8")} aria-hidden>
        <svg viewBox="0 0 24 24" className={grande ? "size-7" : "size-[18px]"} fill="currentColor">
          <path d="M12 21s-7.5-4.6-9.6-9.4C1 8.3 3.1 4.5 6.8 4.5c2.1 0 3.6 1.1 4.4 2.6h1.6c.8-1.5 2.3-2.6 4.4-2.6 3.7 0 5.8 3.8 4.4 7.1C19.5 16.4 12 21 12 21z" />
        </svg>
      </span>
      <span className={juntarClasses("font-bold tracking-tight", grande ? "text-3xl" : "text-xl")}>Afinidade</span>
    </span>
  );
}

function BotaoPanico() {
  return (
    <button
      type="button"
      onClick={acionarPanico}
      aria-label="Saída rápida (ESC)"
      title="Saída rápida (ESC)"
      className="fixed right-4 top-3 z-50 flex size-11 items-center justify-center rounded-full bg-perigo text-white shadow-[0_8px_24px_-6px_rgb(220_38_38/0.7)] transition hover:scale-105 active:scale-95 md:right-6 md:top-4"
    >
      <X className="size-5" strokeWidth={2.6} />
    </button>
  );
}

function Abas({ atual }: { atual: string }) {
  const rotaAtiva = atual === "chat" ? "conexoes" : atual === "moderacao" ? "conta" : atual;
  return (
    <nav
      aria-label="Navegação principal"
      className="vidro seguro-baixo fixed inset-x-0 bottom-0 z-30 border-t border-borda md:static md:inset-auto md:border-0 md:bg-transparent md:backdrop-blur-none"
    >
      <ul className="mx-auto flex max-w-lg justify-around px-2 pt-1.5 md:max-w-none md:justify-center md:gap-1 md:p-0">
        {ABAS.map(({ rota, rotulo, Icone }) => {
          const ativa = rota === rotaAtiva;
          return (
            <li key={rota}>
              <a
                href={`#/${rota}`}
                onClick={(e) => { e.preventDefault(); irPara(rota); }}
                aria-current={ativa ? "page" : undefined}
                className={juntarClasses(
                  "flex min-w-16 flex-col items-center gap-0.5 rounded-2xl px-2 py-1.5 text-[11px] font-medium transition",
                  "md:flex-row md:gap-2 md:rounded-full md:px-4 md:py-2 md:text-sm",
                  ativa ? "text-acento md:bg-acento-suave md:text-acento-texto" : "text-suave hover:text-texto",
                )}
              >
                <Icone className="size-6 md:size-[18px]" strokeWidth={ativa ? 2.4 : 1.8} aria-hidden />
                {rotulo}
              </a>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

export function Estrutura({ rota, comMenu, children }: { rota: string; comMenu: boolean; children: ReactNode }) {
  return (
    <>
      <BotaoPanico />
      {comMenu && (
        <header className="vidro sticky top-0 z-20 border-b border-borda">
          <div className="mx-auto flex h-[68px] max-w-5xl items-center gap-6 px-4 pr-20 md:px-6 md:pr-24">
            <a href="#/descobrir" onClick={(e) => { e.preventDefault(); irPara("descobrir"); }}><Marca /></a>
            <span className="rounded-full border border-borda px-2 py-0.5 text-[11px] font-bold text-suave">18+</span>
            <div className="hidden flex-1 md:block"><Abas atual={rota} /></div>
          </div>
        </header>
      )}
      {MODO_DEMO && (
        <p className="bg-violeta-suave py-1.5 pl-4 pr-16 text-center text-xs font-medium text-violeta">
          Modo demonstração · dados de exemplo, nada é enviado
        </p>
      )}
      <main className={juntarClasses("mx-auto w-full max-w-lg px-4 pt-5 md:max-w-2xl", comMenu ? "pb-32 md:pb-12" : "pb-12")}>
        {children}
      </main>
      {comMenu && <div className="md:hidden"><Abas atual={rota} /></div>}
    </>
  );
}
