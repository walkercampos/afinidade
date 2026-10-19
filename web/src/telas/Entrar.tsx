// Acesso sem senha: a conta nasce pelo e-mail (código de 6 dígitos); depois, biometria (passkey).
import { ArrowLeft, Fingerprint, Lock, Mail, ShieldCheck, Sparkles } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { type FormEvent, useEffect, useRef, useState } from "react";
import { useAvisos } from "../componentes/avisos";
import { Marca } from "../componentes/estrutura";
import { Botao, Campo, Cartao, Marcar, Nota, Segmentado } from "../componentes/ui";
import { api, MODO_DEMO } from "../lib/api";
import { entrarComPasskey, suportaPasskeys } from "../lib/passkeys";
import { irPara } from "../lib/roteador";
import type { Token, VerificacaoEnviada, VersaoTermos } from "../lib/tipos";

export async function aceitarTermosAtuais() {
  const { versao } = await api<VersaoTermos>("/termos");
  return api("/termos/aceitar", { metodo: "POST", corpo: { versao } });
}

const destinoDepoisDoLogin = (r: Token) => (r.novo && suportaPasskeys() ? "biometria" : "descobrir");

/** Seis caixas para o código; colar o código inteiro preenche todas. */
function CampoCodigo({ valor, aoMudar }: { valor: string; aoMudar: (v: string) => void }) {
  const refs = useRef<(HTMLInputElement | null)[]>([]);
  useEffect(() => { refs.current[0]?.focus(); }, []);
  const digitos = valor.padEnd(6, " ").slice(0, 6).split("");

  function definir(i: number, texto: string) {
    const so = texto.replace(/\D/g, "");
    if (so.length > 1) {
      aoMudar(so.slice(0, 6));
      refs.current[Math.min(5, so.length)]?.focus();
      return;
    }
    const novo = digitos.map((d, j) => (j === i ? so || " " : d)).join("").trimEnd();
    aoMudar(novo.replace(/ /g, ""));
    if (so && i < 5) refs.current[i + 1]?.focus();
  }

  return (
    <div className="flex justify-between gap-2" role="group" aria-label="Código de 6 dígitos">
      {digitos.map((d, i) => (
        <input
          key={i}
          ref={(el) => { refs.current[i] = el; }}
          value={d.trim()}
          inputMode="numeric"
          autoComplete={i === 0 ? "one-time-code" : "off"}
          aria-label={`Dígito ${i + 1}`}
          maxLength={6}
          onChange={(e) => definir(i, e.target.value)}
          onKeyDown={(e) => { if (e.key === "Backspace" && !d.trim() && i > 0) refs.current[i - 1]?.focus(); }}
          className="h-14 w-full min-w-0 rounded-2xl border border-transparent bg-superficie-2 text-center text-2xl font-semibold outline-none transition focus:border-acento focus:bg-superficie"
        />
      ))}
    </div>
  );
}

function EtapaCodigo({ email, verificacaoId, reenviar, voltar, aceitouTermos }: {
  email: string; verificacaoId: string; reenviar: () => Promise<void>; voltar: () => void; aceitouTermos: boolean;
}) {
  const { avisar } = useAvisos();
  const [codigo, setCodigo] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState("");

  async function confirmar(e?: FormEvent) {
    e?.preventDefault();
    if (codigo.length !== 6) return;
    setEnviando(true);
    setErro("");
    try {
      const r = await api<Token>("/auth/email/confirmar", { metodo: "POST", corpo: { verificacao_id: verificacaoId, codigo } });
      // A pessoa marcou "Li e aceito" no cadastro: registra o aceite da versão atual.
      if (aceitouTermos) await aceitarTermosAtuais().catch(() => avisar("Aceite os termos para continuar."));
      irPara(destinoDepoisDoLogin(r));
    } catch (e) {
      setErro((e as Error).message);
      setEnviando(false);
    }
  }

  useEffect(() => { if (codigo.length === 6) confirmar(); }, [codigo]);

  return (
    <form onSubmit={confirmar} className="space-y-5">
      <button type="button" onClick={voltar} className="inline-flex items-center gap-1 text-sm font-medium text-suave hover:text-texto">
        <ArrowLeft className="size-4" /> Voltar
      </button>
      <div className="flex size-14 items-center justify-center rounded-2xl bg-acento-suave text-acento-texto"><Mail className="size-7" /></div>
      <div>
        <h2 className="text-xl font-semibold">Confira seu e-mail</h2>
        <Nota className="mt-1">
          Enviamos um código de 6 dígitos para <strong className="text-texto">{email}</strong>. Ele vale por 15 minutos.
          Também dá para abrir o link do e-mail neste aparelho.
          {MODO_DEMO && " No modo demonstração, use 123456."}
        </Nota>
      </div>
      <CampoCodigo valor={codigo} aoMudar={setCodigo} />
      {erro && <p role="alert" className="text-sm font-medium text-perigo">{erro}</p>}
      <Botao type="submit" cheio carregando={enviando} disabled={codigo.length !== 6}>Confirmar</Botao>
      <button type="button" onClick={() => reenviar().then(() => avisar("Enviamos outro código"))}
        className="block w-full text-center text-sm font-medium text-acento-texto">
        Não chegou? Enviar outro código
      </button>
    </form>
  );
}

