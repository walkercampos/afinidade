import { motion } from "motion/react";
import type { ReactNode } from "react";
import { Estrutura } from "./componentes/estrutura";
import { useRota } from "./lib/roteador";
import { TelaBiometria, TelaIdade, TelaIdadeSimulada, TelaTermos, TelaVerificar } from "./telas/Acesso";
import { TelaChat } from "./telas/Chat";
import { TelaConexoes } from "./telas/Conexoes";
import { TelaConta } from "./telas/Conta";
import { TelaDescobrir } from "./telas/Descobrir";
import { TelaEncontros } from "./telas/Encontros";
import { TelaEntrar } from "./telas/Entrar";
import { TelaModeracao } from "./telas/Moderacao";
import { TelaPerfil } from "./telas/Perfil";

const SEM_MENU = new Set(["entrar", "verificar", "verificando", "biometria", "idade-simulada"]);

function tela(rota: string, parametro: string | null): ReactNode {
  switch (rota) {
    case "entrar": return <TelaEntrar />;
    case "verificar": return <TelaVerificar token={parametro} />;
    case "verificando": return null;
    case "biometria": return <TelaBiometria />;
    case "termos": return <TelaTermos />;
    case "idade": return <TelaIdade />;
    case "idade-simulada": return <TelaIdadeSimulada sessao={parametro} />;
    case "conexoes": return <TelaConexoes />;
    case "chat": return <TelaChat outroId={parametro} />;
    case "encontros": return <TelaEncontros comQuem={parametro} />;
    case "perfil": return <TelaPerfil />;
    case "conta": return <TelaConta />;
    case "moderacao": return <TelaModeracao />;
    default: return <TelaDescobrir />;
  }
}

export function App() {
  const { rota, parametro, chave } = useRota();
  return (
    <Estrutura rota={rota} comMenu={!SEM_MENU.has(rota)}>
      <motion.div key={chave} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.2 }}>
        {tela(rota, parametro)}
      </motion.div>
    </Estrutura>
  );
}
