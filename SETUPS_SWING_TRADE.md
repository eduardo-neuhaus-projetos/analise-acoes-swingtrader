# Especificação de Setups de Swing Trade — Timeframe Diário

> Documento de referência para implementação. Regras escritas para serem determinísticas e testáveis.
> Onde as fontes divergem (cursos, livros, autores), a variação está exposta como **parâmetro configurável**, com o valor mais usado como default.
> Conteúdo técnico/educacional — não constitui recomendação de investimento.

---

## 0. Convenções gerais (valem para todos os setups)

### 0.1 Notação
| Símbolo | Significado |
|---|---|
| `O[i], H[i], L[i], C[i], V[i]` | Abertura, máxima, mínima, fechamento e volume do candle `i` |
| `i` | Candle de sinal (último candle **fechado** quando o setup é avaliado) |
| `i-1, i-2...` | Candles anteriores |
| `i+1` | Próximo candle (onde a entrada pode ser acionada) |
| `tick` | Menor variação de preço do ativo (ações B3: R$ 0,01) |
| `MME(n)` | Média móvel exponencial de `n` períodos sobre o fechamento |
| `MMA(n)` | Média móvel aritmética (simples) de `n` períodos sobre o fechamento |
| `body[i]` | `abs(C[i] - O[i])` |
| `range[i]` | `H[i] - L[i]` |

### 0.2 Fórmulas base
- **MME:** `k = 2 / (n + 1)`; `MME[i] = C[i] * k + MME[i-1] * (1 - k)`; semente = MMA(n) dos primeiros `n` candles.
- **IFR (RSI) de Wilder:** ganhos/perdas médios com suavização de Wilder (`média[i] = (média[i-1] * (n-1) + valor[i]) / n`), semente = média simples dos `n` primeiros. `IFR = 100 - 100 / (1 + ganhoMédio / perdaMédia)`.
- **ADX / DI+ / DI- (Wilder):** padrão de Wilder com suavização de Wilder; período configurável.
- **Bandas de Bollinger:** `meio = MMA(20)`, `sup/inf = meio ± 2 * desvioPadrão(20)` (desvio populacional).
- **ATR (N):** média de Wilder do True Range, `TR = max(H-L, abs(H-C[i-1]), abs(L-C[i-1]))`.
- **Warm-up:** descartar sinais até que todos os indicadores usados tenham pelo menos `3 × período` candles (para estabilizar EMAs/Wilder).

### 0.3 Inclinação ("média subindo/caindo")
- `subindo(M, i)`  ⇔ `M[i] > M[i-1]`
- `caindo(M, i)`   ⇔ `M[i] < M[i-1]`
- `virou_para_cima(M, i)` ⇔ `M[i] > M[i-1]` **e** `M[i-1] <= M[i-2]`
- `virou_para_baixo(M, i)` ⇔ `M[i] < M[i-1]` **e** `M[i-1] >= M[i-2]`

### 0.4 Execução de entrada (ordens stop)
- **Compra stop** em `preçoEntrada = H[sinal] + tick`.
- No candle `i+1`:
  - Se `O[i+1] >= preçoEntrada` (gap acima) → executa em `O[i+1]` (parâmetro `aceitar_gap`, default `true`; se `false`, cancela o sinal).
  - Senão, se `H[i+1] >= preçoEntrada` → executa em `preçoEntrada`.
- **Venda stop** é o espelho (`L[sinal] - tick`).
- **Validade do sinal:** default 1 candle. Setups com regra de "arrasto" (ajuste de entrada) estão descritos individualmente.
- **Stop e entrada no mesmo candle:** no diário não há como saber a ordem intradiária. Regra conservadora default: se entrada e stop são atingidos no mesmo candle, considerar **stopado** (parâmetro `ordem_intrabar = "pior_caso"`).

