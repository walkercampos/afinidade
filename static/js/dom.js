// Regra de segurança: dados vindos da API entram no DOM SOMENTE como texto (h() usa
// append de strings, que vira textContent). Nunca use innerHTML com dados do usuário.

import { normalizarFilhos } from "./util.js";

const tela = document.getElementById("tela");
const aviso = document.getElementById("aviso");

export function h(tag, attrs = {}, ...filhos) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === false || v == null) continue;
    if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (k === "class") el.className = v;
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const f of normalizarFilhos(filhos)) el.append(f instanceof Node ? f : String(f));
  return el;
}

export function mostrar(...nos) {
  tela.replaceChildren(...normalizarFilhos(nos));
  window.scrollTo(0, 0);
}

export function carregando() {
  mostrar(h("p", { class: "vazio" }, "Carregando…"));
}

let avisoTimer;
export function avisar(texto) {
  aviso.textContent = texto;
  aviso.hidden = false;
  clearTimeout(avisoTimer);
  avisoTimer = setTimeout(() => { aviso.hidden = true; }, 2600);
}

/** Formulário que desabilita o botão durante o envio e mostra o erro abaixo. */
export function formulario(onEnviar, ...campos) {
  const erro = h("p", { class: "erro", role: "alert" });
  const form = h("form", {
    onsubmit: async (ev) => {
      ev.preventDefault();
      const botao = form.querySelector("button[type=submit]");
      botao.disabled = true;
      erro.textContent = "";
      try { await onEnviar(new FormData(form)); } catch (e) { erro.textContent = e.message; } finally { botao.disabled = false; }
    },
  }, ...campos, erro);
  return form;
}
