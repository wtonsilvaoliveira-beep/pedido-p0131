# Sugestão de pedido de compra: P0131

Projeto CRISP-DM (fases 1 a 6) para sugerir o pedido de compra de um produto de varejo, com 144 lojas e 1 CD.

**Pedido = demanda prevista (28 dias) + estoque de segurança − estoque disponível no CD**

- Modelo: SARIMAX (2,1,2)(1,1,1,7), com a promoção (`pct_lojas_promo`) como variável externa.
- Horizonte: 28 dias (lead time de 14 dias + ciclo de revisão de 14 dias).
- Estoque de segurança: quantil 93,8% dos erros do backtest (12 origens). Faltar custa 30% do preço e sobrar custa 2%, por isso o nível ótimo é 0,9375.

## Arquivos
| Arquivo | O que é |
|---|---|
| `projeto_P0131.ipynb` | Notebook com as fases 1 a 6, já executado com as saídas reais |
| `politica_pedido.py` | Funções usadas por todos (previsão, backtest, estoque de segurança e pedido) |
| `gerar_pedido.py` | Deploy em lote: gera o pedido em CSV |
| `app.py` | Deploy em Streamlit: mostra a conta aberta e permite mudar o estoque do CD e o nível de serviço |
| `dados/demanda.csv` | Base de dados original |
| `saidas/*.csv` | Pedido, previsão diária e erros do backtest (lidos pelo app) |

## Como rodar
```bash
pip install -r requirements.txt
python gerar_pedido.py --estoque-cd 3000   # gera os CSVs em saidas/ (cerca de 1 minuto)
streamlit run app.py                       # abre o app no navegador
```
Parâmetros do script: `--data-corte` (último dia conhecido, padrão 2019-10-03), `--estoque-cd` e `--nivel-servico`.

## Resultado no teste (04/10 a 31/10/2019)
| | Unidades |
|---|---:|
| Demanda prevista | 8.267,0 |
| + Estoque de segurança | 779,1 |
| − Estoque no CD (premissa) | 3.000,0 |
| **= Pedido** | **6.046,1** |
| Vendido de fato | 8.158,0 |

## Limitações
- O resultado foi validado só no P0131.
- A base registra venda, não demanda: os dias de ruptura parecem ter sido apagados.
- O estoque do CD não está na base, por isso as 3.000 unidades são uma premissa.
- O SARIMAX com ajuste padrão não converge, e o resultado é sensível ao otimizador.
- O estoque de segurança usa as mesmas 12 janelas do backtest, inclusive a janela de teste, então o resultado é otimista.
