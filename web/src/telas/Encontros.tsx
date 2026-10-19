// Encontro seguro: quem você vai encontrar, onde e até quando fazer o check-in. Se o check-in
// não vier, o contato de confiança recebe um e-mail com os detalhes.
import { CalendarHeart, Clock, MapPin, Phone, Plus, ShieldAlert, UserRound } from "lucide-react";
import { type FormEvent, useState } from "react";
import { useAvisos } from "../componentes/avisos";
import { AreaTexto, Botao, CabecalhoTela, CarregandoTela, Campo, Cartao, Folha, Nota, Seletor, Vazio } from "../componentes/ui";
import { api } from "../lib/api";
import type { Encontro, PerfilPublico } from "../lib/tipos";
import { useCarregar } from "../lib/useCarregar";
import { dataHora, juntarClasses, paraCampoDataHora } from "../lib/util";

const SITUACOES: Record<string, [string, string]> = {
  agendado: ["Aguardando seu check-in", "bg-violeta-suave text-violeta"],
  confirmado_ok: ["Check-in feito: tudo bem", "bg-ok-suave text-ok"],
  alerta_enviado: ["Alerta enviado ao contato", "bg-perigo/10 text-perigo"],
  cancelado: ["Cancelado", "bg-superficie-2 text-suave"],
};

function FormEncontro({ conexoes, comQuem, aoCriar }: { conexoes: PerfilPublico[]; comQuem: string | null; aoCriar: () => void }) {
  const { avisar } = useAvisos();
  const inicioPadrao = new Date(Date.now() + 60 * 60_000);
  const [campos, setCampos] = useState({
    com: comQuem ?? "", local: "", inicio: paraCampoDataHora(inicioPadrao),
    checkin: paraCampoDataHora(new Date(inicioPadrao.getTime() + 3 * 60 * 60_000)),
    contato_email: "", como_te_conhecem: "", observacoes: "",
  });
  const [salvando, setSalvando] = useState(false);
  const mudar = (k: keyof typeof campos) => (e: { target: { value: string } }) => setCampos({ ...campos, [k]: e.target.value });

  async function salvar(e: FormEvent) {
    e.preventDefault();
    setSalvando(true);
    try {
      await api("/encontros", { metodo: "POST", corpo: {
        com: campos.com || null, local: campos.local, observacoes: campos.observacoes, como_te_conhecem: campos.como_te_conhecem,
        contato_email: campos.contato_email,
        inicio_em: new Date(campos.inicio).toISOString(), checkin_ate: new Date(campos.checkin).toISOString(),
      } });
      avisar("Encontro registrado. Avisamos seu contato de confiança.");
      aoCriar();
    } catch (e) { avisar((e as Error).message); } finally { setSalvando(false); }
  }

  return (
    <form onSubmit={salvar} className="space-y-4">
      <Seletor rotulo="Com quem" value={campos.com} onChange={mudar("com")}>
        <option value="">Prefiro não dizer</option>
        {conexoes.map((c) => <option key={c.id} value={c.id}>{c.nome_exibicao}</option>)}
      </Seletor>
      <Campo rotulo="Onde" required minLength={2} maxLength={200} placeholder="Nome e endereço do lugar" value={campos.local} onChange={mudar("local")} />
      <div className="grid gap-3 sm:grid-cols-2">
        <Campo rotulo="Começa" type="datetime-local" required value={campos.inicio} onChange={mudar("inicio")} />
        <Campo rotulo="Check-in até" type="datetime-local" required value={campos.checkin} onChange={mudar("checkin")} />
      </div>
      <Nota>Se você não tocar em “Estou bem” até o check-in, seu contato recebe o local, o horário e com quem você está.</Nota>
      <Campo rotulo="E-mail do contato de confiança" type="email" required autoComplete="off" autoCapitalize="none" spellCheck={false}
        maxLength={254} value={campos.contato_email} onChange={mudar("contato_email")} />
      <Campo rotulo="Como essa pessoa conhece você" maxLength={60} placeholder="ex.: Ana, sua irmã" value={campos.como_te_conhecem} onChange={mudar("como_te_conhecem")} />
      <AreaTexto rotulo="Observações (opcional)" maxLength={500} placeholder="ex.: volto de táxi às 23 h" value={campos.observacoes} onChange={mudar("observacoes")} />
      <Nota>Tudo fica guardado criptografado e é apagado 30 dias depois do encontro.</Nota>
      <Botao type="submit" cheio carregando={salvando}>Registrar encontro</Botao>
    </form>
  );
}

