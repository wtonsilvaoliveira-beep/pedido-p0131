"""Gera o pedido do P0131 em CSV (deploy em lote).

Uso:
    python gerar_pedido.py                       # corte 2019-10-03, estoque no CD 3000
    python gerar_pedido.py --estoque-cd 2500
    python gerar_pedido.py --data-corte 2019-10-31   # uso real: prevê os 28 dias após a última data
"""
import argparse
from pathlib import Path
import pandas as pd
import politica_pedido as pp

PASTA = Path(__file__).parent
parser = argparse.ArgumentParser()
parser.add_argument("--dados", default=PASTA / "dados" / "demanda.csv")
parser.add_argument("--data-corte", default="2019-10-03", help="último dia conhecido (fim do treino)")
parser.add_argument("--estoque-cd", type=float, default=pp.ESTOQUE_CD_PADRAO)
parser.add_argument("--nivel-servico", type=float, default=pp.NIVEL_SERVICO)
parser.add_argument("--saida", default=PASTA / "saidas")
argumentos = parser.parse_args()
pasta_saida = Path(argumentos.saida); pasta_saida.mkdir(exist_ok=True)

# 1. Dados do produto
dados = pp.carregar_dados(argumentos.dados)
corte = pd.Timestamp(argumentos.data_corte)
dias_futuros = pd.date_range(corte + pd.Timedelta(days=1), periods=pp.H, freq="D")
treino = dados.loc[:corte]
print(f"Produto {pp.PRODUTO} | treino {treino.index.min().date()} a {corte.date()} ({len(treino)} dias)")
print(f"Cobertura do pedido: {dias_futuros[0].date()} a {dias_futuros[-1].date()}")

# 2. Promoção planejada dos próximos 28 dias (calendário de promoções; na base, a coluna pct_lojas_promo)
promo_futuro = dados["pct_lojas_promo"].reindex(dias_futuros).fillna(0).to_frame()

# 3. Erros do backtest (12 origens da Fase 5) para o estoque de segurança
print("Rodando backtest (12 ajustes do SARIMAX)...", flush=True)
erros = pp.backtest_sarimax(dados)
erros.to_csv(pasta_saida / "erros_backtest_P0131.csv", index=False)

# 4. Previsão e conta do pedido
previsao, convergiu = pp.prever_sarimax(treino["unidades"], treino[["pct_lojas_promo"]], promo_futuro)
previsao.index = dias_futuros
conta = pp.politica_pedido(previsao.sum(), erros["erro_total_un"], argumentos.estoque_cd, argumentos.nivel_servico)

# 5. Comparação com o vendido, quando os 28 dias já existem na base
vendido_diario = dados["unidades"].reindex(dias_futuros)
tem_realizado = vendido_diario.notna().all()
vendido = float(vendido_diario.sum()) if tem_realizado else None

pedido = {"produto": pp.PRODUTO, "data_corte": corte.date(),
          "inicio_cobertura": dias_futuros[0].date(), "fim_cobertura": dias_futuros[-1].date(),
          "nivel_servico": argumentos.nivel_servico, **conta,
          "preco_medio": float(dados["preco_medio"].mean()),
          "modelo": "SARIMAX (2,1,2)(1,1,1,7) + promo", "modelo_convergiu": convergiu,
          "vendido_real": vendido,
          "sobra_falta_un": (conta["estoque_cd"] + conta["pedido"] - vendido) if tem_realizado else None}
pd.DataFrame([pedido]).to_csv(pasta_saida / "pedido_P0131.csv", index=False)
pd.DataFrame({"data": dias_futuros.date, "previsao": previsao.values,
              "pct_lojas_promo": promo_futuro["pct_lojas_promo"].values,
              "vendido_real": vendido_diario.values}).to_csv(pasta_saida / "previsao_diaria_P0131.csv", index=False)

print("\n=== Conta do pedido ===")
print(f"  Demanda prevista (28 dias)     {conta['demanda_prevista']:>10,.1f}")
print(f"+ Estoque de segurança ({argumentos.nivel_servico:.1%})  {conta['estoque_seguranca']:>10,.1f}")
print(f"= Necessidade bruta              {conta['necessidade_bruta']:>10,.1f}")
print(f"- Estoque disponível no CD       {conta['estoque_cd']:>10,.1f}")
print(f"= PEDIDO                         {conta['pedido']:>10,.1f}")
if tem_realizado:
    print(f"\nVendido nos 28 dias             {vendido:>10,.1f}")
    print(f"Sobra (+) / falta (-)           {pedido['sobra_falta_un']:>+10,.1f}")
print(f"\nArquivos gravados em {pasta_saida}/: pedido_P0131.csv, previsao_diaria_P0131.csv, erros_backtest_P0131.csv")