function FormEntrar({ aoPedir }: { aoPedir: (email: string) => Promise<void> }) {
  const [email, setEmail] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [entrandoBio, setEntrandoBio] = useState(false);
  const [erro, setErro] = useState("");
  const bio = suportaPasskeys();

  async function enviar(e: FormEvent) {
    e.preventDefault();
    setEnviando(true);
    setErro("");
    try { await aoPedir(email); } catch (e) { setErro((e as Error).message); } finally { setEnviando(false); }
  }

  async function biometria() {
    setEntrandoBio(true);
    setErro("");
    try { irPara(destinoDepoisDoLogin(await entrarComPasskey())); } catch (e) { setErro((e as Error).message); } finally { setEntrandoBio(false); }
  }

  return (
    <div className="space-y-5">
      {bio && (
        <>
          <Botao cheio icone={<Fingerprint className="size-5" />} carregando={entrandoBio} onClick={biometria}>
            Entrar com biometria
          </Botao>
          <Nota className="text-center">Digital, rosto ou PIN do aparelho em que você ativou a biometria.</Nota>
          <div className="flex items-center gap-3 text-xs font-medium uppercase tracking-wider text-suave">
            <span className="h-px flex-1 bg-borda" /> aparelho novo? <span className="h-px flex-1 bg-borda" />
          </div>
        </>
      )}
      <form onSubmit={enviar} className="space-y-4">
        <Campo rotulo="E-mail" type="email" required autoComplete="email" autoCapitalize="none" spellCheck={false}
          maxLength={254} value={email} onChange={(e) => setEmail(e.target.value)} placeholder="voce@exemplo.com" />
        {erro && <p role="alert" className="text-sm font-medium text-perigo">{erro}</p>}
        <Botao type="submit" variante={bio ? "secundario" : "primario"} cheio carregando={enviando}>Receber código por e-mail</Botao>
      </form>
    </div>
  );
}

interface DadosCadastro {
  email: string; handle: string | null; data_nascimento: string;
  confirmo_maior_de_idade: boolean; consinto_dados_sensiveis: boolean;
}

function FormCriar({ aoPedir }: { aoPedir: (d: DadosCadastro) => Promise<void> }) {
  const [email, setEmail] = useState("");
  const [handle, setHandle] = useState("");
  const [nascimento, setNascimento] = useState("");
  const [maior, setMaior] = useState(false);
  const [consinto, setConsinto] = useState(false);
  const [termos, setTermos] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState("");

  async function enviar(e: FormEvent) {
    e.preventDefault();
    if (!maior || !consinto || !termos) { setErro("Marque as três confirmações para continuar."); return; }
    setEnviando(true);
    setErro("");
    try {
      await aoPedir({ email, handle: handle || null, data_nascimento: nascimento, confirmo_maior_de_idade: maior, consinto_dados_sensiveis: consinto });
    } catch (e) { setErro((e as Error).message); } finally { setEnviando(false); }
  }

  return (
    <form onSubmit={enviar} className="space-y-4">
      <Campo rotulo="E-mail" type="email" required autoComplete="email" autoCapitalize="none" spellCheck={false} maxLength={254}
        value={email} onChange={(e) => setEmail(e.target.value)}
        dica="Nunca aparece para ninguém e fica guardado criptografado. Para mais discrição, use um e-mail só para isso ou um alias (Ocultar meu e-mail do iCloud, Firefox Relay)." />
      <Campo rotulo="Apelido (opcional)" autoComplete="nickname" autoCapitalize="none" spellCheck={false}
        pattern="[a-zA-Z0-9_]{3,30}" maxLength={30} value={handle} onChange={(e) => setHandle(e.target.value)}
        dica="Em branco, você recebe um apelido aleatório. Não use o mesmo de outras redes." />
      <Campo rotulo="Data de nascimento" type="date" required value={nascimento} onChange={(e) => setNascimento(e.target.value)}
        dica="Usada só para confirmar a maioridade. Não é armazenada." />
      <div className="space-y-1 rounded-2xl bg-superficie-2 p-3">
        <Marcar marcado={maior} aoMudar={setMaior}>Tenho 18 anos ou mais.</Marcar>
        <Marcar marcado={consinto} aoMudar={setConsinto}>
          Consinto com o tratamento dos meus dados sobre sexualidade para gerar compatibilidades. Posso excluir tudo a qualquer momento.
        </Marcar>
        <Marcar marcado={termos} aoMudar={setTermos}>
          Li e aceito os <a className="font-medium text-acento-texto underline" href="/termos.html" target="_blank" rel="noopener">termos de uso</a>{" "}
          e a <a className="font-medium text-acento-texto underline" href="/privacidade.html" target="_blank" rel="noopener">política de privacidade</a>.
        </Marcar>
      </div>
      {erro && <p role="alert" className="text-sm font-medium text-perigo">{erro}</p>}
      <Botao type="submit" cheio carregando={enviando}>Enviar código de confirmação</Botao>
    </form>
  );
}

