import streamlit as st
import pandas as pd
import numpy as np
from fpdf import FPDF
import matplotlib.pyplot as plt

# -------------------- CONFIGURAÇÕES INICIAIS --------------------
st.set_page_config(page_title="COGEX Almoxarifado", layout="wide")

st.title("📦 COGEX ALMOXARIFADO")
st.markdown("**Sistema Web - Controle Matemático de Estoque - Pedido Automatizado com Critérios Reais**")

# -------------------- CONFIGURAÇÕES --------------------
DICIONARIO_LOGICO = {
    'dias_cobertura': [7, 15, 30, 45],
    'critico_limite': 0,  # Estoque negativo ou zero
    'alerta_limite': 1    # Cobertura inferior ao consumo de 15 dias
}

# -------------------- CARREGAMENTO DE DADOS --------------------
@st.cache_data(show_spinner="Carregando dados do Google Sheets...")
def load_data():
    url_inventory = 'https://docs.google.com/spreadsheets/d/e/2PACX-1vSeWsxmLFzuWsa2oggpQb6p5SFapxXHcWaIl0Jjf2wAezvMgAV9XCc1r7fSSzRWTCgjk9eqREgWlrzp/pub?gid=1710164548&single=true&output=csv'
    url_items = 'https://docs.google.com/spreadsheets/d/e/2PACX-1vSeWsxmLFzuWsa2oggpQb6p5SFapxXHcWaIl0Jjf2wAezvMgAV9XCc1r7fSSzRWTCgjk9eqREgWlrzp/pub?gid=1011017078&single=true&output=csv'
    
    inventory = pd.read_csv(url_inventory)
    inventory['DateTime'] = pd.to_datetime(inventory['DateTime'], errors='coerce')
    items = pd.read_csv(url_items)
    return items, inventory

items_df, inventory_df = load_data()

# -------------------- FUNÇÕES MATEMÁTICAS --------------------
def calcular_consumo_medio(inventory):
    consumo = inventory[inventory['Amount'] < 0].groupby('Item ID')['Amount'].sum().abs()
    dias = (inventory['DateTime'].max() - inventory['DateTime'].min()).days
    consumo_medio = consumo / dias
    return consumo_medio

def calcular_saldo_atual(inventory):
    saldo = inventory.groupby('Item ID')['Amount'].sum()
    return saldo

def gerar_pedido(data_proximo_pedido, intervalo_novo_pedido):
    consumo_medio = calcular_consumo_medio(inventory_df)
    saldo = calcular_saldo_atual(inventory_df)

    pedido_df = pd.merge(items_df[['Item ID', 'Name', 'Description']], saldo.reset_index(), on='Item ID', how='left')
    pedido_df = pd.merge(pedido_df, consumo_medio.reset_index(), on='Item ID', how='left', suffixes=('_Estoque', '_Consumo'))

    pedido_df = pedido_df.fillna({'Amount_Estoque': 0, 'Amount_Consumo': 0})

    dias_ate_pedido = (pd.to_datetime(data_proximo_pedido) - pd.to_datetime('today')).days

    pedido_df['Consumo Médio Diário'] = pedido_df['Amount_Consumo']
    pedido_df['Estoque Atual'] = pedido_df['Amount_Estoque']
    pedido_df['Dias até Pedido'] = dias_ate_pedido

    for dias in DICIONARIO_LOGICO['dias_cobertura']:
        pedido_df[f'Necessidade {dias} dias'] = (pedido_df['Consumo Médio Diário'] * dias).round()
        pedido_df[f'A Pedir {dias} dias'] = pedido_df.apply(lambda row: max(row[f'Necessidade {dias} dias'] - row['Estoque Atual'], 0), axis=1)

    pedido_df['Estoque Necessário até Pedido'] = (pedido_df['Consumo Médio Diário'] * dias_ate_pedido).round()
    pedido_df['Faltante Até Pedido'] = pedido_df['Estoque Necessário até Pedido'] - pedido_df['Estoque Atual']

    pedido_df['Status'] = pedido_df.apply(lambda row: '🔴 Crítico' if row['Estoque Atual'] <= DICIONARIO_LOGICO['critico_limite'] or row['Estoque Atual'] < row['Estoque Necessário até Pedido'] else ('🟡 Alerta' if row['Estoque Atual'] < row['Consumo Médio Diário'] * 15 else '🟢 Ok'), axis=1)

    return pedido_df