### 0.5 Stop inicial, risco e alvos
- **Stop técnico:** definido por setup (geralmente `L[sinal] - tick` na compra).
- **Risco por ação:** `R = entrada - stop`.
- **Alvo por múltiplo de risco:** `alvo = entrada + m * R` (default `m = 2`; parâmetro).
- **Saídas suportadas (escolha por setup):** `alvo_fixo`, `trailing_minima` (stop móvel na mínima do candle anterior), `trailing_media` (regra da família 9.x), `saida_tempo` (n candles), `saida_indicador`.
- **Dimensionamento da posição:** `qtd = floor((capital * risco_pct) / R)`, arredondada para o lote do ativo. Default `risco_pct = 1%`.

### 0.6 Filtros globais opcionais (aplicáveis a qualquer setup)
| Filtro | Regra | Default |
|---|---|---|
| `filtro_tendencia_mm200` | compra só se `C[i] > MMA(200)[i]`; venda só se `<` | desligado |
| `filtro_volume_min` | `MMA(V, 20)[i] >= volume_minimo` (liquidez) | desligado |
| `filtro_semanal` | MME(9) semanal subindo para compras | desligado |
| `apenas_compra` | ignora sinais de venda (comum em ações à vista) | desligado |

### 0.7 Versões de venda
Salvo indicação em contrário, a versão de **venda** é o espelho exato da compra: trocar `H`↔`L`, `>`↔`<`, `subindo`↔`caindo`, `+tick`↔`-tick`.

---

## 1. Família Larry Williams (9.1, 9.2, 9.3, 9.4)

Origem: Larry Williams. Popularização no Brasil: Alexandre Wolwacz (Stormer).
Indicador comum: `M = MME(9)` (parâmetro `periodo_media`, default 9).

### 1.0 Saída padrão da família 9.x (`trailing_media`)
Depois de comprado:
1. Enquanto `M` estiver subindo, manter o stop inicial (ou, opcionalmente, subir para a mínima do candle anterior — parâmetro `trailing_na_minima`, default `false`).
2. No candle `j` em que `virou_para_baixo(M, j)`: colocar **venda stop** em `L[j] - tick`.
3. Se o candle seguinte não romper `L[j]` e a média voltar a subir, cancelar a saída e continuar na posição.
4. Se a média continuar caindo e o novo candle tiver mínima mais baixa sem ter acionado, arrastar a venda stop para a mínima do novo candle (opcional — parâmetro `arrastar_saida`, default `true`).
5. Alternativa configurável: alvo fixo por múltiplo de R.

### 1.1 Setup 9.1 — Virada da média
**Compra**
- **Condição de sinal:** `virou_para_cima(M, i)`.
- **Entrada:** compra stop em `H[i] + tick`.
- **Arrasto da entrada:** se `i+1` não acionar a entrada **e** `M` continuar subindo **e** `H[i+1] < H[i]`, a entrada passa para `H[i+1] + tick` (repetir enquanto valer). Parâmetro `arrastar_entrada`, default `true`.
- **Invalidação:** `M` vira para baixo antes de acionar.
- **Stop:** `L[i] - tick` (mínima do candle que virou a média; se houve arrasto, mínima do candle de sinal vigente — parâmetro `stop_no_candle_vigente`, default `true`).
- **Saída:** `trailing_media` (1.0).

### 1.2 Setup 9.2 — Pullback com fechamento abaixo da mínima anterior
**Compra**
- **Pré-condição:** `subindo(M, i)`.
- **Condição de sinal:** `C[i] < L[i-1]`.
- **Entrada:** compra stop em `H[i] + tick`.
- **Arrasto:** se `i+1` não acionar e também fechar abaixo de `L[i]` com `M` ainda subindo, `i+1` passa a ser o sinal (entrada em `H[i+1] + tick`).
- **Invalidação:** `M` deixa de subir antes de acionar.
- **Stop:** `L[i] - tick` (default). Variante: mínima do pullback (`min(L)` desde o último topo) — parâmetro `stop_tipo = "candle_sinal" | "minima_pullback"`.
- **Saída:** `trailing_media`.

