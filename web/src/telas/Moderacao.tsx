// Painel de moderação. Só aparece para quem tem o papel de moderador; a API responde 404 para
// qualquer outra pessoa. Casos graves primeiro; banir, restaurar e avisar por e-mail.
import { AlertTriangle, PartyPopper } from "lucide-react";
import { useEffect, useState } from "react";
import { useAvisos } from "../componentes/avisos";
import { AreaTexto, Botao, CabecalhoTela, CarregandoTela, Campo, Cartao, Folha, Nota, Vazio } from "../componentes/ui";
import { api, ErroApi } from "../lib/api";
import { irPara } from "../lib/roteador";
import type { ContaNaFila } from "../lib/tipos";
import { dataHora, juntarClasses } from "../lib/util";

const MOTIVOS: Record<string, string> = {
  menor_de_idade: "Menor de idade", conteudo_ilegal: "Conteúdo ilegal", assedio: "Assédio",
  perfil_falso: "Perfil falso", spam: "Spam", discurso_de_odio: "Discurso de ódio", outro: "Outro",
};
const GRAVES = new Set(["menor_de_idade", "conteudo_ilegal"]);

function CartaoCaso({ caso, aoDecidir }: { caso: ContaNaFila; aoDecidir: () => void }) {
  const { avisar } = useAvisos();
  const [decisao, setDecisao] = useState<"banir" | "restaurar" | null>(null);
  const [observacao, setObservacao] = useState("");
  const [aviso, setAviso] = useState(false);
  const [assunto, setAssunto] = useState("");
  const [mensagem, setMensagem] = useState("");
  const grave = caso.denuncias.some((d) => GRAVES.has(d.motivo));

  async function decidir() {
    if (!decisao) return;
    await api(`/moderacao/contas/${caso.conta_id}/decisao`, { metodo: "POST", corpo: { acao: decisao, observacao: observacao || null } });
    avisar(decisao === "banir" ? "Conta banida" : "Conta restaurada");
    setDecisao(null);
    aoDecidir();
  }

  async function enviarAviso() {
    try {
      await api(`/moderacao/contas/${caso.conta_id}/aviso`, { metodo: "POST", corpo: { assunto, mensagem } });
      avisar("Aviso enviado (o endereço não é mostrado a você)");
      setAviso(false);
    } catch (e) { avisar((e as Error).message); }
  }

  return (
    <Cartao className={juntarClasses(grave && "border-perigo")}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="font-semibold">@{caso.handle}</p>
          <p className="text-sm text-suave">{caso.situacao === "em_revisao" ? "Em revisão (oculta)" : "Ativa"}</p>
        </div>
        <span className={juntarClasses("rounded-full px-2.5 py-1 text-xs font-semibold", grave ? "bg-perigo text-white" : "bg-superficie-2")}>
          {caso.denuncias.length} denúncia{caso.denuncias.length > 1 ? "s" : ""}
        </span>
      </div>
      {caso.perfil && (
        <div className="mt-3 rounded-2xl bg-superficie-2 p-3 text-sm">
          <p><strong>{caso.perfil.nome_exibicao}</strong> · {caso.perfil.genero}</p>
          {caso.perfil.bio && <p className="mt-1 text-suave">{caso.perfil.bio}</p>}
        </div>
      )}
      <ul className="mt-3 space-y-2">
        {caso.denuncias.map((d) => (
          <li key={d.id} className={juntarClasses("rounded-2xl border p-3 text-sm", GRAVES.has(d.motivo) ? "border-perigo" : "border-borda")}>
            <p className="flex items-center gap-1.5">
              {GRAVES.has(d.motivo) && <AlertTriangle className="size-4 text-perigo" />}
              <strong>{MOTIVOS[d.motivo] ?? d.motivo}</strong>
              <span className="text-suave">· {dataHora(d.criado_em)}</span>
            </p>
            {d.detalhes && <p className="mt-1">{d.detalhes}</p>}
            {d.evidencias && (
              <details className="mt-2">
                <summary className="cursor-pointer font-medium text-acento-texto">Mensagens anexadas ({d.evidencias.length})</summary>
                <ol className="mt-2 space-y-1">
                  {d.evidencias.map((m, i) => (
                    <li key={i} className={m.de === "denunciado" ? "font-medium" : "text-suave"}><small>{m.de}: </small>{m.texto}</li>
                  ))}
                </ol>
              </details>
            )}
          </li>
        ))}
      </ul>
      <div className="mt-4 grid grid-cols-3 gap-2">
        <Botao pequeno variante="secundario" onClick={() => setAviso(true)}>Avisar</Botao>
        <Botao pequeno variante="secundario" onClick={() => setDecisao("restaurar")}>Restaurar</Botao>
        <Botao pequeno variante="perigo" onClick={() => setDecisao("banir")}>Banir</Botao>
      </div>

      <Folha aberta={Boolean(decisao)} aoFechar={() => setDecisao(null)} titulo={decisao === "banir" ? `Banir @${caso.handle}` : `Restaurar @${caso.handle}`}>
        <AreaTexto rotulo={decisao === "banir" ? "Motivo do banimento (fica no registro)" : "Observação (opcional)"} maxLength={1000}
          value={observacao} onChange={(e) => setObservacao(e.target.value)} />
        <Botao className="mt-4" cheio variante={decisao === "banir" ? "perigo" : "primario"} onClick={decidir}>Confirmar</Botao>
      </Folha>
      <Folha aberta={aviso} aoFechar={() => setAviso(false)} titulo="Aviso por e-mail">
        <div className="space-y-4">
          <Campo rotulo="Assunto" minLength={3} maxLength={120} value={assunto} onChange={(e) => setAssunto(e.target.value)} />
          <AreaTexto rotulo="Mensagem" minLength={3} maxLength={4000} rows={5} value={mensagem} onChange={(e) => setMensagem(e.target.value)} />
          <Nota>O endereço da pessoa nunca é mostrado a você.</Nota>
          <Botao cheio disabled={assunto.length < 3 || mensagem.length < 3} onClick={enviarAviso}>Enviar aviso</Botao>
        </div>
      </Folha>
    </Cartao>
  );
}

export function TelaModeracao() {
  const [fila, setFila] = useState<ContaNaFila[] | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const carregar = () => api<ContaNaFila[]>("/moderacao/fila").then(setFila).catch((e) => {
    if (e instanceof ErroApi && e.status === 404) irPara("descobrir"); // não é moderador(a)
    else setErro(e.message);
  });
  useEffect(() => { carregar(); }, []);

  if (erro) return <Nota>{erro}</Nota>;
  if (!fila) return <CarregandoTela />;
  return (
    <div className="space-y-4">
      <CabecalhoTela titulo="Moderação" subtitulo="Casos graves primeiro. Cada decisão fica registrada." />
      {fila.length === 0
        ? <Vazio icone={<PartyPopper className="size-9" />} titulo="Nenhum caso na fila">Tudo em ordem por aqui.</Vazio>
        : fila.map((c) => <CartaoCaso key={c.conta_id} caso={c} aoDecidir={carregar} />)}
    </div>
  );
}
