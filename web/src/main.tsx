import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { ProvedorDeAvisos } from "./componentes/avisos";
import { api, ErroApi } from "./lib/api";
import { aplicarDiscreto, aplicarTema } from "./lib/discricao";
import { instalarAtalhoDoPanico } from "./lib/panico";
import type { Preferencias } from "./lib/tipos";
import "./index.css";

aplicarTema();
aplicarDiscreto();
instalarAtalhoDoPanico();

// Busca a preferência da conta sem incomodar quem não entrou (sem redirecionar no 401).
api<Preferencias>("/conta/preferencias", { silencioso: true })
  .then((p) => aplicarDiscreto(p.modo_discreto))
  .catch(() => { /* sem sessão ou sem rede: mantém o que estava guardado */ });

window.addEventListener("unhandledrejection", (ev) => {
  if (ev.reason instanceof ErroApi) ev.preventDefault();
});

createRoot(document.getElementById("raiz")!).render(
  <StrictMode>
    <ProvedorDeAvisos>
      <App />
    </ProvedorDeAvisos>
  </StrictMode>,
);