### 1.3 Setup 9.3 — Pullback de dois fechamentos
**Compra**
- **Pré-condição:** `subindo(M, i)`.
- **Condição de sinal:** `C[i-1] < C[i-2]` **e** `C[i] < C[i-2]` (dois fechamentos consecutivos abaixo do fechamento do candle de referência `i-2`).
- **Entrada:** compra stop em `H[i] + tick`.
- **Arrasto:** se não acionar e o próximo candle também fechar abaixo de `C[i-2]` com `M` subindo, ele passa a ser o sinal.
- **Invalidação:** `M` deixa de subir antes de acionar.
- **Stop:** `L[i] - tick` (default) ou mínima do pullback (parâmetro).
- **Saída:** `trailing_media`.

### 1.4 Setup 9.4 — Falha do 9.1 seguida de retomada
> As fontes descrevem o 9.4 com pequenas diferenças. Implementar a versão abaixo (mais difundida no Brasil) e deixar `variante_94` configurável.

**Compra**
- **Contexto:** existe um 9.1 de compra **acionado** recentemente (posição aberta ou recém-encerrada pela saída de média, dentro de `janela_94` candles, default 3).
- **Condição de sinal:** `virou_para_baixo(M, i)` **e** o stop original do 9.1 **não** foi atingido (`L[i] > stop_9_1`).
- **Entrada:** compra stop em `H[i] + tick` (máxima do candle que virou a média para baixo) no candle seguinte.
- **Invalidação:** perda do stop original do 9.1 antes do acionamento, ou passar a janela.
- **Stop:** stop original do 9.1 (default) ou `L[i] - tick` (parâmetro).
- **Saída:** `trailing_media`.

---

## 2. Setups de candle / preço

### 2.1 Setup 123 de compra
Origem: Larry Williams / Joe Ross (formação 1-2-3); versão brasileira difundida por Stormer.

**Compra**
- **Condição de sinal (3 candles: `i-2`, `i-1`, `i`):**
  - `L[i-1] < L[i-2]` **e** `L[i-1] < L[i]` (candle do meio com a menor mínima).
- **Filtros opcionais:**
  - `exigir_fechamento_fundo`: `C[i] > C[i-1]` (default `false`).
  - `exigir_tendencia`: `subindo(MME(9) ou MMA(21), i)` (default `false`; recomendado ligar).
  - `inside_no_meio_invalida`: invalidar se `i-1` for inside bar de `i-2` (default `false`).
- **Entrada:** compra stop em `H[i] + tick`.
- **Arrasto:** se `i+1` não acionar e tiver máxima menor e mínima maior que `L[i-1]` (o fundo continua valendo), reavaliar com `i+1` como terceiro candle (o padrão continua formado). Parâmetro `arrastar_entrada`, default `true`.
- **Invalidação:** qualquer candle perder `L[i-1]` antes do acionamento.
- **Stop:** `L[i-1] - tick` (o fundo do 123).
- **Saída:** alvo fixo `m * R` (default 2R) ou `trailing_minima`.

### 2.2 PFR — Preço de Fechamento de Reversão
**Compra**
- **Condição de sinal:** `L[i] < L[i-1]` **e** `C[i] > C[i-1]`.
- **Variante estrita (`pfr_estrito`, default `false`):** `L[i] < min(L[i-1], L[i-2])` **e** `C[i] > C[i-1]`.
- **Filtro de contexto opcional:** o candle `i` deve ser a menor mínima dos últimos `n` candles (`pfr_minima_n`, default desligado; sugerido 5–10) — para pegar fundos, não ruído.
- **Entrada:** compra stop em `H[i] + tick` (validade 1 candle).
- **Stop:** `L[i] - tick`.
- **Saída:** alvo fixo `m * R` ou `trailing_minima`.

### 2.3 Ponto Contínuo (pullback na MMA21)
Difundido por Stormer.

**Compra**
- **Pré-condições:**
  - `MMA(21)` subindo há pelo menos `k` candles (`k` default 3): `MMA21[i] > MMA21[i-k]` e `subindo(MMA21, i)`.
  - Preço vinha acima da média: `C[i-j] > MMA21[i-j]` para `j = 1..p` (default `p = 3`).
