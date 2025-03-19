# app.py

import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
from datetime import datetime, timedelta
from io import BytesIO
import smtplib
from email.message import EmailMessage

# -------------------- CONFIGURAÇÕES INICIAIS --------------------
st.set_page_config(page_title="COGEX Almoxarifado", layout="wide")
st.title("📦 COGEX ALMOXARIFADO")
st.markdown("**Sistema Integrado Google Sheets - Pedido de Material com Imagens, Filtros e Preditivos**")

# -------------------- CARREGAMENTO DE DADOS --------------------
@st.cache_data(show_spinner="Carregando dados do Google Sheets...")
def load_data():
    url_inventory = 'https://docs.google.com/spreadsheets/d/e/2PACX-1vSeWsxmLFzuWsa2oggpQb6p5SFapxXHcWaIl0Jjf2wAezvMgAV9XCc1r7fSSzRWTCgjk9eqREgWlrzp/pub?gid=1710164548&single=true&output=csv'
    url_items = 'https://docs.google.com/spreadsheets/d/e/2PACX-1vSeWsxmLFzuWsa2oggpQb6p5SFapxXHcWaIl0Jjf2wAezvMgAV9XCc1r7fSSzRWTCgjk9eqREgWlrzp/pub?gid=1011017078&single=true&output=csv'

    inventory = pd.read_csv(url_inventory)
    inventory['DateTime'] = pd.to_datetime(inventory['DateTime'], errors='coerce')
    items = pd.read_csv(url_items)

    # Gerar link de imagem
    items['Image_Link'] = items['Image'].apply(lambda x: f'https://drive.google.com/uc?export=view&id=17DLW40Xz_UiOS-YVR-BzlYffV6mQsQvp/{x}')

    return items, inventory

items_df, inventory_df = load_data()

# -------------------- PREPARAÇÃO DOS DADOS --------------------
merged_df = pd.merge(inventory_df, items_df, on='Item ID', how='left')
merged_df['Ano'] = merged_df['DateTime'].dt.year
merged_df['Mês'] = merged_df['DateTime'].dt.month
merged_df['Semana'] = merged_df['DateTime'].dt.isocalendar().week

# -------------------- CONSUMO MÉDIO --------------------
def consumo_medio(df, dias):
    data_limite = datetime.now() - timedelta(days=dias)
    consumo = df[(df['DateTime'] >= data_limite) & (df['Amount'] < 0)]
    consumo_agrupado = consumo.groupby(['Item ID', 'Name', 'Image_Link'])['Amount'].sum().abs().reset_index()
    consumo_agrupado.rename(columns={'Amount': f'Consumo Médio {dias} dias'}, inplace=True)
    return consumo_agrupado

consumo_7 = consumo_medio(merged_df, 7)
consumo_15 = consumo_medio(merged_df, 15)
consumo_30 = consumo_medio(merged_df, 30)
consumo_45 = consumo_medio(merged_df, 45)

consumo_total = consumo_7.merge(consumo_15, on=['Item ID', 'Name', 'Image_Link'], how='outer')\
                        .merge(consumo_30, on=['Item ID', 'Name', 'Image_Link'], how='outer')\
                        .merge(consumo_45, on=['Item ID', 'Name', 'Image_Link'], how='outer').fillna(0)

estoque_atual = inventory_df.groupby('Item ID')['Amount'].sum().reset_index()
estoque_atual = pd.merge(estoque_atual, items_df[['Item ID', 'Name']], on='Item ID', how='left')

pedido_material = pd.merge(consumo_total, estoque_atual, on=['Item ID', 'Name'], how='left')
pedido_material['Estoque Atual'] = pedido_material['Amount']
pedido_material.drop(columns=['Amount'], inplace=True)

pedido_material['Recomendação Pedido'] = np.where(
    pedido_material['Estoque Atual'] < pedido_material['Consumo Médio 15 dias'],
    'Pedido Necessário',
    'OK'
)

# -------------------- TABS --------------------
tabs = st.tabs(["📋 Tabela & Filtros", "🖼️ Detalhes por Produto", "📊 Estatísticas & Alertas", "📥 Pedido Automático Almoxarifado COGEX"])

with tabs[0]:
    st.header("📊 Controle e Consumo Médio por Produto")

    st.dataframe(pedido_material)

    st.subheader("📈 Gráfico - Consumo Médio (15 dias)")
    chart = alt.Chart(pedido_material).mark_bar().encode(
        x=alt.X('Name:N', sort='-y'),
        y='Consumo Médio 15 dias:Q',
        color=alt.Color('Recomendação Pedido:N', scale=alt.Scale(domain=['Pedido Necessário', 'OK'], range=['red', 'green'])),
        tooltip=['Name', 'Estoque Atual', 'Consumo Médio 7 dias', 'Consumo Médio 15 dias', 'Consumo Médio 30 dias', 'Recomendação Pedido']
    ).properties(width=900, height=400)

    st.altair_chart(chart)

    st.subheader("🏆 Ranking - Itens Mais Consumidos (Últimos 30 dias)")
    ranking_30 = consumo_30.sort_values(by='Consumo Médio 30 dias', ascending=False)
    st.table(ranking_30[['Name', 'Consumo Médio 30 dias']])

    st.download_button(
        label="📥 Baixar Relatório Pedido (CSV)",
        data=pedido_material.to_csv(index=False).encode('utf-8'),
        file_name='pedido_material_cogex.csv',
        mime='text/csv'
    )

with tabs[1]:
    st.header("📦 Detalhes do Produto Selecionado")
    produto_selecionado = st.selectbox("Selecione um Produto:", options=pedido_material['Name'].unique())
    produto_info = pedido_material[pedido_material['Name'] == produto_selecionado].iloc[0]

    st.image(produto_info['Image_Link'], caption=produto_info['Name'], use_container_width=True)
    st.markdown(f"**ID:** {produto_info['Item ID']}")
    st.markdown(f"**Estoque Atual:** {produto_info['Estoque Atual']}")
    st.markdown(f"**Consumo Médio 7 dias:** {produto_info['Consumo Médio 7 dias']}")
    st.markdown(f"**Consumo Médio 15 dias:** {produto_info['Consumo Médio 15 dias']}")
    st.markdown(f"**Consumo Médio 30 dias:** {produto_info['Consumo Médio 30 dias']}")
    st.markdown(f"**Consumo Médio 45 dias:** {produto_info['Consumo Médio 45 dias']}")
    st.markdown(f"**Status de Pedido:** {produto_info['Recomendação Pedido']}")
