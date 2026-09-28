// Ponto de entrada do front-end: registra as telas e liga o botão de pânico.
import { ErroApi } from "./api.js";
import { avisar } from "./dom.js";
import { instalarPanico } from "./panico.js";
import { iniciarRoteador, registrarRota } from "./roteador.js";
import { telaChat } from "./telas/chat.js";
import { telaConexoes } from "./telas/conexoes.js";
import { telaConta } from "./telas/conta.js";
import { telaDescobrir } from "./telas/descobrir.js";
import { telaEntrar } from "./telas/entrar.js";
import { telaPerfil } from "./telas/perfil.js";

instalarPanico();

registrarRota("entrar", telaEntrar, { comMenu: false });
registrarRota("descobrir", telaDescobrir);
registrarRota("conexoes", telaConexoes);
registrarRota("chat", telaChat);
registrarRota("perfil", telaPerfil);
registrarRota("conta", telaConta);

window.addEventListener("unhandledrejection", (ev) => {
  if (ev.reason instanceof ErroApi) {
    ev.preventDefault();
    if (ev.reason.status !== 401) avisar(ev.reason.message);
  }
});

iniciarRoteador();