- **Condição de sinal (toque):** `L[i] <= MMA21[i] * (1 + tolerancia)` (default `tolerancia = 0`) **e** `C[i] >= MMA21[i] * (1 - tolerancia_fechamento)` (default: fecha acima ou na média; parâmetro).
- **Entrada:** compra stop em `H[i] + tick`.
- **Arrasto:** se `i+1` não acionar e também tocar a média (mantidas as pré-condições), passa a ser o sinal.
- **Invalidação:** fechamento abaixo da média por `x` candles (default 1) ou média deixa de subir.
- **Stop:** `L[i] - tick`.
- **Saída:** `trailing_minima`, ou alvo no último topo (`max(H)` dos últimos `n` candles, default 20), ou `m * R`.

### 2.4 Barra Elefante
**Compra**
- **Condição de sinal:**
  - Candle de alta: `C[i] > O[i]`.
  - Tamanho: `range[i] >= fator * média(range, n)[i-1]` (default `fator = 2.0`, `n = 20`). Variante: usar `body` no lugar de `range` (`base_tamanho = "range" | "corpo"`).
  - Corpo dominante: `body[i] / range[i] >= corpo_min` (default 0.70).
  - Fechamento perto da máxima: `(H[i] - C[i]) / range[i] <= pavio_max` (default 0.25).
- **Filtro opcional:** volume acima da média `V[i] > MMA(V,20)[i]`.
- **Entrada (parâmetro `entrada_elefante`):**
  - `"rompimento"` (default): compra stop em `H[i] + tick` no candle seguinte.
  - `"fechamento"`: compra no `C[i]`.
- **Stop (parâmetro):** `L[i] - tick` (default) ou meio do candle `(H[i] + L[i]) / 2`.
- **Saída:** `m * R` (default 2R) ou `trailing_minima`.

### 2.5 Inside Bar
**Compra**
- **Condição de sinal:** `H[i] < H[i-1]` **e** `L[i] > L[i-1]` (variante inclusiva com `<=`/`>=` — parâmetro `inclusivo`, default `false`).
- **Filtro de tendência (recomendado):** `subindo(MME(9), i)` ou `C[i] > MMA(21)[i]`.
- **Entrada (parâmetro `referencia_inside`):**
  - `"inside"` (default): compra stop em `H[i] + tick`.
  - `"mae"`: compra stop em `H[i-1] + tick` (rompimento da barra mãe).
- **Stop:** `L[i] - tick` (inside) ou `L[i-1] - tick` (mãe) — acompanha a referência.
- **Validade:** default 2 candles.
- **Saída:** `m * R` ou `trailing_minima`.

---

## 3. Setups baseados em indicadores

### 3.1 IFR2 (RSI de 2 períodos) — Larry Connors
**Compra (versão mais backtestada no Brasil)**
- **Indicador:** `IFR(2)` de Wilder sobre o fechamento.
- **Condição de sinal:** `IFR2[i] < nivel_compra` (default 25; variantes comuns: 10, 5).
- **Filtro de tendência:** `C[i] > MMA(200)[i]` (default **ligado** neste setup; parâmetro).
- **Entrada (parâmetro `entrada_ifr2`):**
  - `"fechamento"` (default): compra em `C[i]`.
  - `"abertura_seguinte"`: compra em `O[i+1]`.
- **Saída (combinável):**
  - **Alvo:** venda limitada em `max(H[j-1], H[j-2])` recalculada a cada candle `j` em posição (default). Se `O[j]` abrir acima do alvo, sai em `O[j]`.
  - **Saída por tempo:** sair no fechamento após `n_candles` (default 7) se o alvo não for atingido.
  - **Saída por indicador (variante):** `IFR2 > nivel_saida` (ex.: 70) → sai no fechamento.
- **Stop:** originalmente **sem stop técnico** (só saída por tempo). Opcional: `stop_pct` sobre a entrada (default desligado).
- **Venda:** espelho com `IFR2 > 75` e `C < MMA(200)` (pouco usada em ações).