const DESTAQUES = [
  { Icone: Sparkles, texto: "Afinidade calculada pelos gostos, não pela aparência" },
  { Icone: Lock, texto: "Fotos borradas até você liberar, chat que se apaga" },
  { Icone: ShieldCheck, texto: "Sem nome, sem telefone, sem senha" },
];

export function TelaEntrar() {
  const [modo, setModo] = useState<"entrar" | "criar">("entrar");
  const [codigo, setCodigo] = useState<{ email: string; id: string; reenviar: () => Promise<void>; termos: boolean } | null>(null);

  async function pedirEntrar(email: string) {
    const { verificacao_id } = await api<VerificacaoEnviada>("/auth/email/entrar", { metodo: "POST", corpo: { email } });
    setCodigo({ email, id: verificacao_id, termos: false, reenviar: () => pedirEntrar(email) });
  }

  async function pedirCadastro(dados: DadosCadastro) {
    const { verificacao_id } = await api<VerificacaoEnviada>("/auth/email/cadastro", { metodo: "POST", corpo: dados });
    setCodigo({ email: dados.email, id: verificacao_id, termos: true, reenviar: () => pedirCadastro(dados) });
  }

  return (
    <div className="relative">
      {/* brilho de fundo, recortado para não criar rolagem lateral */}
      <div className="pointer-events-none fixed inset-x-0 top-0 h-96 overflow-hidden" aria-hidden>
        <div className="gradiente-marca absolute -left-1/4 -top-48 h-80 w-[150%] opacity-20 blur-3xl" />
      </div>
      <div className="relative pt-8">
        <Marca grande />
        <h1 className="mt-8 text-[32px] font-bold leading-[1.1] tracking-tight">
          Conexões por afinidade, <span className="texto-gradiente">sem expor quem você é.</span>
        </h1>
        <ul className="mt-6 space-y-2.5">
          {DESTAQUES.map(({ Icone, texto }) => (
            <li key={texto} className="flex items-center gap-3 text-[15px] text-suave">
              <Icone className="size-5 shrink-0 text-acento-texto" aria-hidden /> {texto}
            </li>
          ))}
        </ul>

        <Cartao className="mt-8">
          <AnimatePresence mode="wait">
            <motion.div key={codigo ? "codigo" : modo} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} transition={{ duration: 0.18 }}>
              {codigo ? (
                <EtapaCodigo email={codigo.email} verificacaoId={codigo.id} reenviar={codigo.reenviar}
                  aceitouTermos={codigo.termos} voltar={() => setCodigo(null)} />
              ) : (
                <div className="space-y-5">
                  <Segmentado rotulo="Acesso" valor={modo} aoMudar={setModo} opcoes={[["entrar", "Entrar"], ["criar", "Criar conta"]]} />
                  {modo === "entrar" ? <FormEntrar aoPedir={pedirEntrar} /> : <FormCriar aoPedir={pedirCadastro} />}
                </div>
              )}
            </motion.div>
          </AnimatePresence>
        </Cartao>
        <Nota className="mt-5 text-center">Em qualquer tela, aperte <kbd className="rounded-md border border-borda px-1.5 py-0.5 font-mono text-xs">ESC</kbd> ou o botão vermelho para sair na hora.</Nota>
      </div>
    </div>
  );
}
