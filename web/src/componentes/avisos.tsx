// Avisos rápidos (toasts) e confirmações. Substituem alert() e confirm() do navegador.
import { AnimatePresence, motion } from "motion/react";
import { createContext, type ReactNode, useCallback, useContext, useRef, useState } from "react";
import { Botao, Folha, Nota } from "./ui";

interface Confirmacao { titulo: string; texto: string; confirmar: string; perigo?: boolean }
interface Contexto {
  avisar: (texto: string) => void;
  confirmar: (c: Confirmacao) => Promise<boolean>;
}

const Ctx = createContext<Contexto>({ avisar: () => {}, confirmar: async () => false });
export const useAvisos = () => useContext(Ctx);

export function ProvedorDeAvisos({ children }: { children: ReactNode }) {
  const [lista, setLista] = useState<{ id: number; texto: string }[]>([]);
  const [pergunta, setPergunta] = useState<Confirmacao | null>(null);
  const resolver = useRef<(v: boolean) => void>(() => {});
  const contador = useRef(0);

  const avisar = useCallback((texto: string) => {
    const id = ++contador.current;
    setLista((l) => [...l.slice(-2), { id, texto }]);
    setTimeout(() => setLista((l) => l.filter((a) => a.id !== id)), 3600);
  }, []);

  const confirmar = useCallback((c: Confirmacao) => {
    setPergunta(c);
    return new Promise<boolean>((r) => { resolver.current = r; });
  }, []);

  const responder = (v: boolean) => {
    setPergunta(null);
    resolver.current(v);
  };

  return (
    <Ctx.Provider value={{ avisar, confirmar }}>
      {children}
      <div className="pointer-events-none fixed inset-x-0 bottom-28 z-50 flex flex-col items-center gap-2 px-4 md:bottom-8" role="status" aria-live="polite">
        <AnimatePresence>
          {lista.map((a) => (
            <motion.div key={a.id} layout
              initial={{ opacity: 0, y: 16, scale: 0.96 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: 8 }}
              className="max-w-sm rounded-full bg-texto px-5 py-3 text-center text-sm font-medium text-fundo shadow-xl">
              {a.texto}
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
      <Folha aberta={Boolean(pergunta)} aoFechar={() => responder(false)} titulo={pergunta?.titulo ?? ""}>
        <Nota>{pergunta?.texto}</Nota>
        <div className="mt-6 flex gap-3">
          <Botao variante="secundario" cheio onClick={() => responder(false)}>Cancelar</Botao>
          <Botao variante={pergunta?.perigo ? "perigo" : "primario"} cheio onClick={() => responder(true)}>
            {pergunta?.confirmar}
          </Botao>
        </div>
      </Folha>
    </Ctx.Provider>
  );
}
