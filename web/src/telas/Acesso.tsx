// Telas curtas do caminho de acesso: link do e-mail, biometria, termos e verificação de idade.
import { BadgeCheck, FileText, Fingerprint, Link2Off, ScanFace } from "lucide-react";
import { useEffect, useState } from "react";
import { useAvisos } from "../componentes/avisos";
import { Botao, CarregandoTela, Cartao, Nota } from "../componentes/ui";
import { api } from "../lib/api";
import { adicionarPasskey, suportaPasskeys } from "../lib/passkeys";
import { irPara } from "../lib/roteador";
import type { SituacaoIdade, SituacaoTermos, Token, VersaoTermos } from "../lib/tipos";
import { useCarregar } from "../lib/useCarregar";

function Destaque({ icone, titulo, children }: { icone: React.ReactNode; titulo: string; children: React.ReactNode }) {
  return (
    <div className="pt-6">
      <div className="gradiente-marca mb-6 flex size-16 items-center justify-center rounded-3xl text-white shadow-lg">{icone}</div>
      <h1 className="text-[28px] font-bold leading-tight tracking-tight">{titulo}</h1>
      <div className="mt-6">{children}</div>
    </div>
  );
}

const Lista = ({ itens }: { itens: string[] }) => (
  <ul className="space-y-2.5">
    {itens.map((t) => (
      <li key={t} className="flex gap-3 text-[15px] leading-relaxed">
        <BadgeCheck className="mt-0.5 size-5 shrink-0 text-acento-texto" aria-hidden /> {t}
      </li>
    ))}
  </ul>
);

/** Destino do link do e-mail (#/verificar/<token>). O token some do histórico na hora. */
export function TelaVerificar({ token }: { token: string | null }) {
  const [erro, setErro] = useState<string | null>(null);
  useEffect(() => {
    history.replaceState(null, "", "#/verificando");
    api<Token>("/auth/email/link", { metodo: "POST", corpo: { token: token ?? "" } })
      .then((r) => irPara(r.novo && suportaPasskeys() ? "biometria" : "descobrir"))
      .catch((e) => setErro(e.message));
  }, [token]);
  if (!erro) return <CarregandoTela />;
  return (
    <Destaque icone={<Link2Off className="size-8" />} titulo="Link inválido">
      <Cartao>
        <Nota>{erro}</Nota>
        <Botao className="mt-5" cheio onClick={() => irPara("entrar")}>Voltar</Botao>
      </Cartao>
    </Destaque>
  );
}

export function TelaBiometria() {
  const { avisar } = useAvisos();
  const [ativando, setAtivando] = useState(false);
  const [erro, setErro] = useState("");
  useEffect(() => { if (!suportaPasskeys()) irPara("perfil"); }, []);

  async function ativar() {
    setAtivando(true);
    setErro("");
    try {
      await adicionarPasskey("Este aparelho");
      avisar("Biometria ativada");
      irPara("perfil");
    } catch (e) { setErro((e as Error).message); } finally { setAtivando(false); }
  }

  return (
    <Destaque icone={<Fingerprint className="size-8" />} titulo="Conta criada. Agora, a biometria">
      <Cartao className="space-y-4">
        <p className="text-[15px] leading-relaxed">
          Da próxima vez, entre só com a digital, o rosto ou o PIN deste aparelho, sem esperar código por e-mail.
        </p>
        <Nota>
          Sua digital e seu rosto nunca saem do aparelho: o app recebe só uma assinatura digital.
          Se trocar de celular, é só entrar com um código por e-mail e ativar de novo.
        </Nota>
        {erro && <p role="alert" className="text-sm font-medium text-perigo">{erro}</p>}
        <Botao cheio icone={<Fingerprint className="size-5" />} carregando={ativando} onClick={ativar}>Ativar biometria</Botao>
        <Botao cheio variante="fantasma" onClick={() => irPara("perfil")}>Agora não</Botao>
      </Cartao>
    </Destaque>
  );
}

