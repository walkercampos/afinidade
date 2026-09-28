import { api } from "../api.js";
import { formulario, h } from "../dom.js";
import { irPara } from "../roteador.js";

const campoApelido = (obrigatorio) => [
  h("label", { for: "handle" }, obrigatorio ? "Apelido" : "Apelido (opcional)"),
  h("input", { id: "handle", name: "handle", type: "text", required: obrigatorio, autocomplete: "username",
    autocapitalize: "none", spellcheck: "false", pattern: "[a-zA-Z0-9_]{3,30}", maxlength: 30 }),
];

function formEntrar() {
  return formulario(async (f) => {
    await api("/auth/login", { metodo: "POST", corpo: { handle: f.get("handle"), senha: f.get("senha") } });
    irPara("descobrir");
  },
  ...campoApelido(true),
  h("label", { for: "senha" }, "Senha"),
  h("input", { id: "senha", name: "senha", type: "password", required: true, autocomplete: "current-password" }),
  h("div", { class: "acoes" }, h("button", { type: "submit" }, "Entrar")));
}

function formCriar() {
  return formulario(async (f) => {
    const { handle } = await api("/auth/registro", { metodo: "POST", corpo: {
      handle: f.get("handle") || null, senha: f.get("senha"), data_nascimento: f.get("nascimento"),
      confirmo_maior_de_idade: f.get("maior") === "on", consinto_dados_sensiveis: f.get("consinto") === "on",
    } });
    if (!f.get("handle")) alert(`Seu apelido é ${handle}\n\nAnote: é com ele e a senha que você entra.`);
    irPara("perfil");
  },
  h("p", { class: "nota" }, "Não pedimos e-mail, telefone nem nome real."),
  ...campoApelido(false),
  h("p", { class: "nota" }, "Deixe em branco para receber um apelido aleatório. Não use o mesmo de outras redes."),
  h("label", { for: "senha" }, "Senha"),
  h("input", { id: "senha", name: "senha", type: "password", required: true, minlength: 10, maxlength: 128,
    autocomplete: "new-password" }),
  h("p", { class: "nota" }, "Mínimo de 10 caracteres. Sem e-mail não há recuperação de senha: guarde-a num gerenciador."),
  h("label", { for: "nascimento" }, "Data de nascimento"),
  h("input", { id: "nascimento", name: "nascimento", type: "date", required: true }),
  h("p", { class: "nota" }, "Usada só para confirmar a maioridade. Não é armazenada."),
  h("label", { class: "check" }, h("input", { type: "checkbox", name: "maior", required: true }), "Tenho 18 anos ou mais."),
  h("label", { class: "check" }, h("input", { type: "checkbox", name: "consinto", required: true }),
    "Consinto com o tratamento dos meus dados sobre sexualidade para gerar compatibilidades. Posso excluir tudo a qualquer momento."),
  h("div", { class: "acoes" }, h("button", { type: "submit" }, "Criar conta")));
}

export function telaEntrar(_parametro, ctx) {
  const abaEntrar = h("button", { type: "button", role: "tab", onclick: () => trocar("entrar") }, "Entrar");
  const abaCriar = h("button", { type: "button", role: "tab", onclick: () => trocar("criar") }, "Criar conta");
  const area = h("div");
  function trocar(modo) {
    abaEntrar.setAttribute("aria-selected", modo === "entrar");
    abaCriar.setAttribute("aria-selected", modo === "criar");
    area.replaceChildren(modo === "entrar" ? formEntrar() : formCriar());
  }
  ctx.mostrar(h("h1", {}, "Conexões por afinidade, sem expor quem você é"),
    h("p", { class: "nota" }, "Em qualquer tela, aperte ESC ou o botão vermelho para sair na hora."),
    h("div", { class: "abas", role: "tablist" }, abaEntrar, abaCriar), area);
  trocar("entrar");
}
