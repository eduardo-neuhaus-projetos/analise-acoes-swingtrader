# PRD: aplicativo de swing trade para a B3

Nov 6, 2026 · @Eduardo

## Resumo e objetivos

O MVP é um aplicativo web pessoal que transforma candles diários da B3 em sinais, trades simulados e um dashboard que mostra se o setup funciona em cada ativo. As análises ficam em duas abas separadas: uma com os 3 meses da brapi e outra com o histórico do Yahoo desde 01/01/2010. O catálogo tem 21 setups, descritos em [`SETUPS_SWING_TRADE.md`](SETUPS_SWING_TRADE.md), e novos setups entram pelo registro, sem mudança nas telas.

**Problema.** Avaliar um setup manualmente exige percorrer gráficos, anotar trades em planilha e aplicar as regras sem erro. O processo é lento e sujeito a viés, e os resultados de ativos e períodos diferentes ficam difíceis de comparar.

**Proposta de valor.** Em poucos cliques, você escolhe um ativo, vê cada trade no gráfico, confere a taxa de acerto e acompanha novos sinais com as mesmas regras.

**Metas propostas para o MVP:**

| Meta | Como medir | Alvo |
| --- | --- | --- |
| Análise rápida | Tempo entre escolher um ativo com dados em cache e ver o resultado | Até 3 s |
| Regras corretas | Casos de referência do 9.1 aprovados nos testes | 100% |
| Resultado rastreável | Trades que abrem no gráfico com sinal, entrada, stop e saída | 100% |
| Acompanhamento em dia | Pregões processados sem intervenção manual | Pelo menos 95% |
| Setup novo sem retrabalho | Mudanças necessárias no motor e nas telas ao incluir um setup | Nenhuma |

## Usuário e jornadas

O único usuário do MVP é o próprio dono do aplicativo: um trader de swing na B3 que conhece análise técnica e opera no gráfico diário. Ele quer validar regras com dados antes de confiar em um setup, e não precisa de ajuda para entender os termos básicos.

**Jornada principal: avaliar um setup em um ativo**

1. Adicionar o ativo pelo campo "Adicionar ativo", sempre visível, escolhendo na lista ou digitando o código ou o nome, como PETR4.
2. Baixar os dados das duas fontes, ou usar o que já está em cache.
3. Escolher o setup e ajustar os parâmetros, se quiser.
4. Escolher a aba brapi ou Yahoo e ver os trades no gráfico e as métricas no dashboard.
5. Colocar o ativo em acompanhamento na aba desejada.

**Jornada diária: acompanhar novos sinais**

1. Após o fechamento do pregão, o aplicativo atualiza os candles dos ativos acompanhados em cada fonte.
2. O motor recalcula os sinais e atualiza os trades simulados.
3. O usuário abre a tela de acompanhamento, escolhe a aba e vê o que mudou: sinais armados, entradas, stops e trades encerrados.

## Escopo

O MVP cobre todo o ciclo de análise e simulação de um setup em candles diários, sem enviar ordens nem registrar operações reais.

| Tema | Dentro do MVP | Fora do MVP |
| --- | --- | --- |
| Mercado | Ações da B3 no mercado à vista | FIIs, BDRs, opções, futuros, mercado fracionário |
| Dados | Candles diários de duas fontes gratuitas, analisados em abas separadas | Candles intradiários, tempo real, planos pagos da brapi |
| Setups | Os 21 setups de `SETUPS_SWING_TRADE.md`, somente compra, com arquitetura extensível | Venda a descoberto, pirâmide, saída parcial, editor visual de setups |
| Trades | Backtest e acompanhamento simulado | Trades reais, envio de ordens, integração com corretora |
| Análise | Um ativo por vez e comparação entre ativos, parâmetros e setups dentro da mesma aba | Otimização automática de parâmetros, carteira com capital compartilhado, soma de resultados entre abas |
| Uso | Um usuário, sem login, em computador próprio ou servidor privado | Multiusuário, assinatura, aplicativo móvel nativo |
| Fiscal | Custos operacionais configuráveis | Cálculo de imposto e DARF |

## Duas análises separadas

O aplicativo trabalha com dois mundos independentes, cada um em sua aba, e nunca mistura dados ou resultados entre eles. O mesmo setup roda nos dois, com as mesmas regras.

| Característica | Aba brapi | Aba Yahoo |
| --- | --- | --- |
| Fonte | Plano Gratuito da brapi, sempre | Yahoo Finance via yfinance |
| Cadastro | Sem token, só PETR4, MGLU3, VALE3 e ITUB4; os demais ativos pedem o token de uma conta gratuita | Nenhum, para qualquer ativo disponível na fonte |
| Período | Mostra os 3 meses mais recentes e guarda todos os candles já baixados | Desde 01/01/2010, início do histórico do app |
| Volume aproximado | Cerca de 60 pregões na tela e cerca de 250 guardados a cada ano | Cerca de 250 pregões por ano desde 2010, cerca de 4.000 em 2026 |
| Melhor uso | Ver o comportamento recente do setup | Avaliar o setup com uma amostra longa |
| Confiança nas métricas | Baixa, com aviso de amostra pequena | Maior, conforme a quantidade de trades |
| Se a fonte falhar | Mantém os últimos dados da aba e avisa | Mantém os últimos dados da aba e avisa |

**Regras de separação:**

- **Dados e resultados:** cada aba tem seus próprios candles, execuções, trades, métricas e lista de acompanhamento.
- **Sem fonte de reserva:** uma fonte nunca substitui a outra, inclusive quando falha.
- **Sem soma:** nenhuma métrica combina resultados das duas abas.
- **Diferenças esperadas:** o mesmo ativo pode mostrar trades diferentes em cada aba, porque as fontes e o início da MME são diferentes.

**Efeitos da janela de 3 meses:**

- A tela mostra os trades encerrados dentro da janela e os que seguem abertos, mesmo se iniciados antes dela.
- No primeiro download, só há 3 meses de dados, e os sinais começam a partir do 11º candle. Com o acúmulo, a MME usa os candles guardados, e o avanço da janela deixa de alterar os trades.
- O mapa mensal, o resultado anual e a taxa de acerto móvel têm pouca informação nessa aba, e isso fica indicado na tela.

