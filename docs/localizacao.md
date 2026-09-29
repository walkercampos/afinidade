# Localização

Como o app usa a localização para mostrar "até N km" sem nunca saber onde a pessoa está de verdade.

## 1. Quem decide: a própria pessoa

- A localização é **opcional** e só é lida quando a pessoa toca em **"Usar minha localização"**. Nada
  é enviado em segundo plano, e o app não acompanha deslocamentos.
- A **distância máxima** é escolhida numa **barra deslizante** (5 km a 500 km, ou "Qualquer distância").
  Mexer na barra envia **só o número**, nunca coordenadas (`PUT /api/perfil/distancia`).
- O raio vale para os dois lados: se eu escolho 50 km e a outra pessoa escolheu 10 km, só nos vemos
  se estivermos a até 10 km.
- "Remover" apaga a região e o raio na hora.

## 2. Do aparelho ao banco

```
Aparelho                API                                         Banco
lat/lon  ──HTTPS──▶  geohash de 5 caracteres (~4,9 km x 4,9 km)  ──▶  célula + centro da célula
                     a coordenada recebida é descartada aqui          (nunca a coordenada)
```

`PUT /api/perfil/localizacao` recebe `{lat, lon, distancia_max_km}`, calcula a célula
([geohash](https://pt.wikipedia.org/wiki/Geohash)) e grava **apenas a célula e o centro dela**
(`app/routes/perfil.py`, migração `0003_localizacao.sql`). A coordenada não vai para o banco, nem para
logs, nem para backups.

## 3. Distância: fórmula de Haversine

A distância em linha reta sobre a superfície da Terra (raio médio de 6.371 km) é calculada pela
fórmula de Haversine:

```
a = sen²(Δlat/2) + cos(lat1) · cos(lat2) · sen²(Δlon/2)
d = 2 · R · arcsen(√a)
```

Ela existe em dois lugares com o mesmo resultado: a função SQL `distancia_km` (usada no filtro da
descoberta) e `app/geo.py` (usada nos testes). **Os dois pontos são sempre centros de célula**, nunca
posições reais. Quem vê o perfil recebe só a faixa arredondada para cima de 5 em 5 km ("até 5 km",
"até 10 km"…).

## 4. Ataque de trilateração e como o app se protege

**O ataque.** Com a distância exata até alguém, medida de três pontos diferentes, dá para desenhar
três círculos: eles se cruzam na casa da pessoa. Apps de encontro já expuseram usuários a poucos
metros assim. Arredondar a distância não basta: o atacante falsifica a própria posição várias vezes
e observa em que ponto a faixa muda de "até 5 km" para "até 10 km".

**A defesa (snap-to-grid na origem).** O app não arredonda a *resposta*; ele nunca tem a posição
exata. Cada pessoa vira o centro de um quadrado de ~5 km **antes** de qualquer cálculo. Por isso:

- Duas pessoas em pontos diferentes do mesmo quadrado são **indistinguíveis** para qualquer
  observador, por mais medições que ele faça.
- O máximo que um atacante consegue descobrir é **em qual quadrado de ~5 km** a pessoa está, que é
  exatamente o que o app já assume como público.

**Camadas extras:**

| Proteção | Onde |
|---|---|
| Faixas de 5 km, arredondadas para cima | `geo.faixa_km` |
| Até 20 trocas de localização por hora por conta (dificulta "varrer" a cidade) | `salvar_localizacao` |
| Rate limit geral da API | `app/ratelimit.py` |
| Limites absolutos e bloqueios valem antes da distância | `descoberta.py` |

**Como isso é testado** (`tests/test_localizacao.py`, a cada push e todo dia):

- `test_trilateracao_nao_revela_mais_que_o_quadrado`: duas vítimas em cantos opostos do mesmo
  quadrado (a mais de 5 km uma da outra). Um atacante faz 16 sondagens em volta, com o filtro de
  distância no mínimo, e as respostas para as duas vítimas têm de ser **idênticas** em todas elas.
  Se alguém mudar o código para usar a coordenada exata, esse teste falha (verificado).
- `test_limite_de_trocas_de_localizacao`: a 21ª troca na mesma hora é recusada.
- `test_coordenada_exata_nunca_e_gravada`: o banco só tem a célula e o centro dela.

**Limite honesto:** o atacante pode descobrir o quadrado de ~5 km, e com muitas contas falsas pode
contornar o limite de trocas por conta. Por isso a célula é grande de propósito. Quem quiser zero
informação de localização pode simplesmente não ativá-la.

## 5. Decisões e alternativas descartadas

| Alternativa | Por que não |
|---|---|
| **Redis** (`GEOADD`/`GEOSEARCH`) | Serve para milhões de posições mudando a cada segundo. Aqui há uma célula por pessoa, e o PostgreSQL com índice responde em milissegundos até centenas de milhares de perfis. Seria mais um serviço pago e mais um lugar com dado de localização. Rever acima de ~500 mil perfis ativos. |
| **PostGIS** | Precisão que não usamos (o dado já é uma célula). Continua possível no Neon se um dia for útil. |
| **"Caminhos cruzados"** (estilo Happn) | Exige guardar o histórico de onde e quando cada pessoa esteve. Num app adulto e discreto, esse é o dado mais perigoso que poderia vazar. |
| **Atualização contínua em segundo plano** | Rastreamento. A posição só é lida quando a pessoa toca no botão. |
