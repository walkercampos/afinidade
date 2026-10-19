import { ChevronRight, HeartHandshake } from "lucide-react";
import { motion } from "motion/react";
import { Avatar, Botao, CabecalhoTela, CarregandoTela, Nota, Vazio } from "../componentes/ui";
import { api, carregarCatalogo } from "../lib/api";
import { irPara } from "../lib/roteador";
import type { Conversa } from "../lib/tipos";
import { useCarregar } from "../lib/useCarregar";
import { quandoRelativo } from "../lib/util";

export function TelaConexoes() {
  const { dados, erro } = useCarregar(() => Promise.all([api<Conversa[]>("/conversas"), carregarCatalogo()]));
  if (erro) return <Nota>{erro}</Nota>;
  if (!dados) return <CarregandoTela />;
  const [conversas, catalogo] = dados;

  return (
    <div>
      <CabecalhoTela titulo="Conexões" subtitulo={conversas.length ? "Quem curtiu você de volta." : undefined} />
      {conversas.length === 0 ? (
        <Vazio icone={<HeartHandshake className="size-9" />} titulo="Nenhuma conexão ainda"
          acao={<Botao onClick={() => irPara("descobrir")}>Ir para Descobrir</Botao>}>
          Quando alguém que você curtiu curtir você de volta, a conversa aparece aqui.
        </Vazio>
      ) : (
        <>
          <div className="sem-barra -mx-4 mb-6 flex gap-4 overflow-x-auto px-4 pb-1">
            {conversas.map(({ perfil }) => (
              <button key={perfil.id} type="button" onClick={() => irPara(`chat/${perfil.id}`)} className="flex w-16 shrink-0 flex-col items-center gap-1.5">
                <span className="gradiente-marca rounded-full p-[2.5px]"><span className="block rounded-full border-2 border-fundo"><Avatar nome={perfil.nome_exibicao} tamanho={56} /></span></span>
                <span className="w-full truncate text-center text-xs font-medium">{perfil.nome_exibicao}</span>
              </button>
            ))}
          </div>
          <h2 className="mb-2 text-xs font-semibold uppercase tracking-wider text-suave">Conversas</h2>
          <ul className="overflow-hidden rounded-cartao border border-borda bg-superficie shadow-cartao">
            {conversas.map(({ perfil, nao_lidas: naoLidas, ultima_em: ultima }, i) => (
              <motion.li key={perfil.id} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.04 }}
                className="border-b border-borda last:border-0">
                <button type="button" onClick={() => irPara(`chat/${perfil.id}`)}
                  className="flex w-full items-center gap-3 px-4 py-3.5 text-left transition hover:bg-superficie-2">
                  <Avatar nome={perfil.nome_exibicao} tamanho={50} />
                  <span className="min-w-0 flex-1">
                    <span className="flex items-baseline justify-between gap-2">
                      <span className={naoLidas ? "truncate font-bold" : "truncate font-semibold"}>{perfil.nome_exibicao}</span>
                      <span className="shrink-0 text-xs text-suave">{quandoRelativo(ultima)}</span>
                    </span>
                    <span className="mt-0.5 block truncate text-sm text-suave">
                      {naoLidas ? `${naoLidas} ${naoLidas > 1 ? "mensagens novas" : "mensagem nova"}` : (catalogo.rotulo.get(perfil.genero) ?? perfil.genero)}
                    </span>
                  </span>
                  {naoLidas > 0
                    ? <span className="flex size-6 items-center justify-center rounded-full bg-acento text-xs font-bold text-white">{naoLidas}</span>
                    : <ChevronRight className="size-5 text-suave" aria-hidden />}
                </button>
              </motion.li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