### 3.2 Agulhada do Didi — Odir Aguiar (Didi)
**Indicadores**
- **Didi Index:** `MMA(3)`, `MMA(8)` e `MMA(20)` do fechamento, normalizadas pela MMA(8):
  - `curta = MMA3 / MMA8 - 1`, `longa = MMA20 / MMA8 - 1` (a MMA8 é a linha zero).
- **ADX(8)** com `DI+` e `DI-` (período 8 é o padrão do Didi; parâmetro).
- **Bollinger(8, 2)** — padrão Didi; parâmetro (alternativa 20,2).

**Compra**
- **Agulhada de compra no candle `i`:** a curta cruza a MMA8 **para cima** e a longa cruza a MMA8 **para baixo**, no mesmo candle:
  - `MMA3[i-1] <= MMA8[i-1]` e `MMA3[i] > MMA8[i]`
  - `MMA20[i-1] >= MMA8[i-1]` e `MMA20[i] < MMA8[i]`
  - Tolerância: aceitar os dois cruzamentos em até `janela_cruzamento` candles (default 0 = mesmo candle; 1 é variante comum).
- **Confirmações (cada uma ligável/desligável; default todas ligadas):**
  - `confirma_adx`: `ADX[i] > ADX[i-1]` (ADX subindo) e `DI+[i] > DI-[i]`. Opcional: `ADX[i] >= adx_min` (default 0/desligado; 20 é variante comum).
  - `confirma_bollinger`: bandas abrindo — `BBsup[i] > BBsup[i-1]` **e** `BBinf[i] < BBinf[i-1]`.
- **Entrada:** compra stop em `H[i] + tick` (default) ou no fechamento (`entrada_didi`).
- **Stop:** `L[i] - tick` ou mínima dos últimos 3 candles (parâmetro).
- **Saída:** cruzamento inverso (agulhada de venda ou `MMA3` cruzar abaixo de `MMA8` — parâmetro), ou `m * R`.

### 3.3 Cruzamento de médias (9 × 21)
**Compra**
- **Médias (parâmetros):** rápida `MME(9)`, lenta `MMA(21)` (variantes: MME×MME, 9×21, 20×50).
- **Condição de sinal:** `rapida[i-1] <= lenta[i-1]` **e** `rapida[i] > lenta[i]`.
- **Filtro opcional:** `C[i] > MMA(200)[i]` (e/ou lenta subindo).
- **Entrada:** `"fechamento"` (default) ou compra stop em `H[i] + tick`.
- **Stop:** mínima dos últimos `n` candles (default 5) `- tick`.
- **Saída:** cruzamento inverso (default) ou `m * R`.

### 3.4 Bollinger — fechamento fora e retorno
**Compra**
- **Indicador:** Bollinger(20, 2).
- **Condição de sinal:** `C[i-1] < BBinf[i-1]` **e** `C[i] > BBinf[i]`.
- **Filtro opcional:** `C[i] > C[i-1]`; filtro de tendência MM200.
- **Entrada:** compra stop em `H[i] + tick`.
- **Stop:** `min(L[i], L[i-1]) - tick`.
- **Saída (parcial configurável):** alvo 1 = banda central `MMA20` (no candle da saída); alvo 2 = banda superior. Parâmetro `saida_bb = "central" | "superior" | "parcial"` (default `"central"`).

