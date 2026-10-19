import { ChevronRight, Fingerprint, KeyRound, LogOut, Shield, Smartphone, Trash2, Zap } from "lucide-react";
import { useState } from "react";
import { useAvisos } from "../componentes/avisos";
import { Botao, CabecalhoTela, CarregandoTela, Campo, Cartao, Folha, Interruptor, Nota, Segmentado, TituloSecao } from "../componentes/ui";
import { api } from "../lib/api";
import { aplicarDiscreto, aplicarTema, type Tema, temaAtual } from "../lib/discricao";
import { adicionarPasskey, suportaPasskeys } from "../lib/passkeys";
import { irPara } from "../lib/roteador";
import type { MinhaConta, PasskeySalva, Preferencias } from "../lib/tipos";
import { useCarregar } from "../lib/useCarregar";
import { dataCurta } from "../lib/util";

function Linha({ icone, titulo, descricao, aoClicar }: { icone: React.ReactNode; titulo: string; descricao: string; aoClicar: () => void }) {
  return (
    <button type="button" onClick={aoClicar} className="flex w-full items-center gap-4 py-3 text-left">
      <span className="flex size-10 shrink-0 items-center justify-center rounded-2xl bg-acento-suave text-acento-texto">{icone}</span>
      <span className="min-w-0 flex-1">
        <span className="block font-medium">{titulo}</span>
        <span className="block text-sm text-suave">{descricao}</span>
      </span>
      <ChevronRight className="size-5 text-suave" aria-hidden />
    </button>
  );
}

function SecaoPasskeys() {
  const { avisar, confirmar } = useAvisos();
  const { dados: lista, recarregar } = useCarregar(() => api<PasskeySalva[]>("/passkeys"));
  const [nomeando, setNomeando] = useState(false);
  const [nome, setNome] = useState("");
  const [ativando, setAtivando] = useState(false);

  async function ativar() {
    setAtivando(true);
    try {
      await adicionarPasskey(nome);
      avisar("Biometria ativada neste aparelho");
      setNomeando(false);
      setNome("");
      recarregar();
    } catch (e) { avisar((e as Error).message); } finally { setAtivando(false); }
  }

  async function remover(p: PasskeySalva) {
    if (!(await confirmar({ titulo: `Remover “${p.nome}”?`, texto: "Esse aparelho deixa de entrar com biometria.", confirmar: "Remover", perigo: true }))) return;
    await api(`/passkeys/${p.id}`, { metodo: "DELETE" });
    avisar("Passkey removida");
    recarregar();
  }

  return (
    <Cartao>
      <TituloSecao>Biometria</TituloSecao>
      <Nota>
        {lista?.length
          ? "Você entra com a digital, o rosto ou o PIN destes aparelhos. Perdeu um? Entre por e-mail e remova-o aqui."
          : "Ative a biometria para entrar com a digital, o rosto ou o PIN, sem esperar código por e-mail."}
      </Nota>
      {lista && lista.length > 0 && (
        <ul className="mt-3 divide-y divide-borda">
          {lista.map((p) => (
            <li key={p.id} className="flex items-center gap-3 py-3">
              <span className="flex size-10 shrink-0 items-center justify-center rounded-2xl bg-superficie-2"><Smartphone className="size-5" /></span>
              <span className="min-w-0 flex-1">
                <span className="block truncate font-medium">{p.nome}</span>
                <span className="block text-xs text-suave">
                  {p.sincronizada ? "sincronizada" : "só neste aparelho"} · último uso {dataCurta(p.usado_em)}
                </span>
              </span>
              <Botao pequeno variante="secundario" onClick={() => remover(p)}>Remover</Botao>
            </li>
          ))}
        </ul>
      )}
      {suportaPasskeys() && (
        <Botao className="mt-4" cheio variante="suave" icone={<Fingerprint className="size-5" />} onClick={() => setNomeando(true)}>
          Ativar neste aparelho
        </Botao>
      )}
      <Folha aberta={nomeando} aoFechar={() => setNomeando(false)} titulo="Ativar biometria">
        <Campo rotulo="Nome para este aparelho" placeholder="ex.: Celular" maxLength={40} value={nome} onChange={(e) => setNome(e.target.value)} />
        <Botao className="mt-5" cheio carregando={ativando} onClick={ativar}>Continuar</Botao>
      </Folha>
    </Cartao>
  );
}

