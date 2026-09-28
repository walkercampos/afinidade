# Relatório do projeto Afinidade (em linguagem simples)

## Em uma frase

Afinidade é um site (que funciona como aplicativo no celular) para pessoas adultas encontrarem outras
com os mesmos desejos e limites, sem precisar revelar quem são. É gratuito para quem usa e custa zero
para manter no ar.

## Como uma pessoa usa o app

1. **Cria a conta com o e-mail:** recebe um código de 6 dígitos (ou um link) e confirma. Não existe
   senha. Logo depois, o app oferece **ativar a biometria**: das próximas vezes, a pessoa entra só com a
   digital, o rosto ou o PIN do celular. Se não quiser inventar um apelido, o app gera um
   (tipo `anon_k3v9x2mq`). Não pedimos e-mail, telefone, nome nem foto. A pessoa confirma que tem
   18 anos ou mais e que aceita o uso dos dados sobre sexualidade para encontrar compatibilidades.
2. **Monta o perfil:** um nome de exibição (pode ser inventado), o próprio gênero, os gêneros que busca e,
   para cada prática da lista, marca **Quero**, **Curioso(a)** ou **Limite** (nunca).
3. Opcionalmente, **ativa a localização aproximada** e escolhe uma distância máxima ("até 25 km").
4. Opcionalmente, **envia até 3 fotos**. Quem ainda não foi autorizado vê as fotos borradas.
5. Em **Descobrir**, vê os perfis compatíveis com uma porcentagem de afinidade e pode ordenar por
   "mais compatíveis", "gostos parecidos" ou "ativos recentemente". Pode curtir, pular, bloquear ou denunciar.
6. Quando duas pessoas se curtem, vira uma **conexão** e elas podem **conversar**. Cada mensagem some
   5 minutos depois de lida, para os dois lados.
7. A qualquer momento, o **botão vermelho** (ou a tecla ESC) faz o app sumir na hora e abre o Google.
8. Em **Conta**, a pessoa pode sair de todos os aparelhos ou **excluir tudo** para sempre.

## Como o app decide quem aparece para você

Pense em três peneiras, uma depois da outra:

1. **Gênero, dos dois lados.** Só aparece quem é do gênero que você busca **e** busca o seu.
   Ninguém recebe atenção de quem não procura por essa pessoa.
2. **Limites.** Se algo é "Limite" para você, some quem **quer** fazer isso. E você some para quem tem
   como limite algo que você quer. Seus limites **nunca** aparecem para ninguém: só servem para filtrar.
3. **Pontuação.** Entre quem sobrou, cada coincidência vale pontos: os dois querem a mesma coisa = 3,
   um quer e o outro tem curiosidade = 2, os dois têm curiosidade = 1. O resultado vira uma porcentagem.
   A lista usa a média do que você acha da pessoa e do que ela acharia de você, para não empurrar
   combinações desequilibradas para o topo.

Além disso:

- **"Gostos parecidos"** mede o quanto duas pessoas marcaram as mesmas coisas, nos mesmos níveis.
  É ótimo para achar quem curte exatamente o que você curte.
- **Distância:** se você ou a outra pessoa escolheu uma distância máxima, vale a menor das duas.
- Perfis sem uso há mais de 90 dias param de aparecer.

Essa conta é feita dentro do banco de dados. Por isso o app continua rápido mesmo com muitos usuários.

## Privacidade: o que o app guarda e o que não guarda

| Informação | O que acontece |
|---|---|
| E-mail | Pedido só para criar a conta e recuperar o acesso. Fica guardado **embaralhado** (nem nós conseguimos ler) e nunca aparece para ninguém |
| Telefone, nome real, senha | **Não pedimos** |
| Data de nascimento | Usada só para confirmar os 18 anos e **descartada** |
| Endereço de internet (IP) | **Não é gravado** |
| Localização | Vira um quadrado de ~5 km. **A posição exata é jogada fora.** Os outros veem só "até N km" |
| Fotos | O app **apaga os dados escondidos** na foto (como o GPS de onde foi tirada) e guarda tudo **cifrado** |
| Mensagens | Guardadas **cifradas** e **apagadas 5 minutos depois de lidas** |
| Seus limites | Ninguém vê |
| Conta excluída | **Tudo é apagado na hora**, sem cópia "escondida" |

