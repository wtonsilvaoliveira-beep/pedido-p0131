"""Funções da política de pedido do P0131.

Usadas pelo script (gerar_pedido.py), pelo app (app.py) e pelo notebook.
Pedido = demanda prevista (28 dias) + estoque de segurança - estoque disponível no CD.
"""
import warnings
import numpy as np
import pandas as pd

# Parâmetros fixados nas Fases 1 a 5
PRODUTO = "P0131"
H = 28                    # horizonte: lead time 14 dias + ciclo de revisão 14 dias
N_ORIGENS = 12            # origens do backtest
PASSO_ORIGENS = 14        # distância entre origens (dias)
NIVEL_SERVICO = 0.938     # fractil crítico Cu / (Cu + Co) = 0,9375
MARGEM_PERDIDA = 0.30     # custo de faltar = 30% do preço
CARREGO = 0.02            # custo de sobrar = 2% do preço por período
ESTOQUE_CD_PADRAO = 3000  # premissa: estoque do CD não está na base


def carregar_dados(caminho_csv, produto=PRODUTO):
    """Lê demanda.csv e devolve a série diária do produto (índice diário contínuo)."""
    demanda = pd.read_csv(caminho_csv, parse_dates=["data"])
    dados = (demanda[demanda["produto"] == produto]
             .drop(columns="produto").set_index("data").sort_index().asfreq("D"))
    return dados


def prever_sarimax(venda_treino, promo_treino, promo_futuro, horizonte=H):
    """SARIMAX (2,1,2)(1,1,1,7) com promoção como variável externa, ajuste padrão (Fase 4).
    Devolve a previsão diária (cortada em zero) e se o otimizador convergiu."""
    from statsmodels.tsa.statespace.sarimax import SARIMAX
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ajuste = SARIMAX(venda_treino, exog=promo_treino,
                         order=(2, 1, 2), seasonal_order=(1, 1, 1, 7)).fit(disp=False)
    previsao = ajuste.forecast(horizonte, exog=promo_futuro).clip(lower=0)
    return previsao, bool(ajuste.mle_retvals["converged"])


def origens_backtest(dados, horizonte=H, n_origens=N_ORIGENS, passo=PASSO_ORIGENS):
    """Origens da Fase 5: a última é a última data menos H; as demais recuam de 14 em 14 dias."""
    ultima_origem = dados.index.max() - pd.Timedelta(days=horizonte)
    return [ultima_origem - pd.Timedelta(days=passo * k) for k in range(n_origens)][::-1]


def backtest_sarimax(dados, horizonte=H):
    """Erro do total de 28 dias (realizado - previsto) do SARIMAX em cada origem."""
    venda, promo = dados["unidades"], dados[["pct_lojas_promo"]]
    linhas = []
    for origem in origens_backtest(dados, horizonte):
        treino = venda.loc[:origem]
        futuro = venda.loc[origem + pd.Timedelta(days=1):].iloc[:horizonte]
        previsao, convergiu = prever_sarimax(treino, promo.loc[treino.index], promo.loc[futuro.index], horizonte)
        linhas.append({"origem": origem.date(), "total_previsto": float(previsao.sum()),
                       "total_real": float(futuro.sum()),
                       "erro_total_un": float(futuro.sum() - previsao.sum()),  # positivo = faltou
                       "convergiu": convergiu})
    return pd.DataFrame(linhas)


def estoque_seguranca(erros, nivel_servico=NIVEL_SERVICO):
    """Quantil empírico dos erros (realizado - previsto) no nível de serviço pedido."""
    return float(np.quantile(np.asarray(erros, dtype=float), nivel_servico))


def politica_pedido(demanda_prevista, erros, estoque_disponivel, nivel_servico=NIVEL_SERVICO):
    """Devolve os componentes separados do pedido (nunca negativo)."""
    es = estoque_seguranca(erros, nivel_servico)
    necessidade = demanda_prevista + es
    return {"demanda_prevista": float(demanda_prevista), "estoque_seguranca": es,
            "necessidade_bruta": necessidade, "estoque_cd": float(estoque_disponivel),
            "pedido": max(0.0, necessidade - estoque_disponivel)}
