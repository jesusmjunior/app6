import streamlit as st
import pandas as pd
from datetime import datetime

@st.cache_data
def carregar_dados():
    items_url = 'https://docs.google.com/spreadsheets/d/e/2PACX-1vSeWsxmLFzuWsa2oggpQb6p5SFapxXHcWaIl0Jjf2wAezvMgAV9XCc1r7fSSzRWTCgjk9eqREgWlrzp/pub?output=csv&gid=1011017078'
    inventory_url = 'https://docs.google.com/spreadsheets/d/e/2PACX-1vSeWsxmLFzuWsa2oggpQb6p5SFapxXHcWaIl0Jjf2wAezvMgAV9XCc1r7fSSzRWTCgjk9eqREgWlrzp/pub?output=csv&gid=1710164548'

    items_df = pd.read_csv(items_url)
    inventory_df = pd.read_csv(inventory_url)
    inventory_df['DateTime'] = pd.to_datetime(inventory_df['DateTime'], errors='coerce', dayfirst=True)
    return items_df, inventory_df

def preparar_dados(items_df, inventory_df):
    items_df['Item ID'] = items_df['Item ID'].str.strip()
    inventory_df['Item ID'] = inventory_df['Item ID'].str.strip()
    return items_df, inventory_df

def calcular_estoque(items_df, inventory_df, data_pedido, estoque_seguranca, dias_media):
    inicio_periodo = inventory_df['DateTime'].min()
    fim_periodo = inventory_df['DateTime'].max()
    periodo_pre_d = inventory_df.copy()

    entradas = periodo_pre_d[periodo_pre_d['Amount'] > 0]
    saidas = periodo_pre_d[periodo_pre_d['Amount'] < 0]
    estoque_atual = periodo_pre_d.groupby('Item ID')['Amount'].sum().reset_index()
    estoque_atual.columns = ['Item ID', 'Estoque Atual']

    resultado = estoque_atual.copy()
    nome_map = dict(zip(items_df['Item ID'].drop_duplicates(), items_df['Name'].drop_duplicates()))
    desc_map = dict(zip(items_df['Item ID'].drop_duplicates(), items_df['Description'].drop_duplicates()))
    resultado['Nome Produto'] = resultado['Item ID'].map(nome_map)
    resultado['Descrição'] = resultado['Item ID'].map(desc_map)

    pontos_fixos = {
        "4c44f391": 8, "cdb7c49d": 10, "a31fa3e6": 5, "7185e46c": 12,
        "4f0b6e6d": 9, "874f4c45": 6, "03bcd290": 10, "22355245": 6,
        "3809b5ae": 10, "f539ee95": 4, "4551c5df": 8, "cadc39ff": 10,
        "e38864a9": 10, "c125aed6": 13, "faa39ab7": 8, "a500234e": 7,
        "732098bc": 6, "1e85205e": 10, "72e50b91": 10, "f43363c9": 11,
        "e9499711": 7, "bb079e20": 8, "887becc9": 8, "767c19cf": 6,
        "42a8f594": 7, "412e20d0": 5, "77ab23ba": 7, "a42ac7a3": 9,
        "3eda129c": 6, "e98c4af8": 7, "0f1c83e8": 6, "da0a9126": 8,
        "e717180d": 10, "4b447dff": 11, "5a866829": 13, "b10220c8": 6,
        "2e0c6d14": 13, "5a6a0e8c": 7
    }

    resultado['Ponto de Pedido'] = resultado['Item ID'].map(pontos_fixos).fillna(10).astype(int)

    for dias in [7, 15, 30, 45]:
        resultado[f'Necessidade {dias} dias'] = resultado['Ponto de Pedido']

    resultado['Estoque Mínimo'] = resultado['Ponto de Pedido'] * (estoque_seguranca / 100)

    def definir_status(row):
        if (row['Estoque Atual'] < row['Ponto de Pedido']):
            return 'Vermelho - Alerta Crítico'
        elif (row['Estoque Atual'] < row['Ponto de Pedido'] + 5):
            return 'Amarelo - Alerta Médio'
        else:
            return 'Verde - OK'

    resultado['Status'] = resultado.apply(definir_status, axis=1)
    return resultado, entradas, saidas, periodo_pre_d

def gerar_pedido(resultado, periodo):
    pedido = resultado.copy()
    pedido['Qtd a Pedir'] = (resultado['Ponto de Pedido'] - resultado['Estoque Atual']).apply(lambda x: max(0, round(x)))
    return pedido

st.set_page_config(page_title="📦 Dashboard Estoque", layout="wide")
st.title("📦 Dashboard de Controle de Estoque - Dados Reais")

items_df, inventory_df = carregar_dados()
items_df, inventory_df = preparar_dados(items_df, inventory_df)

st.sidebar.header("Parâmetros")
data_pedido = st.sidebar.date_input("Data do Próximo Pedido:", datetime.today())
periodo = st.sidebar.selectbox("Período para Pedido:", [7, 15, 30, 45])
estoque_seguranca = st.sidebar.slider("% Estoque de Segurança:", 10, 100, 50, step=10)
dias_media = st.sidebar.slider("Dias para Média de Consumo:", 15, 120, 60, step=15)

resultado, entradas, saidas, inventario = calcular_estoque(items_df, inventory_df, pd.to_datetime(data_pedido), estoque_seguranca, dias_media)

st.subheader("📋 Histórico de Movimentação")
st.dataframe(inventario[['Item ID', 'DateTime', 'Amount']])

col1, col2 = st.columns(2)
with col1:
    st.write("### ➕ Entradas de Estoque")
    st.dataframe(entradas[['Item ID', 'DateTime', 'Amount']])
with col2:
    st.write("### ➖ Saídas de Estoque")
    st.dataframe(saidas[['Item ID', 'DateTime', 'Amount']])

st.subheader(f"📅 Status dos Produtos para {periodo} dias")
status_tabs = st.tabs(["🔴 Crítico", "🟡 Médio", "🟢 OK"])

for idx, status in enumerate(['Vermelho - Alerta Crítico', 'Amarelo - Alerta Médio', 'Verde - OK']):
    with status_tabs[idx]:
        st.dataframe(resultado[resultado['Status'] == status][['Item ID', 'Nome Produto', 'Descrição', 'Estoque Atual', 'Ponto de Pedido', 'Estoque Mínimo', 'Status']])

st.subheader("📄 Pedido de Material")
pedido = gerar_pedido(resultado, periodo)
st.dataframe(pedido[['Item ID', 'Nome Produto', 'Descrição', 'Estoque Atual', 'Ponto de Pedido', 'Qtd a Pedir']])

csv = pedido.to_csv(index=False).encode('utf-8')
st.download_button(
    label=f"📥 Download Pedido de Material para {periodo} dias",
    data=csv,
    file_name=f'Pedido_Material_{periodo}_dias.csv',
    mime='text/csv'
)