# -------------------- FUNÇÃO PARA PDF --------------------
def gerar_pdf(df, data_pedido):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, f"PEDIDO DE MATERIAL PARA 7, 15, 30 E 45 DIAS - {data_pedido}", ln=True, align='C')
    pdf.set_font("Arial", size=10)

    for index, row in df.iterrows():
        pdf.cell(0, 8, f"{row['Item ID']} - {row['Name']} - Status: {row['Status']} | Min: {row['Estoque Necessário até Pedido']} | 7d: {row['A Pedir 7 dias']} | 15d: {row['A Pedir 15 dias']} | 30d: {row['A Pedir 30 dias']} | 45d: {row['A Pedir 45 dias']}", ln=True)

    return pdf.output(dest='S').encode('latin-1')

# -------------------- INTERFACE STREAMLIT --------------------
menu = st.sidebar.selectbox("Navegar", ["Pedido Automático de Material", "Alertas & Rankings"])

if menu == "Pedido Automático de Material":
    st.header("📄 PEDIDO DE MATERIAL PARA 7, 15, 30 E 45 DIAS")
    data_proximo_pedido = st.date_input("Data do Próximo Pedido")
    intervalo_novo_pedido = st.number_input("Intervalo entre Pedidos (dias):", min_value=1, value=15)

    pedido = gerar_pedido(data_proximo_pedido, intervalo_novo_pedido)

    st.subheader("Resumo do Pedido de Material para cada período:")
    st.dataframe(pedido[['Item ID', 'Name', 'Estoque Atual', 'Consumo Médio Diário', 'Dias até Pedido', 'Estoque Necessário até Pedido', 'Faltante Até Pedido', 'Status'] + [f'A Pedir {dias} dias' for dias in DICIONARIO_LOGICO['dias_cobertura']]], use_container_width=True)

    csv = pedido.to_csv(index=False).encode('utf-8')
    st.download_button("📥 Baixar Pedido CSV", data=csv, file_name=f'pedido_automatico.csv', mime='text/csv')

    pdf = gerar_pdf(pedido, data_proximo_pedido)
    st.download_button("📥 Baixar Pedido PDF", data=pdf, file_name=f'pedido_automatico.pdf', mime='application/pdf')

    st.subheader("📊 Gráficos Estoque por Status")

    status_cores = {'🔴 Crítico': 'red', '🟡 Alerta': 'orange', '🟢 Ok': 'green'}
    for status, cor in status_cores.items():
        subset = pedido[pedido['Status'] == status]
        if not subset.empty:
            st.subheader(f"{status} - {len(subset)} produtos")
            fig, ax = plt.subplots(figsize=(10,5))
            subset.plot(kind='bar', x='Name', y='Estoque Atual', color=cor, ax=ax)
            plt.xticks(rotation=90)
            plt.title(f'Produtos {status}')
            st.pyplot(fig)

elif menu == "Alertas & Rankings":
    st.header("🚨 Itens Críticos, Alerta ou Ok")

    data_proximo_pedido = pd.to_datetime('today') + pd.Timedelta(days=15)
    pedido_alerta = gerar_pedido(data_proximo_pedido, 15)

    st.subheader("Itens com Estoque Crítico ou Alerta")
    criticos = pedido_alerta[pedido_alerta['Status'] != '🟢 Ok']
    st.dataframe(criticos[['Item ID', 'Name', 'Estoque Atual', 'Estoque Necessário até Pedido', 'Status']], use_container_width=True)

    st.subheader("Ranking de Consumo (Top 10)")
    ranking = pedido_alerta.sort_values(by='Consumo Médio Diário', ascending=False).head(10)
    st.bar_chart(ranking.set_index('Name')['Consumo Médio Diário'])

# -------------------- RODAPÉ --------------------
st.markdown("---")
st.markdown("**COGEX ALMOXARIFADO - Gestão Matemática Real com Critérios de Estoque | Powered by Streamlit**")
