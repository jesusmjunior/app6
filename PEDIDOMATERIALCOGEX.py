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
    inicio_periodo = pd.to_datetime('2019-11-01')
    fim_periodo = pd.to_datetime('2020-02-02')
    periodo_pre_d = inventory_df[(inventory_df['DateTime'] >= inicio_periodo) &
                                 (inventory_df['DateTime'] <= fim_periodo) &
                                 (inventory_df['DateTime'].dt.strftime('%Y-%m-%d') != '2020-02-12')].copy()

    entradas = periodo_pre_d[periodo_pre_d['Amount'] > 0]
    saidas = periodo_pre_d[periodo_pre_d['Amount'] < 0]
    estoque_atual = periodo_pre_d.groupby('Item ID')['Amount'].sum().reset_index()
    estoque_atual.columns = ['Item ID', 'Estoque Atual']

    ultimos_dias = inventory_df[inventory_df['DateTime'] >= (inventory_df['DateTime'].max() - pd.Timedelta(days=dias_media))]
    saidas_futuro = ultimos_dias[ultimos_dias['Amount'] < 0].copy()
    saidas_futuro['Amount'] = saidas_futuro['Amount'].abs()
    dias_totais = dias_media or 1
    consumo_medio = saidas_futuro.groupby('Item ID')['Amount'].sum() / dias_totais
    consumo_medio = consumo_medio.reset_index()
    consumo_medio.columns = ['Item ID', 'Consumo Médio Diário']

    resultado = pd.merge(estoque_atual, consumo_medio, on='Item ID', how='left')
    resultado['Consumo Médio Diário'].fillna(0, inplace=True)
    nome_map = dict(zip(items_df['Item ID'].drop_duplicates(), items_df['Name'].drop_duplicates()))
    desc_map = dict(zip(items_df['Item ID'].drop_duplicates(), items_df['Description'].drop_duplicates()))
    resultado['Nome Produto'] = resultado['Item ID'].map(nome_map)
    resultado['Descrição'] = resultado['Item ID'].map(desc_map)

    def calcular_pp_fixo(item_id, cmd):
        regras = {
            "4c44f391": lambda cmd: (cmd * 10) + 2,
            "cdb7c49d": lambda cmd: (cmd * 8) + 3,
            "a31fa3e6": lambda cmd: (cmd * 8) + 2,
            "7185e46c": lambda cmd: (cmd * 12) + 1,
            "4f0b6e6d": lambda cmd: (cmd * 6) + 2,
            "874f4c45": lambda cmd: (cmd * 10) + 1,
            "03bcd290": lambda cmd: (cmd * 9) + 2,
            "22355245": lambda cmd: (cmd * 10) + 3,
            "3809b5ae": lambda cmd: (cmd * 11) + 1,
            "f539ee95": lambda cmd: (cmd * 12) + 2,
            "4551c5df": lambda cmd: (cmd * 9) + 1,
            "cadc39ff": lambda cmd: (cmd * 10) + 2,
            "e38864a9": lambda cmd: (cmd * 14) + 4,
            "c125aed6": lambda cmd: (cmd * 13) + 4,
            "faa39ab7": lambda cmd: (cmd * 7) + 2,
            "a500234e": lambda cmd: (cmd * 7) + 2,
            "732098bc": lambda cmd: (cmd * 12) + 1,
            "1e85205e": lambda cmd: (cmd * 10) + 2,
            "72e50b91": lambda cmd: (cmd * 9) + 3,
            "f43363c9": lambda cmd: (cmd * 8) + 2,
            "e9499711": lambda cmd: (cmd * 10) + 1,
            "bb079e20": lambda cmd: (cmd * 11) + 2,
            "887becc9": lambda cmd: (cmd * 15) + 5,
            "767c19cf": lambda cmd: (cmd * 14) + 5,
            "42a8f594": lambda cmd: (cmd * 10) + 3,
            "412e20d0": lambda cmd: (cmd * 10) + 3,
            "77ab23ba": lambda cmd: (cmd * 9) + 2,
            "a42ac7a3": lambda cmd: (cmd * 9) + 2,
            "3eda129c": lambda cmd: (cmd * 10) + 1,
            "e98c4af8": lambda cmd: (cmd * 10) + 2,
            "0f1c83e8": lambda cmd: (cmd * 13) + 3,
            "da0a9126": lambda cmd: (cmd * 13) + 4,
            "e717180d": lambda cmd: (cmd * 13) + 4,
            "4b447dff": lambda cmd: (cmd * 9) + 2,
            "5a866829": lambda cmd: (cmd * 8) + 2,
            "b10220c8": lambda cmd: (cmd * 8) + 2,
            "2e0c6d14": lambda cmd: (cmd * 9) + 2,
            "5a6a0e8c": lambda cmd: (cmd * 9) + 2,
        }
        return regras.get(item_id, lambda cmd: (cmd * 10) + 2)(cmd)

    resultado['Ponto de Pedido'] = resultado.apply(lambda row: calcular_pp_fixo(row['Item ID'], row['Consumo Médio Diário']), axis=1)

    for dias in [7, 15, 30, 45]:
        resultado[f'Necessidade {dias} dias'] = resultado['Consumo Médio Diário'] * dias

    resultado['Estoque Mínimo'] = resultado['Consumo Médio Diário'] * 30 * (estoque_seguranca / 100)

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

st.subheader("📋 Histórico de Movimentação (Novembro a 02/02, sem 12/02)")
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
