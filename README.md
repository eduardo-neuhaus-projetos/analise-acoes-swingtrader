# Swing B3

Aplicativo web pessoal que transforma candles diários da B3 em sinais, trades simulados e um dashboard. As análises ficam em duas abas que nunca se misturam: **brapi** (janela de 3 meses) e **Yahoo** (histórico desde 01/01/2010). São 21 setups, descritos em [`SETUPS_SWING_TRADE.md`](SETUPS_SWING_TRADE.md).

Requisitos e regras: [`PRD aplicativo de swing trade para a B3.md`](PRD%20aplicativo%20de%20swing%20trade%20para%20a%20B3.md).

Resultados são simulações, não representam ordens executadas e não são recomendação de investimento.

## Como rodar

Precisa de Python 3.11+ e Node 20+. No Windows, dê dois cliques em `iniciar.bat`: ele instala o que faltar, sobe backend e frontend e abre o navegador.

Ou manualmente, em dois terminais:

```powershell
# Terminal 1
cd backend
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# Terminal 2
cd frontend
npm install
npm run dev
```

Abra <http://127.0.0.1:5173>. A documentação da API fica em <http://127.0.0.1:8000/docs>.

## Roteiro de teste

1. Na barra **Meus ativos**, no alto de todas as telas, clique em **Adicionar ativo** e escolha PETR4 na lista ou digite o código ou o nome (o atalho é `/`). As duas fontes baixam os dados, cada uma por conta própria.
2. Clique em um trade na tabela: o gráfico centraliza nele e o painel explica a regra de cada evento. As setas ↑ ↓ navegam entre os trades.
3. Troque entre as abas brapi e Yahoo: ativo, setup e parâmetros continuam, e os resultados são de cada fonte.
4. Mude os parâmetros (por exemplo, alvo de 2R) e os filtros de data.
5. Na tela **Setups**, escolha quais setups aparecem nas análises, por setup ou por família. O link "Editar lista", ao lado do seletor de setup, leva até lá.
6. Abra o Dashboard, depois use "Acompanhar" na Análise e "Atualizar agora" em Acompanhamento.
7. Adicione WEGE3 e alterne entre ele e PETR4 com um clique na barra. Sem token, só a aba brapi pede o token, e a aba Yahoo funciona normalmente.

**Token da brapi:** sem token, a brapi só responde para PETR4, MGLU3, VALE3 e ITUB4. Para outros ativos nessa aba, crie uma conta gratuita em [brapi.dev](https://brapi.dev/) e guarde o token em Configurações, que o testa na hora, ou use a variável de ambiente `BRAPI_TOKEN`. A conta gratuita continua limitada a 3 meses. A aba Yahoo não precisa de token. O caminho com um token real ainda não foi testado.

## O que esta versão entrega

| Área | Situação |
| --- | --- |
| Importação das duas fontes, cache em SQLite, atualização incremental | Pronto |
| Histórico fixo desde 01/01/2010: nada anterior é baixado, guardado ou simulado, e o calendário trava datas anteriores | Pronto |
| Acúmulo da brapi com rebase por provento e marcação de lacunas | Pronto, testado com respostas simuladas; um provento real ainda não passou por ele |
| Validação de candles e calendário da B3 | Pronto |
| Motor e Larry Williams 9.1, com todos os casos do PRD como teste | Pronto |
| Catálogo de 21 setups, com casos numéricos de cada um e opções em lista no formulário | Pronto |
| Registro de setups, com formulário gerado pelo esquema | Pronto |
| Análise, Dashboard, Comparar, Dados, Configurações | Pronto |
| Acompanhamento: lista, estados, ordens, histórico sem duplicar | Pronto, com atualização **manual** |
| Barra Meus ativos em todas as telas: adicionar, trocar com um clique, tirar da lista | Pronto |
| Tema escuro e claro, teclado, memória da última seleção, tablet e celular | Pronto |

### Ainda não incluído

- Atualização automática após o pregão (APScheduler, RF-31) e recuperação de pregões perdidos.
- Backup e restauração do banco. **Até lá, copie `backend/data/` de vez em quando:** os candles acumulados da brapi não podem ser baixados de novo.
- Comparação entre provedores (RF-08, desejável).
- Versões de venda dos setups, pirâmide e saída parcial. As adaptações à especificação estão no PRD, em "Catálogo de setups".
- Filtro por origem do trade no dashboard (RF-42): os trades de acompanhamento ainda não entram no dashboard.
- Edição de item de acompanhamento: para mudar parâmetros, remova e crie outro. O histórico fica guardado.

## Testes

```powershell
cd backend
.venv\Scripts\python -m pytest
```

Os testes não usam rede: os provedores rodam com respostas gravadas ou simuladas.

## Para incluir um setup

1. Crie a classe em `backend/app/setups/`, herdando de `SetupCompra` (`comum.py`), que já traz filtros globais e aquecimento.
2. Registre em `SETUPS`, no arquivo `registro.py`. Ele já aparece na API e nas telas.
3. Escreva os casos de referência. A suíte `tests/test_contrato_setups.py` já cobre contrato, reprodutibilidade e ausência de olhar o futuro de todo setup registrado.

Ao mudar a regra de um setup, aumente `versao`: os resultados antigos seguem ligados à versão que os gerou.

## Licenças e dados

Candles com [TradingView Lightweight Charts](https://github.com/tradingview/lightweight-charts) (Apache 2.0, com atribuição no rodapé) e painéis com Apache ECharts. O yfinance não tem vínculo com a Yahoo e se destina a uso pessoal. Os dados baixados ficam neste computador.

O aplicativo não tem login: mantenha-o em `127.0.0.1` ou em rede privada.
