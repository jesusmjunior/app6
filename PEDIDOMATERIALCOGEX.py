import streamlit as st
import pandas as pd
from datetime import datetime

# Função para carregar dados (exemplo via CSV público, pode adaptar para seu Google Sheet)
@st.cache_data
def carregar_dados():
    items_url = 'https://docs.google.com/spreadsheets/d/1NLLZoIxIZ2u-liHGKM5P8WNXdu3ycCoUUiD3f0FsR84/export?format=csv&gid=0'
    inventory_url = 'https://docs.google.com/spreadsheets/d/1NLLZoIxIZ2u-liHGKM5P8WNXdu3ycCoUUiD3f0FsR84/export?format=csv&gid=1124002636'
    
    items_df = pd.read_csv(items_url)
    inventory_df = pd.read_csv(inventory_url, parse_dates=['DateTime'], dayfirst=True)
    return items_df, inventory_df

# Função para cálculo do estoque
def calcular_estoque(items_df, inventory_df, data_pedido):
    # Ajuste IDs
    items_df['Item ID'] = items_df['Item ID'].str.strip()
    inventory_df['Item ID'] = inventory_df['Item ID'].str.strip()

    # Período pré-definido até 02/02
    inicio_periodo = pd.to_datetime('2019-11-01')
    fim_periodo = pd.to_datetime('2020-02-02')

    if data_pedido <= datetime(2020, 2, 2):
        inventory_periodo = inventory_df[(inventory_df['DateTime'] >= inicio_periodo) & (inventory_df['DateTime'] <= fim_periodo)]
    else:
        inventory_periodo = inventory_df

    # Estoque Atual
    estoque_atual = inventory_periodo.groupby('Item ID')['Amount'].sum().reset_index()
    estoque_atual.columns = ['Item ID', 'Estoque Atual']

    # Consumo Médio Diário
    consumo_df = inventory_periodo[inventory_periodo['Amount'] < 0].copy()
    consumo_df['Amount'] = consumo_df['Amount'].abs()
    dias_periodo = (inventory_periodo['DateTime'].max() - inventory_periodo['DateTime'].min()).days or 1
    consumo_medio = consumo_df.groupby('Item ID')['Amount'].sum() / dias_periodo
    consumo_medio = consumo_medio.reset_index()
    consumo_medio.columns = ['Item ID', 'Consumo Médio Diário']

    # Juntar dados
    resultado = pd.merge(estoque_atual, consumo_medio, on='Item ID', how='left')
    resultado['Consumo Médio Diário'].fillna(0, inplace=True)

    # Calcular necessidades
    for dias in [7, 15, 30, 45]:
        resultado[f'Necessidade {dias} dias'] = resultado['Consumo Médio Diário'] * dias
    resultado['Estoque Mínimo'] = resultado['Consumo Médio Diário'] * 30 * 0.5

    # Status
    def definir_status(row):
        if (row['Estoque Atual'] - row['Necessidade 15 dias']) < row['Estoque Mínimo']:
            return 'Vermelho - Alerta Crítico'
        elif (row['Estoque Atual'] - row['Necessidade 30 dias']) < row['Estoque Mínimo']:
            return 'Amarelo - Alerta Médio'
        else:
            return 'Verde - OK'

    resultado['Status'] = resultado.apply(definir_status, axis=1)
    
    # Mapear nomes
    nome_map = dict(zip(items_df['Item ID'], items_df['Name']))
    resultado['Nome Produto'] = resultado['Item ID'].map(nome_map)

    return resultado

# --------- INÍCIO DO APP ---------
st.set_page_config(page_title="Dashboard Estoque", layout="wide")
st.title("📦 Dashboard de Controle de Estoque")

# Carregar dados
items_df, inventory_df = carregar_dados()

# Inputs
st.sidebar.header("Parâmetros do Pedido")
data_pedido = st.sidebar.date_input("Data do Próximo Pedido:", datetime.today())
periodo = st.sidebar.selectbox("Período para Pedido:", [7, 15, 30, 45])

# Calcular estoque
resultado = calcular_estoque(items_df, inventory_df, pd.to_datetime(data_pedido))

# Exibir por status
st.subheader(f"📅 Status dos Produtos para {periodo} dias")
status_tabs = st.tabs(["🔴 Crítico", "🟡 Médio", "🟢 OK"])

# Separar por status
for idx, status in enumerate(['Vermelho - Alerta Crítico', 'Amarelo - Alerta Médio', 'Verde - OK']):
    with status_tabs[idx]:
        st.dataframe(resultado[resultado['Status'] == status][['Item ID', 'Nome Produto', 'Estoque Atual', f'Necessidade {periodo} dias', 'Estoque Mínimo', 'Status']])

# Gerar arquivo
st.subheader("📄 Gerar Pedido de Material")

pedido = resultado.copy()
pedido['Qtd a Pedir'] = (pedido[f'Necessidade {periodo} dias'] - pedido['Estoque Atual'] + pedido['Estoque Mínimo']).apply(lambda x: max(0, round(x)))

st.dataframe(pedido[['Item ID', 'Nome Produto', 'Estoque Atual', f'Necessidade {periodo} dias', 'Qtd a Pedir']])

csv = pedido.to_csv(index=False).encode('utf-8')
st.download_button(
    label=f"📥 Download Pedido de Material para {periodo} dias",
    data=csv,
    file_name=f'Pedido_Material_{periodo}_dias.csv',
    mime='text/csv'
)