### 3.5 Recuo com IFR curto — Stormer
Fonte: vídeo do canal Stormer no YouTube (https://www.youtube.com/watch?v=Ue8RUMy-0KI). O vídeo testa o sistema em 60 minutos e no diário e anuncia de 80% a 90% de acerto.

**Compra**
- **Tendência:** `MME(17)[i] > MME(20)[i]` (parâmetros `periodo_rapida` e `periodo_lenta`). O vídeo começa com 9 × 11 e adota 17 × 20 depois do teste.
- **Condição de sinal:** `IFR(4)[i] < nivel_compra` (default 25). Variantes do vídeo: IFR(2), que dá mais sinais com acerto um pouco menor, e níveis 30 ou 35.
- **Entrada:** compra na abertura `O[i+1]`.
- **Stop:** `L[i] - distancia_stop`, valor fixo em reais (default R$ 0,50). Se o stop ficar ≤ 0, não há sinal. O vídeo também testa stops de 1,4% e 2% da entrada; eles ficam fora desta versão.
- **Saída:** no fechamento do primeiro candle `j` com `C[j] > preço de entrada`, desde que a posição tenha pelo menos `pregoes_minimos` pregões, contando o da entrada (default 2). Com 1, é a primeira versão do vídeo, que pode sair no fechamento do próprio dia da entrada.
- **Aquecimento:** 3 × 20 = 60 candles.

---

## 4. Setups internacionais muito usados no Brasil

### 4.1 Holy Grail — Linda Raschke
**Compra**
- **Indicadores:** `ADX(14)`, `DI+`, `DI-`, `MME(20)`.
- **Pré-condições:** `ADX[i] > 30` (parâmetro `adx_min`) e `DI+[i] > DI-[i]` (tendência de alta forte).
- **Condição de sinal:** pullback que toca a média: `L[i] <= MME20[i]` (primeiro toque após o ADX passar de 30 — parâmetro `apenas_primeiro_toque`, default `true`).
- **Entrada:** compra stop em `H[i] + tick`.
- **Arrasto:** se não acionar e o próximo candle continuar no pullback (máxima menor), entrada vai para a máxima dele.
- **Stop:** mínima do pullback `- tick` (`min(L)` desde o último topo).
- **Saída:** alvo no topo anterior (`max(H)` do movimento antes do pullback) — default; alternativa `trailing_minima`.

### 4.2 1-2-3 e Ross Hook — Joe Ross
Requer detecção de pivôs.

**Detecção de pivô (fractal):**
- Fundo de pivô em `k`: `L[k]` é a menor mínima entre `k-n` e `k+n` (default `n = 2`).
- Topo de pivô em `k`: `H[k]` é a maior máxima entre `k-n` e `k+n`.
- O pivô só é confirmado `n` candles depois (evitar look-ahead no backtest).

**1-2-3 de fundo (compra)**
- **Ponto 1:** fundo de pivô que é a menor mínima dos últimos `lookback` candles (default 20).
- **Ponto 2:** topo de pivô posterior ao ponto 1.
- **Ponto 3:** fundo de pivô posterior ao ponto 2 com `L[3] > L[1]`.
- **Entrada:** compra stop em `H[ponto2] + tick`.
- **Stop:** `L[ponto3] - tick`.
- **Invalidação:** perda de `L[ponto3]` antes do acionamento.

**Ross Hook (continuação)**
- Após o rompimento do ponto 2, o **primeiro candle que não faz nova máxima** marca o hook: `H_hook = max(H)` desde o rompimento.
- **Entrada:** compra stop em `H_hook + tick`.
- **Stop:** mínima da correção após o hook `- tick`.
- **Saída:** `trailing_minima` ou `m * R`.

### 4.3 Rompimento de Donchian / Tartarugas (Richard Dennis)
**Compra**
- **Canais:** `max(H)` dos últimos `n_entrada` candles **excluindo** o atual; `min(L)` dos últimos `n_saida` candles.
- **Sistema 1 (default):** `n_entrada = 20`, `n_saida = 10`.
- **Sistema 2:** `n_entrada = 55`, `n_saida = 20`.
- **Entrada:** compra stop em `max(H[i-n_entrada+1 .. i]) + tick` (válida para o candle `i+1`).
- **Stop inicial:** `entrada - 2 * ATR(20)` (parâmetro `multiplo_atr`).
- **Saída:** venda stop no rompimento de `min(L)` de `n_saida` candles, ou stop ATR (o que vier primeiro).
- **Filtro original do Sistema 1 (opcional, `filtro_ultimo_vencedor`):** ignorar o sinal se o último rompimento de 20 dias teria sido vencedor.
- **Pirâmide (opcional):** adicionar unidades a cada `0.5 * ATR` a favor, até 4 unidades.

---

## 5. Modelo de dados sugerido para o catálogo de setups

Sugestão de estrutura (agnóstica de linguagem) para cada setup no app:

```
SetupDefinition {
  id: string                 // ex.: "lw_9_1", "pfr", "ifr2", "didi_agulhada"
  nome: string               // ex.: "Setup 9.1 (Larry Williams)"
  familia: string            // "larry_williams" | "candle" | "indicador" | "internacional"
  origem: string             // autor / divulgador
  direcoes: ["compra", "venda"]
  timeframe: "D1"
  indicadores: [ { tipo: "MME", periodo: 9 }, ... ]
  parametros: { nome: { tipo, default, min, max, descricao } }
  sinal(candles, i, params) -> Sinal | null
  gerenciar(posicao, candles, j, params) -> AcaoSaida | null
}

Sinal {
  setup_id, direcao, indice_sinal,
  preco_entrada, tipo_entrada ("stop" | "fechamento" | "abertura"),
  stop_inicial, alvo (opcional),
  validade_candles, regra_arrasto (bool)
}
```

### Casos de teste recomendados (por setup)
1. Sinal válido simples → gera entrada e stop corretos.
2. Gap acima da entrada → executa na abertura (ou cancela, conforme `aceitar_gap`).
3. Sinal não acionado → arrasto (quando aplicável) ou expiração.
4. Invalidação antes do acionamento.
5. Entrada e stop no mesmo candle → regra `ordem_intrabar`.
6. Warm-up insuficiente → nenhum sinal.
7. Versão de venda espelhada.

---

## 6. Resumo rápido (tabela de referência)

| ID | Setup | Sinal (compra) | Entrada | Stop | Saída default |
|---|---|---|---|---|---|
| `lw_9_1` | 9.1 | MME9 vira p/ cima | máx. sinal + tick | mín. sinal | trailing média |
| `lw_9_2` | 9.2 | MME9 subindo, C < mín. anterior | máx. sinal | mín. sinal | trailing média |
| `lw_9_3` | 9.3 | MME9 subindo, 2 fech. < C[i-2] | máx. sinal | mín. sinal | trailing média |
| `lw_9_4` | 9.4 | 9.1 falha sem perder stop | máx. candle que virou p/ baixo | stop do 9.1 | trailing média |
| `s_123` | 123 | candle do meio com menor mínima | máx. 3º candle | mín. do meio | 2R |
| `pfr` | PFR | mín. < anterior e fech. > anterior | máx. sinal | mín. sinal | 2R |
| `ponto_cont` | Ponto Contínuo | toque na MMA21 subindo | máx. sinal | mín. sinal | trailing mínima |
| `elefante` | Barra Elefante | range ≥ 2× média, fech. no topo | máx. sinal | mín. sinal | 2R |
| `inside` | Inside Bar | H < H ant. e L > L ant. | máx. inside | mín. inside | 2R |
| `ifr2` | IFR2 | IFR2 < 25 e C > MM200 | fechamento | sem stop | máx. 2 dias / 7 candles |
| `didi` | Agulhada do Didi | MMA3↑ e MMA20↓ cruzam MMA8 + ADX + BB | máx. sinal | mín. sinal | cruzamento inverso |
| `recuo_ifr_curto` | Recuo com IFR curto (Stormer) | MME17 > MME20 e IFR4 < 25 | abertura seguinte | mín. sinal − R$ 0,50 | 1º fechamento com lucro a partir do 2º pregão |
| `cruz_9_21` | Cruzamento 9×21 | MME9 cruza MMA21 p/ cima | fechamento | mín. 5 candles | cruzamento inverso |
| `bb_retorno` | Bollinger retorno | fecha fora e volta p/ dentro | máx. sinal | mín. 2 candles | banda central |
| `holy_grail` | Holy Grail | ADX > 30, toque MME20 | máx. sinal | mín. pullback | topo anterior |
| `ross_123` | 1-2-3 / Ross Hook | pivôs 1-2-3 | rompimento ponto 2 | ponto 3 | trailing / 2R |
| `donchian` | Tartarugas | rompe máx. 20 dias | máx. 20 + tick | 2 ATR | mín. 10 dias |
| `separacao_alta` | Linha de separação de alta | baixa forte + alta forte com a mesma abertura | máx. sinal | mín. sinal | 2R |
| `mat_hold` | Mat Hold | 5 candles, rompe as 4 máximas | máx. 5º candle | mín. 5º candle | 2R |
| `penetrante` | Padrão penetrante | gap abaixo da mínima, fecha acima do meio | máx. sinal | mín. sinal | 2R |
| `deliberante` | Padrão deliberante | 2 altas fortes + 1 pequeno | máx. 3º candle | mín. 3º candle | 2R |

---

## 7. Padrões de candle — Thomas Bulkowski

Fonte: vídeo "6 padrões de candle" (https://www.youtube.com/watch?v=P3xgP_alm48), que apresenta padrões testados por Thomas Bulkowski. Bebê engolido e Três quedas, também do vídeo, são padrões de **venda** e ficam fora: o app só simula compra.

### 7.0 Regras comuns
- **Medidas:** `corpo[k] = |C[k] - O[k]|`; `faixa[k] = H[k] - L[k]`. O índice `i` é o último candle do padrão, e `n` é o número de candles do padrão.
- **Candle forte:** `corpo[k] >= fator_forte × MMA(corpo, n_media_corpo)[i-n]` (default 1,3 × média de 20). A média para no candle anterior ao padrão.
- **Fecha perto da máxima:** `H[k] - C[k] <= extremo_pct% × faixa[k]` (default 25%). Perto da mínima: `C[k] - L[k] <= extremo_pct% × faixa[k]`.
- **Tendência (padrões de continuidade):** `MMA(21)[i] > MMA(21)[i-1]` (`exigir_tendencia`, default ligado).
- **Entrada:** compra stop em `H[i] + tick`, válida por 1 pregão.
- **Stop (`stop_padrao`):** `L[i] - tick` (default, "arriscar um candle") ou menor mínima do padrão `- tick`.
- **Saída:** alvo de 2R (default) ou stop móvel na mínima, como nos setups de candle e preço. O vídeo não define a saída.
- Os percentuais de acerto citados no vídeo são de Bulkowski, em outro mercado e com outra saída: não são o resultado esperado no app.

### 7.1 Linha de separação de alta (72% de continuidade, segundo o vídeo)
- `C[i-1] < O[i-1]` e candle `i-1` forte.
- `C[i] > O[i]`, candle `i` forte e fechando perto da máxima.
- `|O[i] - O[i-1]| <= tolerancia_abertura_pct% × faixa[i-1]` (default 10%): abre "na mesma abertura", em gap de alta.

### 7.2 Mat Hold (78%)
- Candle `i-4`: de alta, forte, fechando perto da máxima.
- Candle `i-3`: de baixa, com `C[i-3] > C[i-4]`.
- Candle `i-2`: de baixa, com `C[i-2] < C[i-3]`. Candle `i-1`: qualquer cor, com `C[i-1] < C[i-2]`.
- `min(L[i-3..i-1]) > L[i-4]`.
- Candle `i`: de alta, forte, com `C[i] > max(H[i-4..i-1])`.

### 7.3 Padrão penetrante (reversão)
- Candle `i-1`: de baixa, forte, fechando perto da mínima. Com `exigir_queda` (default), `C[i-1] < MMA(21)[i-1]`.
- `O[i] < L[i-1]` (gap de baixa).
- `(O[i-1] + C[i-1]) / 2 < C[i] < O[i-1]`.

### 7.4 Padrão deliberante (77%)
- Candles `i-2` e `i-1`: de alta e fortes, com `C[i-1] > C[i-2]`.
- `|O[i] - C[i-1]| <= tolerancia_abertura_pct% × faixa[i-1]` (default 10%).
- `corpo[i] <= fator_pequeno × média de corpo` (default 0,5).

