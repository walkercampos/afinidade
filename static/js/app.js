// Ponto de entrada do front-end: registra as telas e liga o botão de pânico.
import { ErroApi } from "./api.js";
import { avisar } from "./dom.js";
import { aplicarDiscreto, aplicarTema, sincronizarDiscreto } from "./discricao.js";
import { instalarPanico } from "./panico.js";
import { iniciarRoteador, registrarRota } from "./roteador.js";
import { telaBiometria } from "./telas/biometria.js";
import { telaChat } from "./telas/chat.js";
import { telaConexoes } from "./telas/conexoes.js";
import { telaConta } from "./telas/conta.js";
import { telaDescobrir } from "./telas/descobrir.js";
import { telaEncontros } from "./telas/encontros.js";
import { telaEntrar } from "./telas/entrar.js";
import { telaIdade, telaIdadeSimulada } from "./telas/idade.js";
import { telaModeracao } from "./telas/moderacao.js";
import { telaPerfil } from "./telas/perfil.js";
import { telaTermos } from "./telas/termos.js";
import { telaVerificar } from "./telas/verificar.js";

aplicarTema();
aplicarDiscreto();
instalarPanico();

registrarRota("entrar", telaEntrar, { comMenu: false });
registrarRota("verificar", telaVerificar, { comMenu: false });
registrarRota("biometria", telaBiometria, { comMenu: false });
registrarRota("descobrir", telaDescobrir);
registrarRota("conexoes", telaConexoes);
registrarRota("chat", telaChat);
registrarRota("perfil", telaPerfil);
registrarRota("conta", telaConta);
registrarRota("idade", telaIdade);
registrarRota("termos", telaTermos);
registrarRota("encontros", telaEncontros);
registrarRota("moderacao", telaModeracao);
registrarRota("idade-simulada", telaIdadeSimulada, { comMenu: false });

window.addEventListener("unhandledrejection", (ev) => {
  if (ev.reason instanceof ErroApi) {
    ev.preventDefault();
    if (ev.reason.status !== 401) avisar(ev.reason.message);
  }
});

iniciarRoteador();
sincronizarDiscreto();