export function TelaTermos() {
  const { avisar } = useAvisos();
  const [aceitando, setAceitando] = useState(false);
  const { dados, erro } = useCarregar(() => Promise.all([api<VersaoTermos>("/termos"), api<SituacaoTermos>("/termos/situacao")]));
  useEffect(() => { if (dados?.[1].aceita) irPara("descobrir"); }, [dados]);
  if (erro) return <Nota>{erro}</Nota>;
  if (!dados) return <CarregandoTela />;
  const [versao, situacao] = dados;
  const data = new Date(`${versao.versao}T12:00:00`).toLocaleDateString("pt-BR");

  async function aceitar() {
    setAceitando(true);
    try {
      await api("/termos/aceitar", { metodo: "POST", corpo: { versao: versao.versao } });
      avisar("Obrigado! Tudo certo.");
      irPara("descobrir");
    } catch (e) { avisar((e as Error).message); setAceitando(false); }
  }

  return (
    <Destaque icone={<FileText className="size-8" />} titulo={situacao.versao_aceita ? "Os termos mudaram" : "Termos e privacidade"}>
      <Cartao className="space-y-5">
        <p className="text-[15px] leading-relaxed">
          {situacao.versao_aceita
            ? `Atualizamos os termos de uso e a política de privacidade (versão de ${data}). Para continuar, leia e aceite.`
            : "Antes de ver perfis, leia e aceite os termos de uso e a política de privacidade."}
        </p>
        <Lista itens={[
          "Guardamos o mínimo e protegemos o que é sensível com criptografia.",
          "Seus dados sobre sexualidade são usados só para gerar compatibilidades, com o seu consentimento.",
          "Você pode excluir tudo, na hora, em Conta.",
        ]} />
        <p className="text-sm font-medium">
          <a className="text-acento-texto underline" href={versao.termos_url} target="_blank" rel="noopener">Termos de uso</a>{" · "}
          <a className="text-acento-texto underline" href={versao.privacidade_url} target="_blank" rel="noopener">Política de privacidade</a>
        </p>
        <Botao cheio carregando={aceitando} onClick={aceitar}>Li e aceito</Botao>
      </Cartao>
      <Nota className="mt-4 text-center">
        Não concorda? Você pode <a className="font-medium text-acento-texto underline" href="#/conta">excluir sua conta</a> agora.
      </Nota>
    </Destaque>
  );
}

/** Verificação de idade (ECA Digital). Quem verifica é um provedor externo; aqui fica só o resultado. */
export function TelaIdade() {
  const { avisar } = useAvisos();
  const [iniciando, setIniciando] = useState(false);
  const { dados: s, erro } = useCarregar(() => api<SituacaoIdade>("/idade"));
  if (erro) return <Nota>{erro}</Nota>;
  if (!s) return <CarregandoTela />;

  if (s.verificada) {
    return (
      <Destaque icone={<BadgeCheck className="size-8" />} titulo="Idade verificada">
        <Cartao>
          <p>Tudo certo: sua idade já foi confirmada.</p>
          <Botao className="mt-5" cheio onClick={() => irPara("descobrir")}>Ir para Descobrir</Botao>
        </Cartao>
      </Destaque>
    );
  }

  async function iniciar() {
    setIniciando(true);
    try {
      const { url } = await api<{ url: string }>("/idade/iniciar", { metodo: "POST" });
      location.assign(url);
    } catch (e) { avisar((e as Error).message); setIniciando(false); }
  }

  return (
    <Destaque icone={<ScanFace className="size-8" />} titulo="Confirme sua idade">
      <Cartao className="space-y-5">
        <p className="text-[15px] leading-relaxed">
          Por lei (ECA Digital), só pessoas adultas com idade confirmada podem ver perfis, curtir e conversar.
        </p>
        <Lista itens={[
          "A verificação é feita por uma empresa especializada: uma selfie com prova de vida.",
          "O Afinidade recebe só o resultado (maior de idade: sim ou não).",
          "Nenhuma foto, documento ou CPF fica guardado aqui.",
        ]} />
        {!s.disponivel && <Nota>A verificação está indisponível no momento. Tente mais tarde.</Nota>}
        <Botao cheio disabled={!s.disponivel} carregando={iniciando} onClick={iniciar}>
          {s.pendente ? "Continuar a verificação" : "Verificar minha idade"}
        </Botao>
      </Cartao>
      <Nota className="mt-4 text-center">
        Enquanto isso, você pode montar seu perfil. <a className="font-medium text-acento-texto underline" href="#/perfil">Ir para o perfil</a>
      </Nota>
    </Destaque>
  );
}

/** "Página do provedor" de mentira: só existe em desenvolvimento (a API recusa em produção). */
export function TelaIdadeSimulada({ sessao }: { sessao: string | null }) {
  const { avisar } = useAvisos();
  const id = encodeURIComponent(sessao || "-");
  const concluir = (aprovar: boolean) => async () => {
    try {
      await api(`/idade/simulado/${id}`, { metodo: "POST", corpo: { aprovar } });
      avisar(aprovar ? "Idade confirmada (simulação)" : "Verificação recusada (simulação)");
    } catch (e) { avisar((e as Error).message); }
    irPara("idade");
  };
  return (
    <Destaque icone={<ScanFace className="size-8" />} titulo="Provedor simulado">
      <Cartao>
        <Nota>Esta tela só existe em desenvolvimento e faz o papel da empresa que verifica a idade.</Nota>
        <div className="mt-5 flex gap-3">
          <Botao variante="secundario" cheio onClick={concluir(false)}>Recusar</Botao>
          <Botao cheio onClick={concluir(true)}>Aprovar</Botao>
        </div>
      </Cartao>
    </Destaque>
  );
}