"Cifrado" quer dizer embaralhado com uma chave secreta que **não fica no banco de dados**. Se alguém
roubasse uma cópia do banco, veria só texto sem sentido no lugar das mensagens e das fotos.

## Fotos protegidas: por que o blur é de verdade

Em muitos sites, a foto "borrada" é a foto nítida com um efeito por cima, e qualquer pessoa remove
o efeito em dois cliques. Aqui é diferente: o **servidor** cria uma versão borrada a partir de uma
miniatura minúscula, e é **só ela** que chega a quem não foi autorizado. A foto nítida só é enviada ao
dono e a quem ele aprovou. O pedido de acesso só pode ser aprovado pelo dono, e o dono pode revogar
o acesso depois.

## Botão de pânico

O botão vermelho no canto (ou a tecla ESC) funciona em qualquer tela, inclusive na de login, e em
menos de um instante:

1. apaga o conteúdo da tela;
2. limpa o que o navegador guardou do site;
3. encerra a sessão no servidor (quem pegar o aparelho precisa da senha para entrar de novo);
4. troca a página pelo Google, sem deixar o app no botão "voltar".

## Segurança contra ataques

- **Biometria (passkeys):** o jeito mais seguro de entrar que existe hoje. Não há senha para roubar,
  e um site falso não consegue usar a passkey, porque ela só funciona no endereço verdadeiro do app.
  A digital e o rosto nunca saem do celular; o servidor guarda só uma "chave pública", que não serve
  para entrar na conta de ninguém.
- **Código por e-mail:** vale 15 minutos, uma vez só, e depois de 5 tentativas erradas é descartado.
- **Sessão protegida:** o "crachá" de login fica num lugar que scripts maliciosos não conseguem ler.
- **O site não carrega nada de fora** (nem fontes, nem estatísticas, nem anúncios): nenhuma empresa
  terceira fica sabendo quem acessa.
- **Tudo que as pessoas escrevem aparece como texto puro.** Ninguém consegue esconder código numa bio ou mensagem.
- **Cada tentativa de abuso tem um limite:** curtidas, mensagens, denúncias, envio de fotos, troca de localização.

## Comunidade segura (moderação)

- **Bloquear:** as duas pessoas somem uma para a outra, e a conversa e os acessos a fotos são apagados.
- **Denunciar:** também bloqueia. A pessoa pode anexar a conversa como prova, que fica cifrada.
- **Ocultação automática:** uma denúncia grave (possível menor de idade, conteúdo ilegal) ou 3 denúncias
  de contas diferentes (com mais de 24 horas de existência) escondem o perfil até alguém da moderação decidir.
  Enquanto isso, a conta não pode curtir nem mandar mensagens.
- **Moderadores** veem a fila de denúncias e decidem banir ou restaurar. Toda decisão fica registrada.

## Custo zero: onde o app roda

| O quê | Onde | Custo |
|---|---|---|
| Código, testes e publicação automática | GitHub | grátis |
| O app em si | Render | grátis (depois de um tempo sem uso, o primeiro acesso demora alguns segundos) |
| Banco de dados | Neon | grátis |

Quando alguém aprova uma mudança na versão principal do código, ela é testada e, se tudo passar,
vai para o ar sozinha.

## Qualidade: como sabemos que funciona

- **88 testes automáticos do servidor**, cobrindo 97% do código (o mínimo exigido é 90%).
- **7 testes das funções do site** e **3 testes que abrem um navegador de verdade** e fazem o caminho
  de duas pessoas: cadastro, fotos borradas, pedido de acesso, conexão, chat com contagem regressiva
  e botão de pânico, tudo numa tela de celular.
