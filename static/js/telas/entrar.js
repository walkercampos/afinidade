// Acesso sem senha: a conta nasce pelo e-mail (código de 6 dígitos); depois, biometria (passkey).
import {
  confirmarCodigo, entrarComPasskey, pedirCodigoCadastro, pedirCodigoEntrar, suportaPasskeys,
} from "../api.js";
import { formulario, h } from "../dom.js";
import { irPara } from "../roteador.js";

const campoEmail = () => [
  h("label", { for: "email" }, "E-mail"),
  h("input", { id: "email", name: "email", type: "email", required: true, autocomplete: "email",
    autocapitalize: "none", spellcheck: "false", maxlength: 254 }),
];

/** Segunda etapa: digitar o código que chegou por e-mail. */
function etapaCodigo(area, email, verificacaoId, reenviar) {
  const form = formulario(async (f) => {
    const r = await confirmarCodigo(verificacaoId, f.get("codigo"));
    irPara(r.novo && suportaPasskeys() ? "biometria" : "descobrir");
  },
  h("p", { class: "nota" }, "Enviamos um código de 6 dígitos para ", h("strong", {}, email),
    ". Ele vale por 15 minutos. Também dá para abrir o link do e-mail neste aparelho."),
  h("label", { for: "codigo" }, "Código"),
  h("input", { id: "codigo", name: "codigo", required: true, inputmode: "numeric", autocomplete: "one-time-code",
    pattern: "\\d{6}", maxlength: 6, class: "codigo" }),
  h("div", { class: "acoes" }, h("button", { type: "submit" }, "Confirmar")),
  h("button", { type: "button", class: "link", onclick: reenviar }, "Não chegou? Enviar outro código"));
  area.replaceChildren(form);
  form.querySelector("#codigo").focus();
}

function formEntrar(area) {
  const pedir = async (email) => {
    const { verificacao_id } = await pedirCodigoEntrar(email);
    etapaCodigo(area, email, verificacao_id, () => pedir(email));
  };
  const porEmail = formulario(async (f) => pedir(f.get("email")),
    ...campoEmail(),
    h("div", { class: "acoes" },
      h("button", { type: "submit", class: suportaPasskeys() ? "secundario" : "" }, "Receber código por e-mail")));

  if (!suportaPasskeys()) return porEmail;
  const erro = h("p", { class: "erro", role: "alert" });
  const bio = h("button", { type: "button", class: "passkey", onclick: async () => {
    bio.disabled = true;
    erro.textContent = "";
    try { await entrarComPasskey(); irPara("descobrir"); } catch (e) { erro.textContent = e.message; } finally { bio.disabled = false; }
  } }, "Entrar com biometria");
  return h("div", {},
    h("div", { class: "bloco-passkey" }, bio, erro),
    h("p", { class: "nota" }, "Digital, rosto ou PIN do aparelho em que você ativou a biometria."),
    h("p", { class: "separador" }, "aparelho novo? receba um código"),
    porEmail);
}

function formCriar(area) {
  const pedir = async (dados) => {
    const { verificacao_id } = await pedirCodigoCadastro(dados);
    etapaCodigo(area, dados.email, verificacao_id, () => pedir(dados));
  };
  return formulario(async (f) => pedir({
    email: f.get("email"), handle: f.get("handle") || null, data_nascimento: f.get("nascimento"),
    confirmo_maior_de_idade: f.get("maior") === "on", consinto_dados_sensiveis: f.get("consinto") === "on",
  }),
  ...campoEmail(),
  h("p", { class: "nota" },
    "Seu e-mail nunca aparece para ninguém e fica guardado criptografado. Ele é usado só para confirmar a conta, "
    + "recuperar o acesso e avisos importantes sobre ela (nunca propaganda). Para mais discrição, use um e-mail só "
    + "para isso ou um alias (Ocultar meu e-mail do iCloud, Firefox Relay)."),
  h("label", { for: "handle" }, "Apelido (opcional)"),
  h("input", { id: "handle", name: "handle", type: "text", autocomplete: "nickname", autocapitalize: "none",
    spellcheck: "false", pattern: "[a-zA-Z0-9_]{3,30}", maxlength: 30 }),
  h("p", { class: "nota" }, "Em branco, você recebe um apelido aleatório. Não use o mesmo de outras redes."),
  h("label", { for: "nascimento" }, "Data de nascimento"),
  h("input", { id: "nascimento", name: "nascimento", type: "date", required: true }),
  h("p", { class: "nota" }, "Usada só para confirmar a maioridade. Não é armazenada."),
  h("label", { class: "check" }, h("input", { type: "checkbox", name: "maior", required: true }), "Tenho 18 anos ou mais."),
  h("label", { class: "check" }, h("input", { type: "checkbox", name: "consinto", required: true }),
    "Consinto com o tratamento dos meus dados sobre sexualidade para gerar compatibilidades. Posso excluir tudo a qualquer momento."),
  h("div", { class: "acoes" }, h("button", { type: "submit" }, "Enviar código de confirmação")));
}

export function telaEntrar(_parametro, ctx) {
  const abaEntrar = h("button", { type: "button", role: "tab", onclick: () => trocar("entrar") }, "Entrar");
  const abaCriar = h("button", { type: "button", role: "tab", onclick: () => trocar("criar") }, "Criar conta");
  const area = h("div");
  function trocar(modo) {
    abaEntrar.setAttribute("aria-selected", modo === "entrar");
    abaCriar.setAttribute("aria-selected", modo === "criar");
    area.replaceChildren(modo === "entrar" ? formEntrar(area) : formCriar(area));
  }
  ctx.mostrar(h("h1", {}, "Conexões por afinidade, sem expor quem você é"),
    h("p", { class: "nota" }, "Em qualquer tela, aperte ESC ou o botão vermelho para sair na hora."),
    h("div", { class: "abas", role: "tablist" }, abaEntrar, abaCriar), area);
  trocar("entrar");
}
