import { type DependencyList, useCallback, useEffect, useRef, useState } from "react";
import { ErroApi } from "./api";

/**
 * Carrega dados ao abrir a tela. Se a pessoa sair antes da resposta, o resultado é descartado:
 * uma tela lenta que termina depois não sobrescreve a tela nova.
 */
export function useCarregar<T>(carregar: () => Promise<T>, deps: DependencyList = []) {
  const [dados, setDados] = useState<T | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const geracao = useRef(0);

  const recarregar = useCallback(async () => {
    const minha = ++geracao.current;
    try {
      const d = await carregar();
      if (minha === geracao.current) { setDados(d); setErro(null); }
    } catch (e) {
      // 401 já levou para a tela de entrar; aqui só mostra os outros erros
      if (minha === geracao.current && !(e instanceof ErroApi && e.status === 401)) {
        setErro(e instanceof Error ? e.message : "Não foi possível carregar.");
      }
    }
  }, deps);

  useEffect(() => {
    recarregar();
    return () => { geracao.current++; };
  }, [recarregar]);

  return { dados, erro, recarregar, setDados };
}