function CartaoEncontro({ e, aoMudar }: { e: Encontro; aoMudar: () => void }) {
  const { avisar } = useAvisos();
  const [texto, cores] = SITUACOES[e.situacao] ?? [e.situacao, "bg-superficie-2 text-suave"];
  return (
    <Cartao>
      <div className="flex items-start justify-between gap-3">
        <h3 className="flex items-center gap-2 text-[17px] font-semibold"><MapPin className="size-4 text-acento-texto" />{e.local}</h3>
        <span className={juntarClasses("shrink-0 rounded-full px-2.5 py-1 text-xs font-semibold", cores)}>{texto}</span>
      </div>
      <ul className="mt-3 space-y-1.5 text-sm text-suave">
        <li className="flex items-center gap-2"><Clock className="size-4" />{dataHora(e.inicio_em)} · check-in até {dataHora(e.checkin_ate)}</li>
        {e.com_nome && <li className="flex items-center gap-2"><UserRound className="size-4" />Com {e.com_nome}{e.com_handle && ` (@${e.com_handle})`}</li>}
        <li className="flex items-center gap-2"><ShieldAlert className="size-4" />Contato: {e.contato_email}</li>
      </ul>
      {e.situacao === "agendado" && (
        <div className="mt-4 flex gap-2">
          <Botao variante="secundario" className="flex-1" onClick={async () => { await api(`/encontros/${e.id}/cancelar`, { metodo: "POST" }); aoMudar(); }}>Cancelar</Botao>
          <Botao className="flex-1" onClick={async () => { await api(`/encontros/${e.id}/checkin`, { metodo: "POST" }); avisar("Check-in feito. Que bom!"); aoMudar(); }}>Estou bem</Botao>
        </div>
      )}
    </Cartao>
  );
}

export function TelaEncontros({ comQuem }: { comQuem: string | null }) {
  const { dados, erro, recarregar } = useCarregar(() => Promise.all([api<Encontro[]>("/encontros"), api<PerfilPublico[]>("/conexoes")]));
  const [novo, setNovo] = useState(Boolean(comQuem));
  if (erro) return <Nota>{erro}</Nota>;
  if (!dados) return <CarregandoTela />;
  const [lista, conexoes] = dados;

  return (
    <div className="space-y-4">
      <CabecalhoTela titulo="Encontro seguro" subtitulo="Vai encontrar alguém? Deixe registrado."
        acao={<Botao pequeno icone={<Plus className="size-4" />} onClick={() => setNovo(true)}>Novo</Botao>} />

      <section className="rounded-cartao bg-perigo/10 p-5">
        <h2 className="flex items-center gap-2 font-semibold text-perigo"><ShieldAlert className="size-5" />Em perigo agora?</h2>
        <div className="mt-3 grid grid-cols-2 gap-2">
          <a href="tel:190" className="flex min-h-12 items-center justify-center gap-2 rounded-full bg-perigo text-sm font-semibold text-white"><Phone className="size-4" />190 · Polícia</a>
          <a href="tel:180" className="flex min-h-12 items-center justify-center gap-2 rounded-full bg-superficie text-center text-sm font-semibold text-perigo"><Phone className="size-4" />180 · Mulher</a>
        </div>
      </section>

      {lista.length === 0 ? (
        <Vazio icone={<CalendarHeart className="size-9" />} titulo="Nenhum encontro registrado"
          acao={<Botao onClick={() => setNovo(true)}>Registrar encontro</Botao>}>
          Registre onde e com quem. Se você não fizer o check-in, um contato de confiança é avisado.
        </Vazio>
      ) : lista.map((e) => <CartaoEncontro key={e.id} e={e} aoMudar={recarregar} />)}

      <Folha aberta={novo} aoFechar={() => setNovo(false)} titulo="Novo encontro">
        <FormEncontro conexoes={conexoes} comQuem={comQuem} aoCriar={() => { setNovo(false); recarregar(); }} />
      </Folha>
    </div>
  );
}
