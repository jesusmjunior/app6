import streamlit as st
import pandas as pd

# -------------------- CONFIGURAÇÕES INICIAIS --------------------
st.set_page_config(page_title="COGEX Almoxarifado", layout="wide")

st.title("📦 COGEX ALMOXARIFADO")
st.markdown("**Sistema Integrado Google Sheets - Pedido de Material Otimizado com Imagens e Filtros**")

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

# NOVA FUNÇÃO DE PEDIDO AJUSTADA
def gerar_pedido(cobertura_dias, estoque_minimo=0):
    consumo = calcular_consumo_medio(inventory_df)
    saldo = calcular_saldo_atual(inventory_df)

    pedido_df = pd.DataFrame()
    pedido_df['Consumo Médio Diário'] = consumo
    pedido_df['Estoque Atual'] = saldo
    pedido_df['Necessidade'] = (pedido_df['Consumo Médio Diário'] * cobertura_dias).round()
    pedido_df['Necessidade'] = pedido_df['Necessidade'] + estoque_minimo
    pedido_df['A Pedir'] = pedido_df.apply(lambda row: max(row['Necessidade'] - row['Estoque Atual'], 0), axis=1)
    pedido_df['Status'] = pedido_df['A Pedir'].apply(lambda x: 'Dentro do padrão' if x == 0 else 'Reposição necessária')
    pedido_df = pedido_df.reset_index()
    pedido_df = pd.merge(pedido_df, items_df[['Item ID', 'Name', 'Description', 'Image']], on='Item ID', how='left')
    return pedido_df

# -------------------- INTERFACE STREAMLIT --------------------
menu = st.sidebar.selectbox("Navegar", ["Pedido de Material", "Estoque Atual com Imagens", "Estatísticas"])

# -------------------- ABA PEDIDO DE MATERIAL --------------------
if menu == "Pedido de Material":
    st.header("📄 Pedido de Material Automático")
    dias = st.radio("Selecione a Cobertura (Dias):", [7, 15, 30, 45], horizontal=True)
    estoque_min = st.number_input("Estoque Mínimo de Segurança (opcional):", min_value=0, value=0)

    pedido = gerar_pedido(dias, estoque_min)
    st.subheader(f"Pedido de Material para {dias} dias de cobertura:")
    st.dataframe(pedido[['Item ID', 'Name', 'Estoque Atual', 'Necessidade', 'A Pedir', 'Status']], use_container_width=True)

    csv = pedido.to_csv(index=False).encode('utf-8')
    st.download_button("📥 Baixar Pedido CSV", data=csv, file_name=f'pedido_{dias}dias.csv', mime='text/csv')

# -------------------- ABA ESTOQUE ATUAL COM IMAGENS --------------------
elif menu == "Estoque Atual com Imagens":
    st.header("📊 Estoque Atual com Nome e Imagem")
    saldo = calcular_saldo_atual(inventory_df).reset_index()
    saldo.columns = ['Item ID', 'Saldo Atual']
    saldo = pd.merge(saldo, items_df[['Item ID', 'Name', 'Image']], on='Item ID', how='left')

    # Filtro por nome
    search_name = st.text_input("🔍 Buscar Produto pelo Nome:")
    if search_name:
        saldo = saldo[saldo['Name'].str.contains(search_name, case=False, na=False)]

    # Filtro para saldo negativo
    saldo_negativo = st.checkbox("Mostrar apenas itens com saldo negativo")
    if saldo_negativo:
        saldo = saldo[saldo['Saldo Atual'] < 0]

    for index, row in saldo.iterrows():
        st.write(f"**{row['Name']}** - Saldo Atual: {row['Saldo Atual']}")
        if pd.notna(row['Image']):
            st.image(row['Image'], width=150)

    # Download CSV
    csv_saldo = saldo.to_csv(index=False).encode('utf-8')
    st.download_button("📥 Baixar Estoque Filtrado CSV", data=csv_saldo, file_name='estoque_atual_filtrado.csv', mime='text/csv')

# -------------------- ABA ESTATÍSTICAS --------------------
elif menu == "Estatísticas":
    st.header("📈 Análises e Estatísticas")

    st.subheader("Saldo Atual por Item ID")
    saldo = calcular_saldo_atual(inventory_df).reset_index()
    saldo.columns = ['Item ID', 'Saldo Atual']
    saldo = pd.merge(saldo, items_df[['Item ID', 'Name']], on='Item ID', how='left')
    st.dataframe(saldo[['Item ID', 'Name', 'Saldo Atual']], use_container_width=True)

    st.subheader("Total de Movimentações Registradas")
    st.write(f"Total de registros no inventário: **{len(inventory_df)}**")

# -------------------- RODAPÉ --------------------
st.markdown("---")
st.markdown("**COGEX ALMOXARIFADO - Integração Google Sheets Otimizado | Powered by Streamlit**")
