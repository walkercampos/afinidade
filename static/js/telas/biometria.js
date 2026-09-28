// Logo depois de criar a conta pelo e-mail: ativar a biometria (passkey) para os próximos acessos.
import { adicionarPasskey, suportaPasskeys } from "../api.js";
import { avisar, h } from "../dom.js";
import { irPara } from "../roteador.js";

export function telaBiometria(_parametro, ctx) {
  if (!suportaPasskeys()) return irPara("perfil");
  const erro = h("p", { class: "erro", role: "alert" });
  const ativar = h("button", { type: "button", class: "passkey", onclick: async () => {
    ativar.disabled = true;
    erro.textContent = "";
    try {
      await adicionarPasskey("Este aparelho");
      avisar("Biometria ativada");
      irPara("perfil");
    } catch (e) { erro.textContent = e.message; } finally { ativar.disabled = false; }
  } }, "Ativar biometria");
  ctx.mostrar(
    h("h1", {}, "Conta criada. Agora, a biometria"),
    h("div", { class: "cartao" },
      h("p", {}, "Da próxima vez, entre só com a digital, o rosto ou o PIN deste aparelho, sem esperar código por e-mail."),
      h("p", { class: "nota" }, "Sua digital e seu rosto nunca saem do aparelho: o app recebe só uma assinatura digital. "
        + "Se trocar de celular, é só entrar com um código por e-mail e ativar de novo."),
      h("div", { class: "bloco-passkey" }, ativar, erro),
      h("button", { type: "button", class: "link", onclick: () => irPara("perfil") }, "Agora não")));
}