**Acúmulo de candles da brapi:**

A aba mostra só os últimos 3 meses. O restante fica apenas armazenado, sem data para apagar, e serve ao cálculo da MME. Esse histórico não pode ser baixado de novo no plano Gratuito.

1. **Gravação:** cada atualização inclui os pregões novos e registra os valores exatamente como vieram.
2. **Comparação:** os pregões em comum com o que já está guardado revelam se um provento mudou a base de ajuste.
3. **Rebase:** se a base mudou, o fator encontrado é aplicado aos candles antigos, que a brapi não entrega mais. Sem isso, o histórico teria saltos falsos de preço.
4. **Lacuna:** se o aplicativo ficar mais tempo sem atualizar do que a janela cobre, a série fica marcada como interrompida, e os indicadores recomeçam depois dela.

Dados acumulados não ficam automaticamente mais precisos. Eles só aumentam o período disponível, e a qualidade depende da fonte e deste processo.

## Requisitos funcionais

Os requisitos abaixo cobrem o MVP, e todos são obrigatórios, exceto os marcados como "Desejável".

### Dados de mercado

Os dados vêm de duas fontes gratuitas, cada uma com sua aba: o [plano Gratuito da brapi](https://brapi.dev/pricing), limitado a 3 meses, e o Yahoo Finance, com o histórico desde 01/01/2010. Nenhum plano pago da brapi faz parte do produto. O limite de quatro ativos vale para o uso sem token, e não para o plano Gratuito em si: a [página de planos](https://brapi.dev/pricing) não restringe quais ativos a conta gratuita consulta, mas nenhuma página consultada garante a cobertura completa. Por isso o aplicativo testa o token ao guardá-lo.

**Início do histórico: 01/01/2010.** É um parâmetro fixo do app (`calendario.INICIO_HISTORICO`) e vale para as duas fontes. Nenhum candle anterior é baixado, guardado, validado ou simulado, e nenhuma data de análise, comparação ou acompanhamento pode ser anterior. Motivos:

- Os dados mais antigos do Yahoo têm erros grosseiros. Em PETR4, o candle de 05/08/2003 abriu a 67,50 e fechou a 6,85, e só ele gerava um trade falso de +907% no IFR2.
- O resultado depende de onde o histórico começa, porque indicadores e aquecimento começam no primeiro candle. Com uma data fixa, o app e qualquer conferência externa, como os robôs do Profit, partem do mesmo ponto.
- Ainda sobram mais de 15 anos, cerca de 4.000 pregões, para avaliar um setup.

Ao iniciar, o backend apaga candles anteriores guardados por versões antigas e aumenta a versão dessas séries. Eles vinham só do Yahoo e podem ser baixados de novo. O aquecimento dos setups conta a partir de 01/01/2010, então o IFR2 com MMA 200 só gera o primeiro sinal depois de cerca de 600 pregões, por volta de 2012.

| ID | Requisito | Critério de aceite |
| --- | --- | --- |
| RF-01 | Buscar ativos por código ou nome | Abrir o campo, sem digitar, lista os ativos conhecidos; digitar "PETR" lista PETR3 e PETR4; um código fora da lista pode ser tentado; um código inexistente mostra mensagem clara |
| RF-01A | Manter a lista "Meus ativos" | Uma barra em todas as telas mostra os ativos adicionados e o campo "Adicionar ativo"; um clique troca o ativo em análise; tirar um ativo da lista não apaga os dados guardados; a lista volta ao reabrir o aplicativo |
| RF-01B | Orientar e testar o token da brapi | Sem token, a aba brapi explica o limite e oferece configurar o token ou ver o ativo na aba Yahoo; ao guardar o token, o aplicativo consulta um ativo que exige token e informa se a brapi aceitou; se aceitar, baixa de novo o ativo aberto |
| RF-02 | Baixar candles diários do ativo | A aba brapi traz os 3 meses mais recentes, e a aba Yahoo traz o histórico desde 01/01/2010, com aviso se houver menos de 10 anos; nada anterior a 01/01/2010 é guardado |
| RF-03 | Atualizar de forma incremental | Uma nova atualização busca só o que falta, e reprocessa a série quando um novo ajuste de proventos altera os preços antigos |
| RF-04 | Guardar cache local | Um ativo já baixado abre e roda sem internet |
| RF-05 | Isolar as fontes | Se uma fonte falhar, só a aba dela mostra o aviso e os últimos dados em cache; a outra fonte nunca a substitui |
| RF-06 | Mostrar a origem dos dados | A tela mostra fonte, plano, data da última atualização e último pregão disponível |
| RF-07 | Validar candles | Candles com máxima abaixo da mínima, preço zerado ou pregão faltando geram alerta, e a execução informa quantos existem |
| RF-08 | Comparar provedores (Desejável) | Sob demanda, a tela Dados lista os pregões com diferença acima de um limite configurável, sem misturar os resultados das abas |
| RF-09 | Separar as análises em abas | As abas brapi e Yahoo mostram só os dados e resultados da própria fonte, e a fonte ativa fica sempre visível; trocar de aba mantém ativo, setup e parâmetros |
| RF-09A | Acumular os candles da brapi | Candles que saem da janela de 3 meses continuam guardados e rebaseados; nenhuma tela mostra candles, trades ou métricas anteriores aos 3 últimos meses, e a tela Dados informa apenas o período guardado e as lacunas |

### Execução de setups

| ID | Requisito | Critério de aceite |
| --- | --- | --- |
| RF-10 | Escolher setup | A lista vem do registro de setups, sem nome fixo no código das telas |
| RF-11 | Ajustar parâmetros | O formulário é gerado pelo esquema do setup, valida limites e permite voltar ao padrão |
| RF-12 | Escolher período | Datas inicial e final limitam os trades sem cortar os candles necessários ao aquecimento da MME; o calendário não aceita datas anteriores a 01/01/2010, a barra de filtros mostra "Histórico desde 01/01/2010" e a API recusa datas anteriores com mensagem clara |
| RF-13 | Rodar backtest | O resultado guarda ativo, setup, versão, parâmetros, custos, fonte e período |
| RF-14 | Reproduzir resultado | Mesmos candles e parâmetros geram exatamente os mesmos trades |
| RF-15 | Listar trades | A tabela mostra entrada, saída, motivo da saída, duração e resultado bruto, líquido, em % e em R; ela pode ser exportada em CSV |

### Gráfico

| ID | Requisito | Critério de aceite |
| --- | --- | --- |
| RF-20 | Mostrar candles e indicadores | O gráfico mostra candles, volume e os indicadores declarados pelo setup, com zoom e deslocamento |
| RF-21 | Marcar trades | Sinal, entrada, stop e saída aparecem nos candles corretos |
| RF-22 | Ligar gráfico e tabela | Clicar em um trade centraliza o gráfico nele, e clicar em uma marca seleciona o trade |
| RF-23 | Explicar o trade | O detalhe mostra a regra que gerou cada evento e os avisos, como stop e entrada no mesmo candle |

### Acompanhamento

| ID | Requisito | Critério de aceite |
| --- | --- | --- |
| RF-30 | Criar lista de acompanhamento | Cada item pertence a uma aba, combina ativo, setup e parâmetros, e tem data de início própria |
| RF-31 | Atualizar após o pregão | Um processo agendado roda em dias de pregão e pode ser acionado manualmente; uma nova execução não duplica eventos |
| RF-32 | Mostrar estado atual | Cada item aparece como sem sinal, armado, posicionado ou com saída armada, com os preços das ordens para o próximo pregão |
| RF-33 | Registrar eventos | Sinais, entradas e saídas formam um histórico com data; uma edição de parâmetros abre uma nova versão, sem reescrever o passado |
| RF-34 | Avisar falha | Se a atualização falhar, a tela mostra o último pregão processado e o motivo |

### Dashboard

| ID | Requisito | Critério de aceite |
| --- | --- | --- |
| RF-40 | Mostrar acertos e erros | Percentuais e contagens batem com a lista de trades filtrada da aba |
| RF-41 | Mostrar evolução no tempo | Curva de capital, taxa de acerto móvel, mapa mensal e resultado anual seguem os mesmos filtros |
| RF-42 | Filtrar | Os filtros valem para ativo, setup, parâmetros, período e origem do trade, dentro da aba aberta |
| RF-43 | Comparar | Até 5 ativos, conjuntos de parâmetros ou setups aparecem lado a lado nas mesmas métricas, sempre dentro da mesma aba |
| RF-44 | Comparar com referências | A curva pode ser sobreposta ao buy and hold do ativo e ao Ibovespa, no mesmo período e com dados da fonte da aba |

## Catálogo de setups

As regras de cada setup estão em [`SETUPS_SWING_TRADE.md`](SETUPS_SWING_TRADE.md). A lista tem 21 setups em cinco famílias: Larry Williams (9.1 a 9.4), candle e preço (123, PFR, Ponto Contínuo, Barra Elefante e Inside Bar), padrões de candle de Bulkowski (Linha de separação de alta, Mat Hold, Padrão penetrante e Padrão deliberante), indicadores (IFR2, Recuo com IFR curto do Stormer, Agulhada do Didi, Cruzamento de médias e Bollinger) e internacionais (Holy Grail, 1-2-3 com Ross Hook e Tartarugas).

**Execução.** O motor continua sendo o único executor e passou a aceitar, além das ordens stop:

| Ordem | Comportamento |
| --- | --- |
| Compra ou venda no fechamento | Executa no fechamento do próprio candle que gerou a ordem. Na prática, supõe decidir nos últimos minutos do pregão, e por isso os trades mostram a regra usada |
| Compra na abertura | Executa na abertura do pregão seguinte |
| Alvo móvel | Venda limitada recalculada a cada fechamento. Se a abertura já estiver acima, executa na abertura |
| Trade sem stop | Sem risco definido, o trade não tem resultado em R e fica fora da expectativa e da distribuição em R |

**Adaptações à especificação dos setups:**

| Tema | Decisão |
| --- | --- |
| Direção | Somente compra, como no restante do MVP. As versões de venda ficam fora |
| Aquecimento | 3 vezes o maior período, como pede a especificação, inclusive nos filtros. O IFR2 padrão usa a MMA 200 e exige 600 candles, por isso não roda na aba brapi |
| Dimensionamento | O resultado em reais usa o capital por trade de Configurações, e não `risco_pct` |
| Fora desta versão | Pirâmide e `filtro_ultimo_vencedor` das Tartarugas, saída parcial do Bollinger, `variante_94` e `inside_no_meio_invalida` do 123 |
| `inside_no_meio_invalida` | Não entra porque nunca teria efeito: o candle do meio do 123 tem mínima menor que a anterior, então não pode estar contido nela |
| `variante_94` | A especificação pede a opção, mas descreve só uma variante |
| Agulhada do Didi | O padrão segue o vídeo [setup e operacional agulhada do didi passo a passo](https://www.youtube.com/watch?v=D586Z0uWHgk), do canal TraderDicas, e a regra da especificação fica como opção. Detalhes abaixo |
| 9.4 | O 9.1 é simulado à parte e só serve de contexto: os resultados mostram apenas os trades de retomada |
| Ross Hook | Fica no mesmo setup do 1-2-3, com a opção "Entradas" para escolher o 1-2-3, o hook ou os dois |

**Agulhada do Didi.** O vídeo opera ouro em 5 minutos e mostra as regras no gráfico, sem descrevê-las por completo. Esta é a leitura adotada para candle diário:

| Tema | Regra padrão | Origem |
| --- | --- | --- |
| Gatilho | MMA 3 cruza a MMA 20 para cima, com a MMA 3 acima da MMA 8. Na tela do Didi Index, a curta cruza a longa acima da linha neutra | Dois sinais marcados no vídeo |
| Quatro indicadores | Didi Index (3, 8, 20), ADX (8) subindo com DI+ acima de DI-, Estocástico (8, 3, 3) subindo com %K acima de %D, TRIX (8) subindo e acima da média de 3 | Parâmetros mostrados na tela. As condições de cada um são a leitura de "tudo indicado para cima" |
| Entrada | Abertura do pregão seguinte | Fala do vídeo |
| ADX mínimo | Desligado, disponível como parâmetro | O vídeo olha o nível 32. No diário, 32 deixa 4 a 8 sinais em 27 anos nos 5 ativos medidos, contra 53 a 91 sem ele |
| Stop e saída | Mínima do candle de sinal menos 1 tick, e MMA 3 cruzando abaixo da MMA 8 | Especificação. O vídeo não define stop, e os 200 pontos de alvo são do ouro em 5 minutos, sem equivalente aqui |
| Bollinger | Desligado, disponível como parâmetro | Não aparece no vídeo, só na especificação |
| Regra da especificação | MMA 3 e MMA 20 cruzando a MMA 8 no mesmo candle, disponível em "Gatilho" | Especificação |

**Recuo com IFR curto (Stormer).** Segue o [vídeo do canal Stormer](https://www.youtube.com/watch?v=Ue8RUMy-0KI). O apresentador muda as regras durante os testes, e o padrão adota a versão que ele resume no fim:

| Tema | Regra padrão | Origem |
| --- | --- | --- |
| Tendência | MME 17 acima da MME 20 | Resumo final do vídeo; o começo usa 9 × 11 |
| Gatilho | IFR de 4 períodos abaixo de 25; IFR 2 e outros níveis ficam como parâmetro | Vídeo. Ele diz que o IFR 2 dá mais sinais com acerto menor |
| Entrada | Abertura do pregão seguinte | Vídeo |
| Stop | R$ 0,50 abaixo da mínima do candle de sinal, em reais fixos | Vídeo. Como o app usa preço ajustado, R$ 0,50 pesa mais nos anos antigos de ações que pagaram muitos proventos. Os stops percentuais testados no vídeo ficam fora |
| Saída | Primeiro fechamento com lucro, a partir do 2º pregão na posição, contando o da entrada | Versão melhorada do vídeo; com 1 pregão, é a primeira versão |
| Saída por tempo | Nenhuma: sem lucro, a posição só sai no stop | O vídeo não define |

O acerto anunciado no vídeo, de 80% a 90%, vem de testes em 60 minutos e em outro período. No diário desde 2010, com o padrão e sem custos, o app mediu de 54% a 81% de acerto em 9 ativos, e a perda média ficou maior que o ganho médio em todos eles. Por isso o resultado acumulado foi negativo em PETR4, VALE3, ITUB4, BBAS3 e GGBR4.

**Padrões de candle (Bulkowski).** Vêm do [vídeo "6 padrões de candle"](https://www.youtube.com/watch?v=P3xgP_alm48). O vídeo descreve os padrões só no gráfico; os limites numéricos estão em `SETUPS_SWING_TRADE.md`, seção 7, e todos são parâmetros.

| Tema | Decisão |
| --- | --- |
| Bebê engolido e Três quedas | Fora: são padrões de venda, e o app só simula compra |
| Candle forte | Corpo de pelo menos 1,3 vez a média dos 20 corpos anteriores ao padrão |
| Fechamento no extremo | No máximo 25% da faixa do candle entre o fechamento e a máxima ou a mínima |
| Saída | Alvo de 2R ou stop móvel, como em "Candle e preço". O vídeo não define saída |
| Stop | Mínima do último candle, como o vídeo recomenda ("arriscar um candle"), ou menor mínima do padrão |
| Acerto citado | 71% a 78%, números de Bulkowski em outro mercado e com outra saída |
| Frequência | Raros no diário da B3. Em 10 ativos desde 2010, com os padrões: Linha de separação 9 sinais, Padrão penetrante 85, Padrão deliberante 94 e Mat Hold nenhum. No Mat Hold, o quinto candle nunca fechou acima das quatro máximas anteriores |

**Gráfico.** Indicadores em outra escala, como IFR, ADX e ATR, ficam em um painel abaixo dos candles. A Agulhada do Didi usa três painéis, porque ADX, Estocástico e TRIX têm escalas diferentes.

**Setups nas análises.** Na tela Setups, com um painel por família, o usuário marca quais setups aparecem no seletor, por setup ou pela família inteira, e o seletor leva a essa tela com "Editar lista". A escolha é salva a cada clique, fica no backend e guarda os setups ocultos, de modo que um setup novo aparece sem precisar ser marcado. Pelo menos um setup fica na lista. Se o setup aberto sair da lista, a análise passa para o primeiro da lista e a tela avisa. Esconder um setup não apaga resultados e não interrompe itens em Acompanhamento.

## Especificação do Larry Williams 9.1

O setup compra o rompimento da máxima do candle em que a MME de 9 períodos vira para cima, e sai quando ela vira para baixo e a mínima desse candle é perdida. As regras seguem a seção 1.1 de [`SETUPS_SWING_TRADE.md`](SETUPS_SWING_TRADE.md).

### Regras

| Etapa | Regra padrão |
| --- | --- |
| Indicador | MME de 9 períodos sobre o fechamento, iniciada pela média simples dos 9 primeiros candles |
| Sinal | `MME[t] > MME[t-1]` e `MME[t-1] <= MME[t-2]` |
| Entrada | Ordem stop na máxima do candle de sinal + 1 tick, válida a partir do pregão seguinte |
| Gatilho não acionado | Enquanto a MME seguir subindo e a máxima do novo candle for menor, o gatilho passa para essa máxima + 1 tick |
| Cancelamento | Se a MME virar para baixo antes da entrada, o sinal é cancelado |
| Stop inicial | Mínima do candle de sinal vigente − 1 tick: acompanha o gatilho até a entrada e fica fixo depois dela |
| Saída armada | Quando a MME vira para baixo, ordem stop na mínima desse candle − 1 tick |
| Saída não acionada | A ordem passa para a mínima de cada novo candle enquanto a MME cair, e é cancelada se ela voltar a subir |
| Novo sinal | Sinais são ignorados com posição aberta; após a saída, o setup volta a procurar sinal |

### Parâmetros

| Parâmetro | Padrão | Opções |
| --- | --- | --- |
| Período da MME | 9 | 2 a 200 |
| Exigir fechamento acima da MME no sinal | Não | Sim, não |
| Atualizar gatilho não acionado | Sim | Sim, não (gatilho válido só no próximo candle) |
| Stop acompanha o gatilho atualizado | Sim | Sim, não (stop fica no candle do primeiro sinal) |
| Tick | R$ 0,01 | Valor positivo |
| Alvo fixo em R | Desligado | Múltiplo positivo, como 2R |

### Exemplo completo: trade vencedor

Os candles são fictícios. O cálculo usa fator de suavização de 0,2 e parte de MME de 20,10 e 20,00 nos dois pregões anteriores ao D1. Custos não estão incluídos.

| Pregão | Abertura | Máxima | Mínima | Fechamento | MME | O que acontece |
| --- | --- | --- | --- | --- | --- | --- |
| D1 | 20,00 | 20,60 | 19,90 | 20,50 | 20,10 | MME vira para cima: gatilho em 20,61 e stop em 19,89 |
| D2 | 20,55 | 20,90 | 20,40 | 20,80 | 20,24 | Entrada em 20,61 |
| D3 | 20,90 | 22,10 | 20,85 | 22,00 | 20,59 | Posição mantida |
| D4 | 22,10 | 23,60 | 22,00 | 23,50 | 21,17 | Posição mantida |
| D5 | 23,50 | 24,60 | 23,40 | 24,50 | 21,84 | Posição mantida |
| D6 | 23,00 | 23,10 | 21,60 | 21,70 | 21,81 | MME vira para baixo: saída armada em 21,59 |
| D7 | 21,70 | 21,80 | 21,20 | 21,30 | 21,71 | Saída em 21,59 |

O risco inicial é de R$ 0,72 (20,61 − 19,89). O ganho é de R$ 0,98 por ação (21,59 − 20,61), ou seja, +4,75% e +1,36R.

### Casos especiais

Os casos abaixo partem do mesmo D1: gatilho em 20,61, stop em 19,89 e risco de R$ 0,72.

| Caso | Situação | Resultado esperado |
| --- | --- | --- |
| Gatilho atualizado | D2 tem máxima de 20,40, sem entrada, e a MME segue subindo | O gatilho de D3 passa para 20,41, e o stop, para a mínima de D2 − 1 tick |
| Sinal cancelado | Sem entrada em D2, e a MME vira para baixo em D2 | Nenhum trade é aberto |
| Gap na entrada | D2 abre em 20,90, acima do gatilho | Entrada em 20,90, com risco de R$ 1,01 até o stop |
| Gap no stop | Posição aberta em 20,61 e um pregão abre em 19,50 | Saída em 19,50: −5,39% e −1,54R |
| Stop no candle da entrada | D2 tem máxima de 20,70 e mínima de 19,70, abrindo entre gatilho e stop | Entrada em 20,61 e saída em 19,89: −3,49% e −1R, com aviso no trade |
| Saída cancelada | Após D6, um pregão não perde 21,60 e a MME volta a subir | A saída armada é cancelada e a posição segue |

### Estados do setup

&#91;embedded content: estados do 9.1 · 5 estados\]

A tela de acompanhamento usa estes mesmos estados. O stop inicial e o alvo, quando ligado, também valem no estado de saída armada.

## Motor de backtest

O motor percorre os candles em ordem e só usa dados já fechados para decidir, de modo que cada ordem vale a partir do pregão seguinte. O mesmo código atende ao backtest, ao acompanhamento e às duas abas, para que todos sigam regras idênticas.

### Regras de execução

| Situação | Regra |
| --- | --- |
| Ordem de compra stop | Executa no gatilho se a máxima o alcançar; se a abertura já estiver acima, executa na abertura |
| Ordem de venda stop | Executa no preço da ordem se a mínima o alcançar; se a abertura já estiver abaixo, executa na abertura |
| Alvo fixo | Executa no alvo se a máxima o alcançar; se a abertura já estiver acima, executa na abertura |
| Stop e saída armada no mesmo candle | Vale a ordem de preço mais alto, a primeira a ser alcançada em uma queda |
| Entrada e stop no mesmo candle | Sem dados intradiários, a ordem dos eventos é desconhecida; o padrão considera o stop executado e marca o trade |
| Alvo e stop no mesmo candle | O padrão considera o stop executado e marca o trade |
| Fim dos dados com posição aberta | O trade fica aberto, aparece com resultado não realizado e não entra na taxa de acerto |
| Aquecimento | Nenhum sinal é gerado antes de o indicador ter candles suficientes; se faltarem candles, a execução avisa |

### Premissas de simulação

- **Preços:** sinais e simulação usam a série ajustada por proventos e eventos societários. Os preços brutos ficam guardados para consulta quando a fonte os oferece, o que não inclui a aba brapi, pois a documentação da brapi os reserva ao plano Pro.
- **Tick:** em séries ajustadas, os valores deixam de seguir múltiplos exatos de R$ 0,01. O tick é somado ou subtraído sem arredondar o resultado.
- **Custos:** corretagem, emolumentos e slippage são configuráveis por trade. O resultado aparece bruto e líquido.
- **Posição:** há uma posição por combinação de ativo, setup e parâmetros. O resultado é calculado em % e em R, e o valor em reais é opcional.
- **Liquidez:** o MVP assume que toda ordem seria executada. O volume médio aparece como referência, para evitar ativos pouco negociados.

### Acompanhamento e revisão de dados

Um novo provento altera os preços ajustados do passado, então os níveis de um trade de acompanhamento podem mudar depois de registrados. Por isso, cada evento guarda os preços como foram calculados naquele dia e a versão da série usada. O reprocessamento fica visível e nunca apaga o registro original.

Os resultados do backtest são simulações e não representam ordens executadas. A tela deve dizer isso de forma permanente.

## Dashboard e métricas

O dashboard responde a três perguntas: o setup acerta com que frequência, quanto ganha quando acerta e se esse desempenho se mantém ao longo do tempo. Cada aba tem seu próprio dashboard. Todas as métricas usam trades encerrados e resultado líquido, salvo indicação em contrário.

### Definições

| Métrica | Cálculo |
| --- | --- |
| Acerto | Trade com resultado líquido acima de zero |
| Erro | Trade com resultado líquido abaixo de zero |
| Empate | Trade com resultado líquido igual a zero, mostrado à parte |
| Taxa de acerto | Acertos ÷ (acertos + erros) |
| Taxa de erro | Erros ÷ (acertos + erros) |
| Ganho médio | Média do resultado em % dos acertos |
| Perda média | Média do resultado em % dos erros |
| Payoff | Ganho médio ÷ valor absoluto da perda média |
| Fator de lucro | Soma dos ganhos ÷ valor absoluto da soma das perdas |
| Expectativa | Média do resultado em R de todos os trades |
| Retorno acumulado | Resultado composto dos trades em sequência, a partir de uma base de 100 |
| Drawdown máximo | Maior queda percentual da curva de capital em relação ao pico anterior |
| Duração média | Média de pregões entre entrada e saída |
| Tempo exposto | Pregões com posição aberta ÷ pregões do período |

### Composição da tela

| Bloco | Conteúdo | Forma |
| --- | --- | --- |
| Indicadores principais | Trades, taxa de acerto, taxa de erro, payoff, fator de lucro, expectativa, retorno e drawdown | Linha de cartões |
| Evolução do capital | Retorno acumulado comparado ao buy and hold e ao Ibovespa | Gráfico de linhas |
| Queda da curva | Drawdown em cada data | Gráfico de área, abaixo da curva |
| Acertos ao longo do tempo | Taxa de acerto móvel dos últimos 20 trades (configurável) | Gráfico de linha com a taxa geral como referência |
| Sequência de trades | Resultado de cada trade em ordem cronológica | Barras acima e abaixo de zero |
| Sazonalidade | Retorno por mês e ano | Mapa de calor |
| Resultado anual | Trades, taxa de acerto e retorno por ano | Tabela |
| Distribuição | Quantidade de trades por faixa de resultado em R | Histograma |

### Regras de leitura

- **Backtest e acompanhamento separados:** os dois aparecem com cores e filtros próprios. A soma só acontece se você pedir, com aviso visível.
- **Amostra pequena:** com menos de 30 trades, as métricas exibem aviso de baixa confiabilidade. O limite é uma proposta configurável, e o aviso deve aparecer quase sempre na aba brapi.
- **Trades com aviso:** o painel mostra quantos trades dependem da premissa de stop e entrada no mesmo candle.
- **Cores:** verde e vermelho sempre vêm acompanhados de sinal, rótulo ou ícone, para não depender só da cor.

## Arquitetura extensível de setups

Um setup novo é um módulo que declara parâmetros, indicadores e regras. O motor executa as ordens, e as telas se montam a partir dessa declaração.

&#91;embedded content: arquitetura do aplicativo · 8 componentes\]

O setup decide quais ordens quer ter ativas. O motor decide se e a que preço elas são executadas.

### Contrato de setup

```python
class Setup(Protocol):
    id: str                      # "larry_williams_9_1"
    version: str                 # muda quando a regra muda
    name: str
    direction: list[str]         # ["long"] no MVP; "short" fica previsto
    params: type[BaseModel]      # gera o formulário e valida os valores

    def warmup(self, params) -> int: ...
    def indicators(self, candles, params) -> dict[str, Series]: ...
    def on_candle(self, ctx: CandleContext) -> list[Order]: ...
```

`CandleContext` entrega somente candles e indicadores até o pregão atual, além da posição e das ordens ativas. Assim, o setup não consegue olhar o futuro por engano. Cada `Order` indica tipo, preço e motivo, e esse motivo aparece no detalhe do trade.

### Como incluir um setup

1. Criar o módulo do setup, seguindo o contrato.
2. Registrar o setup, para ele aparecer na lista.
3. Escrever os casos de referência com candles e trades esperados.
4. Rodar a suíte comum, que verifica contrato, reprodutibilidade e ausência de olhar o futuro.

Na primeira versão, os setups são escritos em Python. Um editor visual fica fora do MVP. Alterar a regra de um setup exige nova versão, e os resultados antigos continuam ligados à versão que os gerou.

## Modelo de dados

O modelo separa dados de mercado, definições de setup e resultados, para que cada trade possa ser rastreado até a série e os parâmetros que o geraram. A fonte da série define a aba de cada resultado.

| Entidade | Campos principais | Relações |
| --- | --- | --- |
| Ativo | Código, nome, tipo, situação | Tem séries e itens de acompanhamento |
| Série de preços | Provedor, versão, data de obtenção, período, hash do conteúdo | Pertence a um ativo e tem candles |
| Candle | Data, OHLC ajustado, OHLC bruto opcional, OHLC como recebido, fator de rebase, volume, avisos | Pertence a uma série |
| Evento societário | Tipo, data, valor ou fator | Pertence a um ativo |
| Setup | Identificador, nome, versão, esquema de parâmetros | Tem configurações |
| Configuração | Valores dos parâmetros, custos, hash | Pertence a uma versão de setup |
| Execução | Tipo (backtest ou acompanhamento), período, data, situação | Liga uma série a uma configuração e gera sinais e trades |
| Item de acompanhamento | Fonte, data de início, ativo sim ou não, último pregão processado, estado | Liga um ativo a uma configuração |
| Sinal | Data, tipo, gatilho, stop, situação | Pertence a uma execução |
| Trade | Entrada, saída, motivo, resultados bruto e líquido, em % e em R, avisos, origem | Pertence a uma execução e nasce de um sinal |
| Evento do trade | Data, tipo, preço, versão da série | Pertence a um trade e nunca é sobrescrito |

As métricas do dashboard são calculadas a partir dos trades, e não ficam guardadas como dado de origem. Um cache é aceitável, desde que possa ser refeito.

## UX e interface

A interface coloca gráfico, métricas e trades na mesma tela, e o caminho de escolher um ativo até ver o resultado leva no máximo três interações quando os dados já estão em cache.

&#91;embedded content: wireframe da tela de análise\]

A imagem mostra a organização da tela, e não o visual final. Acima de tudo fica a barra "Meus ativos", presente em todas as telas: é nela que se adiciona e se troca o ativo. Escolher um ativo em Dados ou Configurações leva à Análise. As abas separam as duas fontes em Análise, Dashboard, Acompanhamento e Comparar, e os filtros valem para tudo o que aparece abaixo deles.

### Telas

| Tela | Objetivo | Conteúdo principal |
| --- | --- | --- |
| Análise | Avaliar um setup em um ativo | Filtros, indicadores, gráfico, curva de capital e trades |
| Dashboard | Ver a evolução ao longo do tempo | Métricas, curvas, mapa mensal e distribuição |
| Acompanhamento | Saber o que fazer no próximo pregão | Estado de cada item, preços das ordens, eventos recentes |
| Comparar | Escolher ativo, parâmetro ou setup | Até 5 itens lado a lado, dentro da mesma aba |
| Dados | Confiar nos dados | Ativos em cache, fonte, período, avisos, atualização e atalho para analisar |
| Setups | Escolher os setups das análises | Um painel por família, com descrição e origem de cada setup; marcar setup ou família inteira |
| Configurações | Definir padrões | Passo a passo e teste do token da brapi, custos, horário da atualização e backup |

### Princípios visuais

- **Tema:** escuro por padrão, com tema claro disponível.
- **Densidade:** informação densa, com números alinhados e hierarquia clara, para análise em tela grande.
- **Teclado:** `/` abre o campo "Adicionar ativo" em qualquer tela, e as setas navegam entre os trades.
- **Tela menor:** o layout se adapta ao tablet, e o acompanhamento continua legível no celular.
- **Memória:** o último ativo, setup e filtros voltam ao reabrir o aplicativo.

### Estados de tela

| Estado | Comportamento |
| --- | --- |
| Primeiro uso | Sugere adicionar o primeiro ativo, sem exigir cadastro: a aba Yahoo funciona sem token |
| Ativo sem token na aba brapi | Explica o limite e oferece configurar o token ou ver o ativo na aba Yahoo, sem trocar de fonte sozinho |
| Carregando | Mostra o progresso do download e mantém os dados em cache na tela |
| Sem trades | Explica que o setup não gerou trades no período e sugere ampliar as datas |
| Dados com aviso | Mostra quantos candles têm problema e leva à lista deles |
| Provedor indisponível | Informa a falha na aba afetada e a data do último dado, sem trocar de fonte |
| Histórico curto | Na aba brapi, lembra o limite de 3 meses; na aba Yahoo, avisa se houver menos de 10 anos desde 01/01/2010 |
| Início do histórico | A barra de filtros, a tela Dados e Configurações informam que o histórico começa em 01/01/2010; uma data anterior digitada no período fica marcada como inválida, não roda a análise e vira 01/01/2010 ao sair do campo |

## Requisitos não funcionais

Os alvos abaixo são propostas para um computador pessoal comum, com até 100 ativos em cache.

| Área | Requisito | Alvo |
| --- | --- | --- |
| Desempenho | Backtest de um ativo com 10 anos de candles | Até 1 s |
| Desempenho | Abertura do dashboard filtrado | Até 2 s |
| Desempenho | Gráfico com 10 anos de candles | Zoom sem travamento perceptível |
| Confiabilidade | Atualização diária repetida ou interrompida | Sem eventos duplicados, retomando do último pregão processado |
| Confiabilidade | Falha ou limite do provedor | Novas tentativas com espera crescente na mesma fonte, sem perder o cache nem afetar a outra aba |
| Dados | Backup | Um comando ou botão exporta e restaura todo o banco, e um backup automático protege os candles acumulados da brapi |
| Calendário | Dias sem pregão | O calendário da B3 evita falsos alertas de candle faltando |
| Segurança | Tokens de API | Ficam fora do código e nunca aparecem em registros |
| Segurança | Acesso em servidor próprio | Sem login no aplicativo, o acesso exige rede privada ou autenticação na frente dele |
| Acessibilidade | Interface | Navegação por teclado e contraste mínimo de 4,5:1 no texto |
| Idioma | Formato | Português, datas DD/MM/AAAA, valores em reais e decimais com vírgula |
| Limites | Consumo do plano Gratuito da brapi | Fila com 1 requisição por vez e 1 ativo por requisição, dentro de 15.000 requisições por mês |

**Testes obrigatórios:**

- Testes unitários do cálculo da MME e de cada regra do setup.
- Todos os casos numéricos da especificação do 9.1 como testes de referência.
- Teste de ausência de olhar o futuro: incluir candles novos nunca altera trades já encerrados na mesma versão da série.
- Testes dos provedores com respostas gravadas, incluindo erro, limite excedido e dado inválido.
- Testes das métricas com uma lista de trades de resultado conhecido.

## Stack sugerida

A stack combina Python para o cálculo financeiro e React para a interface, e cabe em um único computador. Ela é uma recomendação e pode mudar sem alterar os requisitos.

| Camada | Escolha | Motivo |
| --- | --- | --- |
| Backend | Python, FastAPI | API simples e boa integração com bibliotecas de dados |
| Cálculo | pandas e NumPy | Indicadores e métricas sobre séries temporais |
| Banco | SQLite | Sem servidor separado, com backup de um arquivo |
| Agendamento | APScheduler | Atualização após o pregão dentro do próprio backend |
| Interface | React, TypeScript, Vite | Componentes reutilizáveis e formulários gerados por esquema |
| Gráfico de candles | [TradingView Lightweight Charts](https://github.com/tradingview/lightweight-charts) | Feito para séries financeiras; licença Apache 2.0, que exige atribuição e link para a TradingView |
| Gráficos do dashboard | Apache ECharts | Linhas, barras, histograma e mapa de calor na mesma biblioteca |
| Histórico desde 2010 | [yfinance](https://github.com/ranaroussi/yfinance) | Acesso ao Yahoo Finance, sem custo e sem vínculo oficial com a Yahoo |
| Janela de 3 meses | API da brapi, plano Gratuito | API focada na B3, sem custo |

## Riscos e aspectos legais

O maior risco do produto é confiar em um resultado de backtest distorcido por dados ou premissas, mais do que uma falha técnica. Por isso, as premissas e a origem dos dados ficam sempre visíveis.

| Risco | Impacto | Mitigação |
| --- | --- | --- |
| Histórico da brapi limitado pelo plano | A aba brapi gera poucos trades e pouca confiança estatística | Aviso de amostra pequena e aba Yahoo para a avaliação longa |
| Yahoo sem garantia | O acesso via yfinance pode mudar ou parar, e a brapi gratuita não substitui o histórico longo | Cache local, aviso na aba e camada de provedores para trocar a fonte no futuro |
| Ajustes diferentes entre fontes | Sinais e resultados mudam conforme a fonte | Abas separadas, sem emendar séries nem somar resultados, e fonte registrada em cada execução |
| Preço ajustado misto | A brapi avisa que alguns pontos podem vir sem ajuste ou com `adjustedClose` nulo | Validar a série e alertar antes de usar |
| Viés de seleção | Testar só ativos vencedores ou que sobreviveram infla o resultado | Avisar na comparação e permitir listas definidas antes do teste |
| Excesso de ajuste | Parâmetros bons no passado falham depois | Sem otimização automática no MVP e acompanhamento separado do backtest |
| Candle diário não mostra a ordem dos eventos | Resultado incerto quando entrada e stop caem no mesmo candle | Padrão conservador e contagem dos trades afetados |
| Custos subestimados | Resultado líquido melhor do que o real | Custos configuráveis e exibição do bruto e do líquido |
| Acúmulo da brapi interrompido ou perdido | Pregões fora da janela de 3 meses não podem mais ser obtidos no plano Gratuito | Backup automático, alerta de atualização atrasada e lacunas marcadas na série |
| Rebase incorreto | Saltos falsos de preço geram sinais errados | Guardar os valores recebidos, testar com proventos conhecidos e alertar se os pregões em comum não tiverem um fator único |

### Aspectos legais

Este trecho não é parecer jurídico. Um uso comercial exigiria revisão das licenças.

- **Natureza do produto:** a tela deve informar que os resultados são simulações, não recomendação de investimento, e que resultado passado não garante resultado futuro.
- **Yahoo Finance:** o [yfinance](https://github.com/ranaroussi/yfinance) não é afiliado à Yahoo e informa que a API se destina a uso pessoal. Isso serve ao MVP, mas não a um futuro SaaS. Os [termos de API da Yahoo](https://legal.yahoo.com/us/en/yahoo/terms/product-atos/apiforydn/index.html) também restringem obter receita e uso excessivo. O alcance deles sobre os endpoints usados pelo yfinance não foi confirmado.
- **Cotações da B3:** o [arquivo histórico oficial](https://www.b3.com.br/pt_br/market-data-e-indices/servicos-de-dados/market-data/historico/mercado-a-vista/cotacoes-historicas/) cobre desde 1986, mas não traz ajuste por proventos e proíbe coleta automatizada para qualquer finalidade. O aplicativo não fará essa coleta.
- **TradingView:** a biblioteca de gráficos exige atribuição e um link para a TradingView em local acessível do aplicativo.
- **Redistribuição:** os dados baixados ficam no uso pessoal e não são publicados nem compartilhados pelo aplicativo.

## Roadmap e questões em aberto

O MVP avança em quatro fases, e as duas fontes entram desde a primeira. Datas ainda não foram definidas, pois dependem do tempo disponível para o projeto.

&#91;embedded content: roadmap do MVP · 4 fases, sem datas definidas\]

A ordem garante que as regras estejam testadas antes de a interface exibir qualquer resultado. Depois do MVP, os candidatos naturais são varredura de sinais em uma lista de ativos e registro de trades reais.

### Questões em aberto

- [ ] **Onde o aplicativo vai rodar?** Em um computador pessoal, a atualização diária precisa recuperar os pregões perdidos quando ele estiver desligado. Em um servidor próprio, o acesso precisa de proteção extra.
- [ ] **Quais custos entram por padrão?** Definir valores iniciais de corretagem, emolumentos e slippage, com base na sua corretora.
- [ ] **De onde virá o Ibovespa?** Confirmar a disponibilidade e o ajuste da série em cada fonte, inclusive no plano Gratuito da brapi.

A primeira fase também deve testar o plano Gratuito da brapi com um token real, o que ainda não foi feito. A documentação não deixa claro quais ativos e índices a conta gratuita libera, se todos os preços vêm ajustados nela, nem quantos pregões a janela de 3 meses entrega. Também deve comparar as duas fontes por alguns meses, porque nenhuma página consultada da brapi mostra que seus dados sejam mais precisos que os do Yahoo. A permissão para guardar os dados deve ser confirmada nos Termos de Uso da brapi, que não foi possível abrir nesta consulta.

## Fontes

Consultadas em 6 de novembro de 2026. Limites e preços podem mudar e devem ser reconferidos antes de contratar.

- [Planos da brapi.dev](https://brapi.dev/pricing): limites, histórico e preços por plano.
- [Documentação de ações da brapi.dev](https://brapi.dev/docs/acoes): consulta de preços e `includeRaw`.
- [Histórico de preços da brapi.dev](https://brapi.dev/docs/acoes/historico.md): ajuste de preços e `adjustedClose`.
- [Autenticação da brapi.dev](https://brapi.dev/docs/authentication): os quatro ativos que respondem sem token.
- [yfinance](https://github.com/ranaroussi/yfinance): aviso de uso pessoal e de não afiliação à Yahoo.
- [Termos de API da Yahoo](https://legal.yahoo.com/us/en/yahoo/terms/product-atos/apiforydn/index.html): restrições de uso.
- [Cotações históricas da B3](https://www.b3.com.br/pt_br/market-data-e-indices/servicos-de-dados/market-data/historico/mercado-a-vista/cotacoes-historicas/): período, ausência de ajuste e proibição de coleta automatizada.
- [TradingView Lightweight Charts](https://github.com/tradingview/lightweight-charts): licença e atribuição.
- [Fontes de dados da brapi.dev](https://brapi.dev/faq/fonte-de-dados): origem declarada dos dados, sem comparação de precisão com outros provedores.
