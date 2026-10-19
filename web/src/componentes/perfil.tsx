// Peças ligadas a perfis de outras pessoas: anel de afinidade, fotos protegidas e denúncia.
import { Eye, Flag, Lock, ShieldBan } from "lucide-react";
import { useState } from "react";
import { api } from "../lib/api";
import type { Foto, MotivoDenuncia } from "../lib/tipos";
import { useAvisos } from "./avisos";
import { AreaTexto, Botao, Folha, Marcar, Nota, Seletor } from "./ui";

export function AnelAfinidade({ valor, tamanho = 64, claro }: { valor: number; tamanho?: number; claro?: boolean }) {
  const raio = 26;
  const volta = 2 * Math.PI * raio;
  return (
    <div className="relative shrink-0" style={{ width: tamanho, height: tamanho }} role="img" aria-label={`${valor}% de afinidade`}>
      <svg viewBox="0 0 64 64" className="size-full -rotate-90">
        <defs>
          <linearGradient id="anel" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor="#e11d48" />
            <stop offset="1" stopColor="#8b5cf6" />
          </linearGradient>
        </defs>
        <circle cx="32" cy="32" r={raio} fill="none" strokeWidth="6" className={claro ? "stroke-white/25" : "stroke-superficie-2"} />
        <circle cx="32" cy="32" r={raio} fill="none" strokeWidth="6" strokeLinecap="round" stroke="url(#anel)"
          strokeDasharray={volta} strokeDashoffset={volta * (1 - Math.min(100, Math.max(0, valor)) / 100)} />
      </svg>
      <span className={`absolute inset-0 flex flex-col items-center justify-center leading-none ${claro ? "text-white" : ""}`}>
        <span className="text-[15px] font-bold">{valor}%</span>
      </span>
    </div>
  );
}

/**
 * Fotos de outra pessoa. Quem não foi autorizado recebe do SERVIDOR uma versão já borrada
 * (a nítida nunca chega ao navegador); o blur aqui só suaviza a miniatura.
 */
export function FotoProtegida({ foto, className }: { foto: Foto; className?: string }) {
  return (
    <div className={`relative overflow-hidden bg-superficie-2 ${className ?? ""}`}>
      <img src={foto.url} alt="Foto do perfil" loading="lazy" draggable={false}
        className={`size-full object-cover ${foto.nitida ? "" : "scale-110 blur-xl"}`} />
      {!foto.nitida && (
        <span className="absolute left-3 top-3 inline-flex items-center gap-1.5 rounded-full bg-black/45 px-3 py-1 text-xs font-medium text-white backdrop-blur">
          <Lock className="size-3.5" aria-hidden /> Foto protegida
        </span>
      )}
    </div>
  );
}

export function usePedirFotos() {
  const { avisar } = useAvisos();
  return async (perfilId: string) => {
    const { status } = await api<{ status: string }>(`/perfis/${perfilId}/fotos/solicitar`, { metodo: "POST" });
    avisar(status === "negado" ? "O acesso não foi liberado." : "Pedido enviado. As fotos ficam nítidas se a pessoa aprovar.");
  };
}

const MOTIVOS: [MotivoDenuncia, string][] = [
  ["assedio", "Assédio"], ["menor_de_idade", "Parece menor de idade"], ["perfil_falso", "Perfil falso"],
  ["spam", "Spam ou golpe"], ["conteudo_ilegal", "Conteúdo ilegal"], ["discurso_de_odio", "Discurso de ódio"],
  ["outro", "Outro motivo"],
];

/** Menu de segurança de um perfil: pedir fotos, bloquear e denunciar. Denunciar também bloqueia. */
export function MenuSeguranca({ aberto, aoFechar, perfilId, nome, comMensagens, comFotosBorradas, aoRemover }: {
  aberto: boolean; aoFechar: () => void; perfilId: string; nome: string;
  comMensagens?: boolean; comFotosBorradas?: boolean; aoRemover: () => void;
}) {
  const { avisar, confirmar } = useAvisos();
  const pedirFotos = usePedirFotos();
  const [modo, setModo] = useState<"menu" | "denunciar">("menu");
  const [motivo, setMotivo] = useState<MotivoDenuncia>("assedio");
  const [detalhes, setDetalhes] = useState("");
  const [anexar, setAnexar] = useState(true);
  const [enviando, setEnviando] = useState(false);

  const fechar = () => { aoFechar(); setTimeout(() => setModo("menu"), 300); };

  async function bloquear() {
    const sim = await confirmar({
      titulo: `Bloquear ${nome}?`, texto: "Vocês deixam de se ver para sempre. A pessoa não é avisada.",
      confirmar: "Bloquear", perigo: true,
    });
    if (!sim) return;
    await api(`/perfis/${perfilId}/bloquear`, { metodo: "POST" });
    fechar();
    aoRemover();
    avisar("Perfil bloqueado");
  }

  async function denunciar() {
    setEnviando(true);
    try {
      await api(`/perfis/${perfilId}/denunciar`, { metodo: "POST", corpo: {
        motivo, detalhes: detalhes || null, incluir_mensagens: Boolean(comMensagens && anexar),
      } });
      fechar();
      aoRemover();
      avisar("Denúncia enviada. Obrigado por proteger a comunidade.");
    } catch (e) {
      avisar((e as Error).message);
    } finally {
      setEnviando(false);
    }
  }

  return (
    <Folha aberta={aberto} aoFechar={fechar} titulo={modo === "menu" ? nome : "Denunciar"}>
      {modo === "menu" ? (
        <div className="space-y-2">
          {comFotosBorradas && (
            <Botao variante="secundario" cheio icone={<Eye className="size-4" />}
              onClick={async () => { await pedirFotos(perfilId); fechar(); }}>
              Pedir para ver as fotos
            </Botao>
          )}
          <Botao variante="secundario" cheio icone={<ShieldBan className="size-4" />} onClick={bloquear}>Bloquear</Botao>
          <Botao variante="secundario" cheio icone={<Flag className="size-4" />} className="text-perigo" onClick={() => setModo("denunciar")}>
            Denunciar
          </Botao>
        </div>
      ) : (
        <div className="space-y-4">
          <Seletor rotulo="Motivo" value={motivo} onChange={(e) => setMotivo(e.target.value as MotivoDenuncia)}>
            {MOTIVOS.map(([v, t]) => <option key={v} value={v}>{t}</option>)}
          </Seletor>
          <AreaTexto rotulo="Detalhes (opcional)" maxLength={1000} value={detalhes} onChange={(e) => setDetalhes(e.target.value)} />
          {comMensagens && (
            <Marcar marcado={anexar} aoMudar={setAnexar}>Anexar as mensagens recentes como evidência</Marcar>
          )}
          <Nota>A pessoa não fica sabendo quem denunciou. Vocês deixam de se ver.</Nota>
          <Botao variante="perigo" cheio carregando={enviando} onClick={denunciar}>Enviar denúncia</Botao>
        </div>
      )}
    </Folha>
  );
}
