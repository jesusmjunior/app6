import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# -------------------- CONFIGURAÇÕES INICIAIS --------------------
st.set_page_config(page_title="COGEX Almoxarifado", layout="wide")

st.title("📦 COGEX ALMOXARIFADO")
st.markdown("**Sistema Integrado Google Sheets - Controle Matemático e Visual de Estoque com Lógica Fuzzy Avançada**")

# -------------------- DICIONÁRIO CONFIGURAÇÕES --------------------
DICIONARIO_LOGICO = {
    'lead_time_padrao': 7,
    'buffer_percentual_padrao': 15,
    'dias_cobertura': [7, 15, 30, 45],
    'fuzzy_critico': 7,
    'fuzzy_alerta': 15,
    'variabilidade_alta': 30,  # Coeficiente de variação em %
    'fator_seguro': 1.5,       # Novo fator para buffer dinâmico
    'min_historico': 5         # Mínimo de registros para análise confiável
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

# -------------------- FUNÇÕES UTILITÁRIAS --------------------
def calcular_consumo_medio(inventory):
    consumo = inventory[inventory['Amount'] < 0].groupby('Item ID')['Amount'].sum().abs()
    dias = (inventory['DateTime'].max() - inventory['DateTime'].min()).days
    consumo_medio = consumo / dias
    return consumo_medio

def calcular_saldo_atual(inventory):
    saldo = inventory.groupby('Item ID')['Amount'].sum()
    return saldo

def calcular_variabilidade(inventory):
    variabilidade = inventory[inventory['Amount'] < 0].groupby('Item ID')['Amount'].std().fillna(0)
    return variabilidade

def contar_registros(inventory):
    registros = inventory.groupby('Item ID')['Amount'].count()
    return registros

# Função matemática para buffer dinâmico
def calcular_buffer_dinamico(desvio_padrao):
    return (desvio_padrao * DICIONARIO_LOGICO['fator_seguro']).round()

def pertinencia_fuzzy_avancado(cobertura, variabilidade, registros):
    if registros < DICIONARIO_LOGICO['min_historico']:
        return '⚪️ Dados Insuficientes'
    if cobertura < DICIONARIO_LOGICO['fuzzy_critico'] and variabilidade > DICIONARIO_LOGICO['variabilidade_alta']:
        return '🔴 Crítico e Instável'
    elif cobertura < DICIONARIO_LOGICO['fuzzy_critico']:
        return '🟠 Crítico'
    elif variabilidade > DICIONARIO_LOGICO['variabilidade_alta']:
        return '🟡 Instável'
    else:
        return '🟢 Ok'

# -------------------- FUNÇÃO DE PEDIDO AUTOMÁTICO --------------------
def gerar_pedido(lead_time):
    consumo = calcular_consumo_medio(inventory_df)
    saldo = calcular_saldo_atual(inventory_df)
    variabilidade = calcular_variabilidade(inventory_df)
    registros = contar_registros(inventory_df)

    pedido_df = pd.DataFrame()
    pedido_df['Consumo Médio Diário'] = consumo
    pedido_df['Estoque Atual'] = saldo
    pedido_df['Variabilidade Consumo'] = variabilidade
    pedido_df['Qtd Registros'] = registros
    pedido_df['Coeficiente Variação (%)'] = ((variabilidade / consumo) * 100).round(1)
    pedido_df['Estoque Mínimo'] = (pedido_df['Consumo Médio Diário'] * lead_time).round()
    pedido_df['Buffer Dinâmico'] = calcular_buffer_dinamico(variabilidade)
    pedido_df['Ponto de Pedido'] = pedido_df['Estoque Mínimo'] + pedido_df['Buffer Dinâmico']
    pedido_df['Cobertura Atual (dias)'] = (pedido_df['Estoque Atual'] / pedido_df['Consumo Médio Diário']).round(1)

    # Fuzzy Criticidade Avançada
    pedido_df['Criticidade'] = pedido_df.apply(lambda row: pertinencia_fuzzy_avancado(row['Cobertura Atual (dias)'], row['Coeficiente Variação (%)'], row['Qtd Registros']), axis=1)

    pedido_df = pedido_df.reset_index()
    pedido_df = pd.merge(pedido_df, items_df[['Item ID', 'Name', 'Description']], on='Item ID', how='left')

    return pedido_df

# -------------------- INTERFACE STREAMLIT --------------------
menu = st.sidebar.selectbox("Navegar", ["Pedido Automático de Material", "Alertas & Rankings"])

# -------------------- ABA PEDIDO AUTOMÁTICO --------------------
if menu == "Pedido Automático de Material":
    st.header("📄 Pedido Automático de Material com Lógica Fuzzy Refinada")
    lead_time = st.number_input("Lead Time (dias):", min_value=1, value=DICIONARIO_LOGICO['lead_time_padrao'])

    pedido = gerar_pedido(lead_time)

    # Tabelas de pedido para múltiplos períodos
    for dias in DICIONARIO_LOGICO['dias_cobertura']:
        pedido[f'Necessidade {dias} dias'] = (pedido['Consumo Médio Diário'] * dias).round()
        pedido[f'A Pedir {dias} dias'] = pedido.apply(lambda row: max(row[f'Necessidade {dias} dias'] - row['Estoque Atual'], 0), axis=1)

    st.subheader("Resumo do Pedido de Material para cada período:")
    st.dataframe(pedido[['Item ID', 'Name', 'Estoque Atual', 'Cobertura Atual (dias)', 'Coeficiente Variação (%)', 'Qtd Registros', 'Criticidade'] + [f'A Pedir {dias} dias' for dias in DICIONARIO_LOGICO['dias_cobertura']]], use_container_width=True)

    csv = pedido.to_csv(index=False).encode('utf-8')
    st.download_button("📥 Baixar Pedido CSV", data=csv, file_name=f'pedido_automatico.csv', mime='text/csv')

# -------------------- ABA ALERTAS & RANKINGS --------------------
elif menu == "Alertas & Rankings":
    st.header("🚨 Alertas de Estoque e Ranking Fuzzy")

    pedido_alerta = gerar_pedido(DICIONARIO_LOGICO['lead_time_padrao'])

    st.subheader("Itens com Criticidade Alta, Instável ou Dados Insuficientes")
    criticos = pedido_alerta[pedido_alerta['Criticidade'] != '🟢 Ok']
    st.dataframe(criticos[['Item ID', 'Name', 'Estoque Atual', 'Cobertura Atual (dias)', 'Coeficiente Variação (%)', 'Qtd Registros', 'Criticidade']], use_container_width=True)

    st.subheader("Gráfico Quadrante: Cobertura vs Variabilidade")
    fig, ax = plt.subplots()
    colors = {'🔴 Crítico e Instável': 'red', '🟠 Crítico': 'orange', '🟡 Instável': 'yellow', '⚪️ Dados Insuficientes': 'grey', '🟢 Ok': 'green'}
    for crit, color in colors.items():
        subset = criticos[criticos['Criticidade'] == crit]
        ax.scatter(subset['Cobertura Atual (dias)'], subset['Coeficiente Variação (%)'], label=crit, color=color)
    ax.set_xlabel('Cobertura Atual (dias)')
    ax.set_ylabel('Coeficiente Variação (%)')
    ax.legend()
    st.pyplot(fig)

    st.subheader("Ranking de Consumo (Top 10)")
    ranking = pedido_alerta.sort_values(by='Consumo Médio Diário', ascending=False).head(10)
    fig, ax = plt.subplots()
    ax.bar(ranking['Name'], ranking['Consumo Médio Diário'], color='blue')
    ax.set_xlabel('Nome do Item')
    ax.set_ylabel('Consumo Médio Diário')
    ax.set_title('Top 10 Consumo Médio Diário')
    plt.xticks(rotation=45, ha='right')
    st.pyplot(fig)

# -------------------- RODAPÉ --------------------
st.markdown("---")
st.markdown("**COGEX ALMOXARIFADO - Motor Matemático Fuzzy Refinado | Powered by Streamlit**")
