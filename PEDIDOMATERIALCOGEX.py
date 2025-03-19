import streamlit as st
import pandas as pd
import numpy as np

# -------------------- CONFIGURAÇÕES INICIAIS --------------------
st.set_page_config(page_title="COGEX Almoxarifado", layout="wide")

st.title("📦 COGEX ALMOXARIFADO")
st.markdown("**Sistema Web - Controle Matemático e Visual de Estoque com Lógica Fuzzy Avançada**")

# -------------------- DICIONÁRIO CONFIGURAÇÕES --------------------
DICIONARIO_LOGICO = {
    'lead_time_padrao': 7,
    'buffer_percentual_padrao': 15,
    'dias_cobertura': [7, 15, 30, 45],
    'fuzzy_critico': 7,
    'fuzzy_alerta': 15,
    'variabilidade_alta': 30,  # Coeficiente de variação em %
    'fator_seguro': 1.5,
    'min_historico': 5
}

# -------------------- CARREGAMENTO DE DADOS ONLINE --------------------
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
def calcular_consumo_total(inventory):
    consumo = inventory[inventory['Amount'] < 0].groupby('Item ID')['Amount'].sum().abs()
    return consumo

def calcular_saldo_atual(inventory):
    saldo = inventory.groupby('Item ID')['Amount'].sum()
    return saldo

def contar_registros(inventory):
    registros = inventory.groupby('Item ID')['Amount'].count()
    return registros

def calcular_ponto_pedido(consumo_total, lead_time, saldo_atual):
    consumo_diario = consumo_total / lead_time
    estoque_medio = (saldo_atual + consumo_total) / 2
    ponto_pedido = consumo_diario * lead_time
    return consumo_diario, estoque_medio, ponto_pedido

# -------------------- FUNÇÃO DE PEDIDO AUTOMÁTICO --------------------
def gerar_pedido(lead_time):
    consumo_total = calcular_consumo_total(inventory_df)
    saldo = calcular_saldo_atual(inventory_df)
    registros = contar_registros(inventory_df)

    pedido_df = pd.DataFrame()
    pedido_df['Consumo Total'] = consumo_total
    pedido_df['Estoque Atual'] = saldo
    pedido_df['Qtd Registros'] = registros
    pedido_df['Consumo Diário Estimado'], pedido_df['Estoque Médio'], pedido_df['Ponto de Pedido'] = calcular_ponto_pedido(consumo_total, lead_time, saldo)

    pedido_df = pedido_df.reset_index()
    pedido_df = pd.merge(pedido_df, items_df[['Item ID', 'Name', 'Description']], on='Item ID', how='left')

    return pedido_df

# -------------------- INTERFACE STREAMLIT --------------------
menu = st.sidebar.selectbox("Navegar", ["Pedido Automático de Material", "Alertas & Rankings"])

if menu == "Pedido Automático de Material":
    st.header("📄 Pedido Automático de Material com Cálculo Just-In-Time")
    lead_time = st.number_input("Lead Time (dias):", min_value=1, value=DICIONARIO_LOGICO['lead_time_padrao'])
    periodo_personalizado = st.number_input("Período Personalizado de Análise (dias):", min_value=1, value=10)

    pedido = gerar_pedido(lead_time)

    for dias in DICIONARIO_LOGICO['dias_cobertura'] + [periodo_personalizado]:
        pedido[f'Necessidade {dias} dias'] = (pedido['Consumo Diário Estimado'] * dias).round()
        pedido[f'A Pedir {dias} dias'] = pedido.apply(lambda row: max(row[f'Necessidade {dias} dias'] - row['Estoque Atual'], 0), axis=1)

    st.subheader("Resumo do Pedido de Material para cada período:")
    st.dataframe(pedido[['Item ID', 'Name', 'Estoque Atual', 'Estoque Médio', 'Ponto de Pedido', 'Qtd Registros'] + [f'A Pedir {dias} dias' for dias in DICIONARIO_LOGICO['dias_cobertura'] + [periodo_personalizado]]], use_container_width=True)

    csv = pedido.to_csv(index=False).encode('utf-8')
    st.download_button("📥 Baixar Pedido CSV", data=csv, file_name=f'pedido_automatico.csv', mime='text/csv')

elif menu == "Alertas & Rankings":
    st.header("🚨 Alertas de Estoque e Ranking")

    pedido_alerta = gerar_pedido(DICIONARIO_LOGICO['lead_time_padrao'])

    st.subheader("Itens com Estoque Baixo ou Registros Insuficientes")
    criticos = pedido_alerta[pedido_alerta['Estoque Atual'] < pedido_alerta['Ponto de Pedido']]
    st.dataframe(criticos[['Item ID', 'Name', 'Estoque Atual', 'Estoque Médio', 'Ponto de Pedido', 'Qtd Registros']], use_container_width=True)

    st.subheader("Ranking de Consumo (Top 10)")
    ranking = pedido_alerta.sort_values(by='Consumo Total', ascending=False).head(10)
    st.bar_chart(ranking.set_index('Name')['Consumo Total'])

# -------------------- RODAPÉ --------------------
st.markdown("---")
st.markdown("**COGEX ALMOXARIFADO - Motor Matemático Just-In-Time | Powered by Streamlit**")
