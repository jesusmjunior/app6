import streamlit as st
import pandas as pd
from datetime import datetime

# ==============================
# 1. Função para carregar dados
# ==============================
@st.cache_data
def carregar_dados():
    items_url = 'https://docs.google.com/spreadsheets/d/e/2PACX-1vSeWsxmLFzuWsa2oggpQb6p5SFapxXHcWaIl0Jjf2wAezvMgAV9XCc1r7fSSzRWTCgjk9eqREgWlrzp/pub?output=csv&gid=1011017078'
    inventory_url = 'https://docs.google.com/spreadsheets/d/e/2PACX-1vSeWsxmLFzuWsa2oggpQb6p5SFapxXHcWaIl0Jjf2wAezvMgAV9XCc1r7fSSzRWTCgjk9eqREgWlrzp/pub?output=csv&gid=1710164548'

    items_df = pd.read_csv(items_url)
    inventory_df = pd.read_csv(inventory_url)
    inventory_df['DateTime'] = pd.to_datetime(inventory_df['DateTime'], errors='coerce', dayfirst=True)

    return items_df, inventory_df

# ==============================
# 2. Função de preparação e limpeza
# ==============================
def preparar_dados(items_df, inventory_df):
    items_df['Item ID'] = items_df['Item ID'].str.strip()
    inventory_df['Item ID'] = inventory_df['Item ID'].str.strip()
    return items_df, inventory_df

# ==============================
# 3. Função de cálculo de estoque
# ==============================
def calcular_estoque(items_df, inventory_df, data_pedido, estoque_seguranca, dias_media):
    # Filtrar período até Dia D (12/02 excluído)
    inicio_periodo = pd.to_datetime('2019-11-01')
    fim_periodo = pd.to_datetime('2020-02-02')

    periodo_pre_d = inventory_df[(inventory_df['DateTime'] >= inicio_periodo) &
                                 (inventory_df['DateTime'] <= fim_periodo) &
                                 (inventory_df['DateTime'].dt.strftime('%Y-%m-%d') != '2020-02-12')].copy()

    # Separar entradas e saídas
    entradas = periodo_pre_d[periodo_pre_d['Amount'] > 0]
    saidas = periodo_pre_d[periodo_pre_d['Amount'] < 0]

    # Estoque Atual
    estoque_atual = periodo_pre_d.groupby('Item ID')['Amount'].sum().reset_index()
    estoque_atual.columns = ['Item ID', 'Estoque Atual']

    # Consumo Médio Diário baseado no período configurado
    ultimos_dias = inventory_df[inventory_df['DateTime'] >= (inventory_df['DateTime'].max() - pd.Timedelta(days=dias_media))]
    saidas_futuro = ultimos_dias[ultimos_dias['Amount'] < 0].copy()
    saidas_futuro['Amount'] = saidas_futuro['Amount'].abs()
    dias_totais = dias_media or 1
    consumo_medio = saidas_futuro.groupby('Item ID')['Amount'].sum() / dias_totais
    consumo_medio = consumo_medio.reset_index()
    consumo_medio.columns = ['Item ID', 'Consumo Médio Diário']

    # Unir dados com Items
    resultado = pd.merge(estoque_atual, consumo_medio, on='Item ID', how='left')
    resultado['Consumo Médio Diário'].fillna(0, inplace=True)
    nome_map = dict(zip(items_df['Item ID'], items_df['Name']))
    desc_map = dict(zip(items_df['Item ID'], items_df['Description']))
    resultado['Nome Produto'] = resultado['Item ID'].map(nome_map)
    resultado['Descrição'] = resultado['Item ID'].map(desc_map)

    # Necessidades para múltiplos períodos
    for dias in [7, 15, 30, 45]:
        resultado[f'Necessidade {dias} dias'] = resultado['Consumo Médio Diário'] * dias

    # Estoque Mínimo configurável
    resultado['Estoque Mínimo'] = resultado['Consumo Médio Diário'] * 30 * (estoque_seguranca / 100)

    # Classificação
    def definir_status(row):
        if (row['Estoque Atual'] - row['Necessidade 15 dias']) < row['Estoque Mínimo']:
            return 'Vermelho - Alerta Crítico'
        elif (row['Estoque Atual'] - row['Necessidade 30 dias']) < row['Estoque Mínimo']:
            return 'Amarelo - Alerta Médio'
        else:
            return 'Verde - OK'

    resultado['Status'] = resultado.apply(definir_status, axis=1)

    return resultado, entradas, saidas, periodo_pre_d

# ==============================
# 4. Função para gerar pedido exportável
# ==============================
def gerar_pedido(resultado, periodo):
    pedido = resultado.copy()
    pedido['Qtd a Pedir'] = (pedido[f'Necessidade {periodo} dias'] - pedido['Estoque Atual'] + pedido['Estoque Mínimo']).apply(lambda x: max(0, round(x)))
    return pedido

# ==============================
# 5. INÍCIO STREAMLIT APP
# ==============================
st.set_page_config(page_title="📦 Dashboard Estoque", layout="wide")
st.title("📦 Dashboard de Controle de Estoque - Dados Reais")

# Carregar e preparar dados
items_df, inventory_df = carregar_dados()
items_df, inventory_df = preparar_dados(items_df, inventory_df)

# Sidebar
st.sidebar.header("Parâmetros")
data_pedido = st.sidebar.date_input("Data do Próximo Pedido:", datetime.today())
periodo = st.sidebar.selectbox("Período para Pedido:", [7, 15, 30, 45])
estoque_seguranca = st.sidebar.slider("% Estoque de Segurança:", 10, 100, 50, step=10)
dias_media = st.sidebar.slider("Dias para Média de Consumo:", 15, 120, 60, step=15)

# Cálculos
resultado, entradas, saidas, inventario = calcular_estoque(items_df, inventory_df, pd.to_datetime(data_pedido), estoque_seguranca, dias_media)

# Histórico Geral
st.subheader("📋 Histórico de Movimentação (Novembro a 02/02, sem 12/02)")
st.dataframe(inventario[['Item ID', 'DateTime', 'Amount']])

# Entradas e Saídas
col1, col2 = st.columns(2)
with col1:
    st.write("### ➕ Entradas de Estoque")
    st.dataframe(entradas[['Item ID', 'DateTime', 'Amount']])
with col2:
    st.write("### ➖ Saídas de Estoque")
    st.dataframe(saidas[['Item ID', 'DateTime', 'Amount']])

# Status dos produtos
st.subheader(f"📅 Status dos Produtos para {periodo} dias")
status_tabs = st.tabs(["🔴 Crítico", "🟡 Médio", "🟢 OK"])

for idx, status in enumerate(['Vermelho - Alerta Crítico', 'Amarelo - Alerta Médio', 'Verde - OK']):
    with status_tabs[idx]:
        st.dataframe(resultado[resultado['Status'] == status][['Item ID', 'Nome Produto', 'Descrição', 'Estoque Atual', f'Necessidade {periodo} dias', 'Estoque Mínimo', 'Status']])

# Gerar Pedido
st.subheader("📄 Pedido de Material")
pedido = gerar_pedido(resultado, periodo)
st.dataframe(pedido[['Item ID', 'Nome Produto', 'Descrição', 'Estoque Atual', f'Necessidade {periodo} dias', 'Qtd a Pedir']])

csv = pedido.to_csv(index=False).encode('utf-8')
st.download_button(
    label=f"📥 Download Pedido de Material para {periodo} dias",
    data=csv,
    file_name=f'Pedido_Material_{periodo}_dias.csv',
    mime='text/csv'
)
