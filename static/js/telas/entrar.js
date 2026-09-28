import { api, cadastrarComPasskey, entrarComPasskey, suportaPasskeys } from "../api.js";
import { formulario, h } from "../dom.js";
import { irPara } from "../roteador.js";

const campoApelido = (obrigatorio) => [
  h("label", { for: "handle" }, obrigatorio ? "Apelido" : "Apelido (opcional)"),
  h("input", { id: "handle", name: "handle", type: "text", required: obrigatorio, autocomplete: "username",
    autocapitalize: "none", spellcheck: "false", pattern: "[a-zA-Z0-9_]{3,30}", maxlength: 30 }),
];

function botaoPasskey(texto, acao) {
  const erro = h("p", { class: "erro", role: "alert" });
  const botao = h("button", { type: "button", class: "passkey", onclick: async () => {
    botao.disabled = true;
    erro.textContent = "";
    try { await acao(); } catch (e) { erro.textContent = e.message; } finally { botao.disabled = false; }
  } }, texto);
  return h("div", { class: "bloco-passkey" }, botao, erro);
}

function formEntrar() {
  const comSenha = formulario(async (f) => {
    await api("/auth/login", { metodo: "POST", corpo: { handle: f.get("handle"), senha: f.get("senha") } });
    irPara("descobrir");
  },
  ...campoApelido(true),
  h("label", { for: "senha" }, "Senha"),
  h("input", { id: "senha", name: "senha", type: "password", required: true, autocomplete: "current-password" }),
  h("div", { class: "acoes" }, h("button", { type: "submit", class: suportaPasskeys() ? "secundario" : "" }, "Entrar com senha")));

  if (!suportaPasskeys()) return comSenha;
  return h("div", {},
    botaoPasskey("Entrar com passkey", async () => { await entrarComPasskey(); irPara("descobrir"); }),
    h("p", { class: "nota" }, "Sem digitar nada: use a digital, o rosto ou o PIN do seu aparelho."),
    h("p", { class: "separador" }, "ou com apelido e senha"),
    comSenha);
}

function formCriar() {
  const passkey = suportaPasskeys();
  let modo = passkey ? "passkey" : "senha";
  const senha = h("input", { id: "senha", name: "senha", type: "password", minlength: 10, maxlength: 128,
    autocomplete: "new-password" });
  const blocoSenha = h("div", {},
    h("label", { for: "senha" }, "Senha"), senha,
    h("p", { class: "nota" }, "Mínimo de 10 caracteres. Sem e-mail não há recuperação de senha: guarde-a num gerenciador."));
  const enviar = h("button", { type: "submit" });
  const alternar = h("button", { type: "button", class: "link", onclick: () => { modo = modo === "passkey" ? "senha" : "passkey"; aplicar(); } });
  const explicacaoPasskey = h("p", { class: "nota" },
    "Com passkey não existe senha para vazar ou esquecer: você entra com a digital, o rosto ou o PIN deste aparelho. "
    + "Passkeys salvas no iCloud ou no Google aparecem nos seus outros aparelhos.");

  function aplicar() {
    const comSenha = modo === "senha";
    blocoSenha.hidden = !comSenha;
    senha.required = comSenha;
    explicacaoPasskey.hidden = comSenha;
    enviar.textContent = comSenha ? "Criar conta com senha" : "Criar conta com passkey";
    alternar.textContent = comSenha ? "Prefiro usar passkey (sem senha)" : "Prefiro criar com senha";
    alternar.hidden = !passkey;
  }

  const form = formulario(async (f) => {
    const dados = {
      handle: f.get("handle") || null, data_nascimento: f.get("nascimento"),
      confirmo_maior_de_idade: f.get("maior") === "on", consinto_dados_sensiveis: f.get("consinto") === "on",
    };
    const { handle } = modo === "passkey"
      ? await cadastrarComPasskey(dados)
      : await api("/auth/registro", { metodo: "POST", corpo: { ...dados, senha: f.get("senha") } });
    if (!f.get("handle")) alert(`Seu apelido é ${handle}\n\nÉ assim que as pessoas vão te ver até você escolher um nome.`);
    irPara("perfil");
  },
  h("p", { class: "nota" }, "Não pedimos e-mail, telefone nem nome real."),
  ...campoApelido(false),
  h("p", { class: "nota" }, "Deixe em branco para receber um apelido aleatório. Não use o mesmo de outras redes."),
  h("label", { for: "nascimento" }, "Data de nascimento"),
  h("input", { id: "nascimento", name: "nascimento", type: "date", required: true }),
  h("p", { class: "nota" }, "Usada só para confirmar a maioridade. Não é armazenada."),
  h("label", { class: "check" }, h("input", { type: "checkbox", name: "maior", required: true }), "Tenho 18 anos ou mais."),
  h("label", { class: "check" }, h("input", { type: "checkbox", name: "consinto", required: true }),
    "Consinto com o tratamento dos meus dados sobre sexualidade para gerar compatibilidades. Posso excluir tudo a qualquer momento."),
  blocoSenha, explicacaoPasskey,
  h("div", { class: "acoes" }, enviar),
  alternar);
  aplicar();
  return form;
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
