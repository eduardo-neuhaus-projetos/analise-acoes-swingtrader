# CLAUDE.md: Swing B3

Aplicativo pessoal de backtest e acompanhamento simulado de swing trade na B3. Requisitos no PRD (`PRD aplicativo de swing trade para a B3.md`); escopo atual e como rodar no `README.md`. `exemplo.zip` é referência de formato de outro projeto, com outra stack: não siga as regras dele (em especial o fallback entre fontes, que o PRD proíbe).

Código, identificadores, comentários e mensagens em português (pt-BR).

## Comandos

```powershell
# backend/ (venv própria em backend/.venv)
.venv\Scripts\python -m pytest
.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# frontend/
npm run dev      # porta 5173; proxy de /api para a 8000 (SWING_B3_API muda o destino)
npm run build    # inclui tsc --noEmit
```

## Arquitetura

- `backend/app/motor/`: `motor.py` é o único executor de ordens, usado por backtest e acompanhamento. `metricas.py` calcula tudo a partir da lista de trades.
- `backend/app/setups/`: setups declaram parâmetros (pydantic), indicadores e ordens desejadas. `comum.py` traz a base `SetupCompra`, com filtros globais, aquecimento e saídas comuns. `registro.py` é o único ponto de inclusão, e as telas não têm nome de setup fixo. Estado de um setup entre candles fica em `ctx.memoria`, nunca na instância, que é compartilhada. As regras estão em `SETUPS_SWING_TRADE.md`, e as adaptações, no PRD, em "Catálogo de setups".
- `backend/app/provedores/`: uma classe por fonte.
- `backend/app/servicos/`: `dados.py` (importação, rebase, validação), `analise.py`, `acompanhamento.py`. As rotas em `api/rotas.py` são finas.
- `frontend/src/App.tsx` guarda a seleção, a lista Meus ativos, os setups ocultos e os resultados por fonte. Setups ocultos (escolhidos na tela Setups, um painel por `familia`) só somem do seletor: a API continua aceitando todos, porque o Acompanhamento e o Comparar podem usá-los. A lista fica no navegador (`lib/memoria.ts`) e tirar um ativo dela nunca apaga candles. `lib/opcoesGraficos.ts` tem as opções do ECharts, e `componentes/GraficoCandles.tsx` usa o Lightweight Charts.

## Regras que não podem quebrar

- **Fontes nunca se misturam:** sem fonte de reserva, sem soma entre abas. Falha de uma fonte só aparece na aba dela e mantém o cache.
- **Histórico desde 01/01/2010** (`calendario.INICIO_HISTORICO`): nada anterior é baixado, guardado, simulado ou aceito como data de análise, comparação ou acompanhamento. O backend apaga ao iniciar candles anteriores que versões antigas guardaram. Os testes que criam candles precisam usar datas a partir de 2010.
- **Sem olhar o futuro:** o setup só recebe dados até o candle atual, e a ordem vale a partir do pregão seguinte. A exceção são as ordens a fechamento, que executam no preço já conhecido do próprio candle. O candle do dia em formação é descartado até 18h30 (`calendario.candle_em_formacao`).
- **Janela da brapi:** nenhuma tela mostra candle, trade ou métrica com mais de 3 meses, exceto trade ainda aberto. Os candles antigos ficam guardados para a MME e nunca são apagados, pois não dá para baixar de novo.
- **Preços:** a simulação usa OHLC ajustado (`fechamento_ajustado / fechamento` aplicado ao candle), sem arredondar o tick. Os valores recebidos ficam em `recebido_*`.
- **Eventos de acompanhamento nunca são sobrescritos:** `INSERT OR IGNORE` é proposital.
- **Token da brapi:** vai no cabeçalho, nunca na URL; fica fora do banco; nunca volta pela API.
- **Regra de setup mudou:** aumente `versao`.
- A tela mostra sempre que os resultados são simulações, e a atribuição à TradingView fica no rodapé.

## Formato

Datas DD/MM/AAAA, decimal com vírgula, valores em reais, inclusive em texto gerado no backend (`motor.preco_br`) e no CSV. Verde e vermelho sempre vêm com sinal ou rótulo. Use as funções de `lib/formatos.ts` e os tokens CSS de `estilos.css`; cores novas de gráfico passam por `lib/cores.ts`.

## Armadilhas do ambiente

- Windows em português: `netstat` escreve `ESCUTANDO` em vez de `LISTENING`.
- O `zoneinfo` precisa do pacote tzdata no Windows; por isso o fuso da B3 é um deslocamento fixo de -3h (o Brasil não tem horário de verão desde 2019).
- O `iniciar.bat` encerra os servidores anteriores deste projeto (`servidores.ps1`): sem isso, um backend antigo segura a porta 8000 e o app abre com o código velho. Quem sobe pelos terminais precisa reiniciar o backend depois de mudar código Python.
- A variável `TRADER_DB` troca o banco. Use-a em testes manuais para não mexer em `backend/data/`.
