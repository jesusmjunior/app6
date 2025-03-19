import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

# -------------------- CONFIGURAÇÕES INICIAIS --------------------
st.set_page_config(page_title="COGEX Almoxarifado", layout="wide")

st.title("📦 COGEX ALMOXARIFADO")
st.markdown("**Sistema Integrado Google Sheets - Controle Matemático e Visual de Estoque**")

# -------------------- DICIONÁRIO CONFIGURAÇÕES --------------------
DICIONARIO_LOGICO = {
    'lead_time_padrao': 7,
    'buffer_percentual_padrao': 15,
    'dias_cobertura': [7, 15, 30, 45],
    'fuzzy_critico': 7,
    'fuzzy_alerta': 15
}

# -------------------- CARREGAMENTO DE DADOS DO GOOGLE SHEETS --------------------
@st.cache_data(show_spinner="Carregando dados do Google Sheets...")
def load_data():
    url_inventory = 'https://docs.google.com/spreadsheets/d/e/2PACX-1vSeWsxmLFzuWsa2oggpQb6p5SFapxXHcWaIl0Jjf2wAezvMgAV9XCc1r7fSSzRWTCgjk9eqREgWlrzp/pub?gid=1710164548&single=true&output=csv'
    url_items = 'https://docs.google.com/spreadsheets/d/e/2PACX-1vSeWsxmLFzuWsa2oggpQb6p5SFapxXHcWaIl0Jjf2wAezvMgAV9XCc1r7fSSzRWTCgjk9eqREgWlrzp/pub?gid=1011017078&single=true&output=csv'

    inventory = pd.read_csv(url_inventory)
    inventory['DateTime'] = pd.to_datetime(inventory['DateTime'], errors='coerce')
    items = pd.read_csv(url_items)
    return items, inventory

items_df, inventory_df = load_data()

# -------------------- FUNÇÕES UTILITÁRIAS --------------------
def calcular_consumo_medio(inventory):
    consumo = inventory[inventory['Amount'] < 0].groupby('Item ID')['Amount'].sum().abs()
    dias = (inventory['DateTime'].max() - inventory['DateTime'].min()).days
    consumo_medio = consumo / dias
    return consumo_medio

def calcular_saldo_atual(inventory):
    saldo = inventory.groupby('Item ID')['Amount'].sum()
    return saldo

# -------------------- FUNÇÃO DE PEDIDO AUTOMÁTICO --------------------
def gerar_pedido(lead_time, buffer_percent):
    consumo = calcular_consumo_medio(inventory_df)
    saldo = calcular_saldo_atual(inventory_df)

    pedido_df = pd.DataFrame()
    pedido_df['Consumo Médio Diário'] = consumo
    pedido_df['Estoque Atual'] = saldo
    pedido_df['Estoque Mínimo'] = (pedido_df['Consumo Médio Diário'] * lead_time).round()
    pedido_df['Buffer Segurança'] = (pedido_df['Estoque Mínimo'] * buffer_percent / 100).round()
    pedido_df['Ponto de Pedido'] = pedido_df['Estoque Mínimo'] + pedido_df['Buffer Segurança']
    pedido_df['Cobertura Atual (dias)'] = (pedido_df['Estoque Atual'] / pedido_df['Consumo Médio Diário']).round(1)

    # Fuzzy Criticidade
    pedido_df['Criticidade'] = pedido_df['Cobertura Atual (dias)'].apply(lambda x: 'Crítico' if x < DICIONARIO_LOGICO['fuzzy_critico'] else ('Alerta' if x < DICIONARIO_LOGICO['fuzzy_alerta'] else 'Ok'))

    pedido_df = pedido_df.reset_index()
    pedido_df = pd.merge(pedido_df, items_df[['Item ID', 'Name', 'Description', 'Image']], on='Item ID', how='left')
    return pedido_df

# -------------------- INTERFACE STREAMLIT --------------------
menu = st.sidebar.selectbox("Navegar", ["Pedido Automático de Material", "Estoque Atual com Imagens", "Estatísticas", "Indicadores", "Alertas & Rankings"])

# -------------------- ABA PEDIDO AUTOMÁTICO --------------------
if menu == "Pedido Automático de Material":
    st.header("📄 Pedido Automático de Material")
    lead_time = st.number_input("Lead Time (dias):", min_value=1, value=DICIONARIO_LOGICO['lead_time_padrao'])
    buffer_percent = st.number_input("Buffer de Segurança (%):", min_value=0, value=DICIONARIO_LOGICO['buffer_percentual_padrao'])

    pedido = gerar_pedido(lead_time, buffer_percent)

    # Tabelas de pedido para múltiplos períodos
    for dias in DICIONARIO_LOGICO['dias_cobertura']:
        pedido[f'Necessidade {dias} dias'] = (pedido['Consumo Médio Diário'] * dias).round()
        pedido[f'A Pedir {dias} dias'] = pedido.apply(lambda row: max(row[f'Necessidade {dias} dias'] - row['Estoque Atual'], 0), axis=1)

    st.subheader("Resumo do Pedido de Material para cada período:")
    st.dataframe(pedido[['Item ID', 'Name', 'Estoque Atual', 'Cobertura Atual (dias)', 'Criticidade'] + [f'A Pedir {dias} dias' for dias in DICIONARIO_LOGICO['dias_cobertura']]], use_container_width=True)

    csv = pedido.to_csv(index=False).encode('utf-8')
    st.download_button("📥 Baixar Pedido CSV", data=csv, file_name=f'pedido_automatico.csv', mime='text/csv')

# -------------------- ABA ALERTAS & RANKINGS --------------------
elif menu == "Alertas & Rankings":
    st.header("🚨 Alertas de Estoque e Ranking de Consumo")

    pedido_alerta = gerar_pedido(DICIONARIO_LOGICO['lead_time_padrao'], DICIONARIO_LOGICO['buffer_percentual_padrao'])

    st.subheader("Itens com Criticidade Alta")
    criticos = pedido_alerta[pedido_alerta['Criticidade'] == 'Crítico']
    st.dataframe(criticos[['Item ID', 'Name', 'Estoque Atual', 'Cobertura Atual (dias)', 'Criticidade']], use_container_width=True)

    st.subheader("Ranking de Consumo (Top 10)")
    ranking = pedido_alerta.sort_values(by='Consumo Médio Diário', ascending=False).head(10)
    fig = px.bar(ranking, x='Name', y='Consumo Médio Diário', color='Criticidade', title='Top 10 Consumo Médio Diário')
    st.plotly_chart(fig, use_container_width=True)

# -------------------- RODAPÉ --------------------
st.markdown("---")
st.markdown("**COGEX ALMOXARIFADO - Controle Matemático e Visual | Powered by Streamlit**")