function SecaoAparencia({ preferencias }: { preferencias: Preferencias }) {
  const { avisar } = useAvisos();
  const [tema, setTema] = useState<Tema>(temaAtual());
  const [discreto, setDiscreto] = useState(preferencias.modo_discreto);

  async function mudarDiscreto(ligado: boolean) {
    setDiscreto(ligado);
    try {
      await api("/conta/preferencias", { metodo: "PUT", corpo: { modo_discreto: ligado } });
      aplicarDiscreto(ligado);
      avisar(ligado ? "Modo discreto ligado" : "Modo discreto desligado");
    } catch (e) { setDiscreto(!ligado); avisar((e as Error).message); }
  }

  return (
    <Cartao>
      <TituloSecao>Aparência e discrição</TituloSecao>
      <Segmentado rotulo="Tema" valor={tema} aoMudar={(t) => { setTema(t); aplicarTema(t); }}
        opcoes={[["sistema", "Automático"], ["claro", "Claro"], ["escuro", "Escuro"]]} />
      <div className="mt-4">
        <Interruptor rotulo="Modo discreto" ligado={discreto} aoMudar={mudarDiscreto}
          descricao="Na aba do navegador, no histórico e na tela inicial o app aparece como “Notas”, com um ícone neutro." />
      </div>
    </Cartao>
  );
}

export function TelaConta() {
  const { avisar, confirmar } = useAvisos();
  const { dados, erro } = useCarregar(() => Promise.all([api<MinhaConta>("/conta"), api<Preferencias>("/conta/preferencias")]));
  if (erro) return <Nota>{erro}</Nota>;
  if (!dados) return <CarregandoTela />;
  const [conta, preferencias] = dados;

  async function sair() {
    await api("/auth/sair", { metodo: "POST" });
    irPara("entrar");
  }

  async function excluir() {
    const primeira = await confirmar({
      titulo: "Excluir sua conta?", confirmar: "Continuar", perigo: true,
      texto: "Apaga definitivamente perfil, fotos, interesses, curtidas, conexões e mensagens. Não há como desfazer.",
    });
    if (!primeira) return;
    const segunda = await confirmar({ titulo: "Tem certeza?", texto: "Última confirmação: tudo será apagado agora.", confirmar: "Excluir tudo", perigo: true });
    if (!segunda) return;
    await api("/conta", { metodo: "DELETE" });
    irPara("entrar");
    avisar("Conta excluída");
  }

  return (
    <div className="space-y-4">
      <CabecalhoTela titulo="Conta" />
      <Cartao>
        <div className="flex items-center gap-4">
          <span className="gradiente-marca flex size-14 items-center justify-center rounded-2xl text-white"><KeyRound className="size-6" /></span>
          <div className="min-w-0">
            <p className="truncate text-lg font-semibold">@{conta.handle}</p>
            <p className="truncate text-sm text-suave">{conta.email ?? "E-mail ainda não registrado"}</p>
          </div>
        </div>
        <Nota className="mt-3">
          {conta.email
            ? "Seu e-mail fica guardado criptografado e é usado só para códigos de acesso e avisos sobre a conta."
            : "Entre uma vez com um código por e-mail para registrar o e-mail de acesso."}
        </Nota>
      </Cartao>

      <Cartao className="py-2">
        <div className="divide-y divide-borda">
          {conta.moderador && (
            <Linha icone={<Shield className="size-5" />} titulo="Moderação" descricao="Fila de denúncias e decisões" aoClicar={() => irPara("moderacao")} />
          )}
          <Linha icone={<Zap className="size-5" />} titulo="Encontro seguro" descricao="Avisa um contato se você não fizer o check-in" aoClicar={() => irPara("encontros")} />
        </div>
      </Cartao>

      <SecaoPasskeys />
      <SecaoAparencia preferencias={preferencias} />

      <Cartao>
        <TituloSecao>Saída rápida</TituloSecao>
        <Nota>Aperte ESC ou o botão vermelho a qualquer momento: a tela some, a sessão é encerrada e você vai para o Google.</Nota>
      </Cartao>

      <Cartao className="space-y-3">
        <Botao variante="secundario" cheio icone={<LogOut className="size-4" />} onClick={sair}>Sair de todos os dispositivos</Botao>
        <Botao variante="fantasma" cheio icone={<Trash2 className="size-4" />} className="text-perigo hover:bg-perigo/10" onClick={excluir}>Excluir conta</Botao>
      </Cartao>
    </div>
  );
}
