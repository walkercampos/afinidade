# Testes exploratórios

Tudo que é novo no Afinidade entra com **testes unitários** e com **uma sessão de teste
exploratório registrada aqui**. Os unitários provam o que a gente já sabe que precisa funcionar;
a exploração procura o que ninguém pensou em escrever, e cada problema encontrado vira um teste
automático de regressão.

## Como fazer uma sessão

1. **Missão (charter)** em uma frase: *Explorar* o quê, *com* quais recursos, *para descobrir*
   o quê. Ex.: "Explorar o campo Outro com textos Unicode estranhos para descobrir se o mínimo
   de 3 caracteres pode ser burlado."
2. **Tempo fechado:** de 30 a 60 minutos. Acabou o tempo, registre e pare.
3. **Explore de verdade:** use o app como pessoas diferentes usariam. Anote o que tentou, não só
   o que quebrou. Scripts de navegador (Playwright) ajudam a repetir variações, mas o roteiro sai
   da curiosidade, não de uma lista pronta.
4. **Registre** em `AAAA-MM-DD-<tema>.md` a partir do [modelo](modelo.md): missão, o que foi
   tentado, achados, e o que virou teste.
5. **Feche cada achado:** bug corrigido ganha teste de regressão (unitário e/ou no navegador)
   **no mesmo PR**; o que não for corrigido agora vira issue ou fica como "observação" com o motivo.

## Heurísticas deste projeto

Use as que fazem sentido para o que mudou; não precisa passar por todas.

| Área | O que tentar |
|---|---|
| Texto e Unicode | vazio, só espaços, quebras de linha, emoji (inclusive compostos 👩🏽‍💻), acentos combinantes, caracteres invisíveis (U+200B, U+00AD, U+200E), texto enorme, HTML/JS colado |
| Limites | exatamente no mínimo e no máximo, um a menos, um a mais; zero; datas na virada (quem faz 18 anos hoje) |
| Privacidade | o dado aparece para outra pessoa, na URL, no log, na mensagem de erro? Limites continuam invisíveis? |
| Acesso | outra conta tentando o mesmo recurso; conta bloqueada, em revisão, sem idade verificada, sem termos aceitos |
| Estado e tempo | duplo clique, voltar do navegador, recarregar no meio, duas abas, rede lenta ou caindo, sessão expirada |
| Teclado e leitor de tela | usar só Tab/Espaço/Enter; foco visível; nomes acessíveis fazem sentido lidos em voz alta |
| Toque e tela | 320 px, zoom de 200% (≈180 px), paisagem, toque sem hover |
| Tema e discrição | tema escuro, modo discreto, botão de pânico (ESC) no meio da ação |
| Textos | nada promete anonimato total nem criptografia de ponta a ponta |

## Sessões registradas

| Data | Tema | Achados | Virou teste |
|---|---|---|---|
| 2026-09-30 | [Formulário de identidade](2026-09-30-formulario-identidade.md) | 3 bugs, 2 observações | 22 unitários, 2 regressões no navegador |