- Um teste compara, em 60 perfis sorteados, a conta feita no banco com a conta de referência, para
  garantir que dão o mesmo resultado.
- A cada mudança e **todo dia de manhã**, uma esteira automática roda: padrão de código, todos os
  testes, busca por falhas de segurança conhecidas nas bibliotecas usadas, montagem do app e um teste
  do app montado.

**Erros que os testes pegaram e já foram corrigidos:**

- Um apelido digitado com letra maiúscula (ex.: "Fulano") era recusado em vez de aceito.
- A tela de Conexões mostrava um texto técnico ("[object HTMLElement]") no lugar dos perfis.
- Trocar de tela rápido podia fazer uma tela antiga aparecer por cima da nova.
- Salvar o perfil pela primeira vez e sair logo em seguida puxava a pessoa de volta para o perfil.
- No celular, alguns botões ficavam cortados para fora da tela.
- O cálculo no banco arredondava diferente do cálculo de referência em casos de "meio" (12,5%).

## Visual

O app tem uma identidade própria, chamada **Véu Luminoso**: fundo noturno (discreto à noite e em
lugares públicos), títulos numa serifa itálica elegante e um único tom de rosa reservado para o que é
"revelado" (a afinidade, os interesses em comum, o botão principal). Ao fundo, uma grade quase invisível
lembra os quadrados de ~5 km da localização. A fonte fica guardada no próprio app, sem depender de
serviços de fora. O manifesto e a prancha que inspiraram o visual estão em [design/](design/).

## Para quem vai programar

O projeto segue regras para facilitar a manutenção por outras pessoas: cada assunto tem seu próprio
arquivo, há um guia passo a passo para criar funções novas ([CONTRIBUTING.md](../CONTRIBUTING.md)),
o estilo do código é corrigido automaticamente, e todo erro corrigido ganha um teste que impede que
ele volte. Os comandos do dia a dia estão no `Makefile` (`make` lista todos).

## O que ainda falta e cuidados

**Antes de abrir para o público:**

1. **Revisão com advogado(a).** Dados sobre vida sexual são "sensíveis" pela LGPD. O Marco Civil pode
   obrigar a guardar registros de acesso. A lei (ECA Digital) pode exigir verificação de idade mais forte
   do que a autodeclaração.
2. **Tela de moderação** (hoje a moderação funciona, mas só por comandos).
3. **Avisos de novidades** dentro do app (nova conexão, nova mensagem, pedido de foto).
4. **Termos de uso e política de privacidade.**

A lista completa, inspirada no pH7Builder, está em [roadmap.md](roadmap.md).

**Limites honestos:**

- Não prometa "100% de anonimato". O provedor de hospedagem vê os endereços de internet, e um apelido ou
  texto reaproveitado de outra rede pode identificar alguém.
- O chat é cifrado no servidor, mas **não "ponta a ponta"**: quem controla o servidor poderia, em tese,
  ler as mensagens durante os 5 minutos de vida delas.
- **Guarde bem a `CHAVE_MENSAGENS`.** Se ela se perder, mensagens e fotos existentes não podem mais ser abertas.

## Pequeno glossário

| Termo | Significado |
|---|---|
| API / servidor | A parte do app que roda "na nuvem" e guarda os dados |
| Banco de dados | Onde as informações ficam salvas (aqui, PostgreSQL) |
| Cifrar | Embaralhar com uma chave secreta, para ninguém sem a chave conseguir ler |
| Deploy | Colocar uma nova versão do app no ar |
| CI/CD, pipeline, esteira | Sequência automática que testa e publica o app a cada mudança |
| Teste automático | Um pequeno programa que usa o app e confere se o resultado está certo |
| Cobertura de testes | Quanto do código é exercitado pelos testes (aqui, 97%) |
