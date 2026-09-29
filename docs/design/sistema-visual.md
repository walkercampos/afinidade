# Sistema visual

O visual segue os padrões atuais dos apps mais usados no mundo (iOS, Android/Material 3 e os
grandes apps de encontros), para quem usa se sentir em casa desde a primeira tela.

## Princípios

1. **Fonte do próprio aparelho:** San Francisco no iPhone, Roboto no Android, Segoe no Windows.
   Carrega na hora, não baixa nada e é a mais legível em cada sistema.
2. **Claro e escuro:** seguem a configuração do celular. O escuro é mais discreto à noite e em
   lugares públicos; o claro chama menos atenção de dia.
3. **Superfícies limpas:** cartões brancos (ou cinza-grafite no escuro), cantos de 22 px, borda fina
   e sombra leve. Nada de texturas.
4. **Um só tom de destaque:** o rosa da marca (`#e11d48`) marca o que importa: o botão principal,
   a afinidade e os interesses em comum.
5. **Toque confortável:** todo botão tem pelo menos 44–48 px de altura (recomendação da Apple e do
   Google); botões em formato de pílula.
6. **Barra de abas inferior** com ícones e rótulos, com efeito de vidro. No computador ela vira uma
   barra de navegação no topo.

## Tokens (em `static/app.css`, bloco `:root`)

| Token | Claro | Escuro | Uso |
|---|---|---|---|
| `--fundo` | `#f6f6f8` | `#0b0b0f` | fundo da página |
| `--superficie` | `#ffffff` | `#16161c` | cartões |
| `--superficie-2` | `#f1f1f4` | `#202029` | campos, chips, botões secundários |
| `--texto` / `--suave` | `#17171c` / `#6b6b76` | `#f4f4f6` / `#a1a1ad` | texto principal / de apoio |
| `--acento` | `#e11d48` | `#e11d48` | botão principal, marca |
| `--acento-texto` | `#be123c` | `#fda4b4` | afinidade, links, chips em comum |
| `--ok` / `--violeta` / `--perigo` | verde / violeta / vermelho | — | Quero / Curioso / Limite, pânico |

O texto branco sobre o rosa `#e11d48` atende ao nível AA de contraste (acessibilidade).

## Regras para telas novas

- Use só os tokens: nada de cores soltas no CSS das telas.
- Botão principal: `<button>`; secundário: `class="secundario"`; destrutivo: `class="perigo"`.
- Blocos de conteúdo: `class="cartao"`; textos de apoio: `class="nota"`.
- Nada de fontes, ícones ou scripts externos: a política de segurança (CSP) do app bloqueia, e isso
  protege a privacidade de quem usa. Ícones são SVG escritos no próprio HTML.
- Teste nos dois temas e em 360 px de largura (os testes no navegador conferem a rolagem
  horizontal).

## Telas

Capturas nos dois temas em [../telas/](../telas/README.md).
