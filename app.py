"""App Streamlit: sugestão de pedido do P0131 com a conta aberta.

Rodar localmente:  streamlit run app.py
O app lê os CSVs gerados por gerar_pedido.py (pasta saidas/), sem ajustar modelo na hora.
"""
from pathlib import Path
import pandas as pd
import streamlit as st
import politica_pedido as pp


def br(valor, casas=1):
    """Formata número no padrão brasileiro (1.234,5)."""
    return f"{valor:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")

PASTA = Path(__file__).parent
# Os CSVs ficam em saidas/; se o upload achatou as pastas, procura na raiz do repositório
SAIDAS = PASTA / "saidas" if (PASTA / "saidas" / "pedido_P0131.csv").exists() else PASTA

st.set_page_config(page_title="Pedido P0131", layout="wide")


@st.cache_data
def carregar_saidas():
    pedido = pd.read_csv(SAIDAS / "pedido_P0131.csv").iloc[0]
    diario = pd.read_csv(SAIDAS / "previsao_diaria_P0131.csv", parse_dates=["data"])
    erros = pd.read_csv(SAIDAS / "erros_backtest_P0131.csv")
    return pedido, diario, erros


pedido_base, diario, erros = carregar_saidas()

st.title("Sugestão de pedido: P0131")
st.caption(f"Modelo: {pedido_base['modelo']} · treino até {pedido_base['data_corte']} · "
           f"cobertura de {pedido_base['inicio_cobertura']} a {pedido_base['fim_cobertura']} (28 dias = lead time 14 + revisão 14)")

# Entradas do comprador
with st.sidebar:
    st.header("Entradas")
    estoque_cd = st.number_input("Estoque disponível no CD (unidades)", min_value=0.0,
                                 value=float(pedido_base["estoque_cd"]), step=100.0)
    nivel_servico = st.slider("Nível de serviço", 0.80, 0.99, float(pedido_base["nivel_servico"]), 0.001,
                              format="%.3f")
    st.caption("Padrão 0,938 = Cu / (Cu + Co), com falta a 30% e sobra a 2% do preço.")

# Conta do pedido (recalculada com as entradas)
conta = pp.politica_pedido(pedido_base["demanda_prevista"], erros["erro_total_un"], estoque_cd, nivel_servico)

coluna1, coluna2, coluna3 = st.columns(3)
coluna1.metric("Pedido sugerido", f"{br(conta['pedido'], 0)} un")
coluna2.metric("Demanda prevista (28 dias)", f"{br(conta['demanda_prevista'], 0)} un")
coluna3.metric("Estoque de segurança", f"{br(conta['estoque_seguranca'], 0)} un")

st.subheader("Conta aberta")
tabela_conta = pd.DataFrame({
    "Componente": ["Demanda prevista (28 dias)", f"+ Estoque de segurança ({nivel_servico:.1%})",
                   "= Necessidade bruta", "− Estoque disponível no CD", "= PEDIDO"],
    "Unidades": [conta["demanda_prevista"], conta["estoque_seguranca"], conta["necessidade_bruta"],
                 conta["estoque_cd"], conta["pedido"]],
})
st.dataframe(tabela_conta.style.format({"Unidades": br}), hide_index=True, width="stretch")

# Comparação com o realizado (quando os 28 dias existem na base)
if pd.notna(pedido_base["vendido_real"]):
    vendido = float(pedido_base["vendido_real"])
    disponivel = conta["estoque_cd"] + conta["pedido"]
    saldo = disponivel - vendido
    preco = float(pedido_base["preco_medio"])
    custo = max(saldo, 0) * pp.CARREGO * preco + max(-saldo, 0) * pp.MARGEM_PERDIDA * preco
    st.subheader("Comparação com o que foi vendido")
    comparacao = pd.DataFrame({
        "Item": ["Vendido nos 28 dias", "Previsão − vendido", "Disponível (CD + pedido)",
                 "Sobra (+) / falta (−)", "Custo do erro no período (R$)"],
        "Valor": [vendido, conta["demanda_prevista"] - vendido, disponivel, saldo, custo],
    })
    st.dataframe(comparacao.style.format({"Valor": br}), hide_index=True, width="stretch")

st.subheader("Previsão diária vs vendido")
grafico = diario.set_index("data")[["previsao", "vendido_real"]].rename(
    columns={"previsao": "Previsão SARIMAX", "vendido_real": "Vendido"})
st.line_chart(grafico, y_label="unidades por dia")

with st.expander("Erros do backtest usados no estoque de segurança (12 origens)"):
    st.dataframe(erros, hide_index=True, width="stretch")
    st.caption("erro_total_un = realizado − previsto no total de 28 dias (positivo = faltou produto). "
               "O estoque de segurança é o quantil desses erros no nível de serviço escolhido.")

st.subheader("Downloads")
pedido_atual = pedido_base.copy()
for chave, valor in conta.items():
    pedido_atual[chave] = valor
pedido_atual["nivel_servico"] = nivel_servico
coluna_a, coluna_b, coluna_c = st.columns(3)
coluna_a.download_button("Pedido (CSV)", pd.DataFrame([pedido_atual]).to_csv(index=False),
                         "pedido_P0131.csv", "text/csv")
coluna_b.download_button("Previsão diária (CSV)", diario.to_csv(index=False),
                         "previsao_diaria_P0131.csv", "text/csv")
notebook = PASTA / "projeto_P0131.ipynb"
if notebook.exists():
    coluna_c.download_button("Notebook do projeto (.ipynb)", notebook.read_bytes(),
                             "projeto_P0131.ipynb", "application/x-ipynb+json")
