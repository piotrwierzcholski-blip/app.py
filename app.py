import streamlit as st
import pandas as pd
import numpy as np

# Konfiguracja wyglądu strony
st.set_page_config(page_title="Raporty Finansowe BU", layout="wide")
st.title("📊 Interaktywny Raport Finansowy BU")
st.markdown("Wgraj wyeksportowany plik z systemu, aby natychmiast przeliczyć realizację budżetu.")

# Pasek boczny
st.sidebar.header("Ustawienia Panelu")
uploaded_file = st.sidebar.file_uploader("Wgraj plik ze 'Stosem danych' (CSV/XLSX)", type=['csv', 'xlsx'])

if uploaded_file is not None:
    # Wczytywanie danych
    with st.spinner("Przetwarzanie danych..."):
        try:
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file)
            else:
                xl = pd.ExcelFile(uploaded_file)
                if 'Stos danych' in xl.sheet_names:
                    df = pd.read_excel(uploaded_file, sheet_name='Stos danych')
                else:
                    df = pd.read_excel(uploaded_file)
            
            if 'Rok' not in df.columns:
                st.error("Błąd: Wgrany plik lub zakładka nie zawiera kolumny 'Rok'. Upewnij się, że wgrywasz zakładkę 'Stos danych'.")
                st.stop()
                
        except Exception as e:
            st.error(f"Wystąpił błąd przy wczytywaniu pliku: {e}")
            st.stop()
            
    # --- FILTRY W PASKU BOCZNYM ---
    lata = df['Rok'].dropna().astype(int).unique()
    rok = st.sidebar.selectbox("Wybierz rok", sorted(lata, reverse=True))
    miesiac = st.sidebar.slider("Wybierz miesiąc zamknięcia (YTD)", 1, 12, 4)
    
    # Filtr BU
    lista_bu = sorted(df['BU PwC'].dropna().astype(str).unique())
    wybrane_bu = st.sidebar.multiselect("Filtruj po BU", options=lista_bu, default=lista_bu)

    # Definicje linii P&L
    cost_lines = [
        'Total Cost of Goods Sold', 'Total Cost of Sales & Marketing',
        'Cost of General Administration', 'Depreciation & Amortization', 'Holding Cost',
        'Cost of General Administration - Bonuses', 'Cost of General Administration - Change in reserves on bonuses'
    ]
    
    df_rok = df[df['Rok'] == rok]
    df_rok_filtered = df_rok[df_rok['BU PwC'].isin(wybrane_bu)]
    
    # --- FUNKCJE POMOCNICZE ---
    def calculate_ytd(data_subset, is_cost=False):
        ytd_act = data_subset[(data_subset['Miesiąc'] <= miesiac) & (data_subset['Rodzaj danych'] == 'ACT')].groupby('BU PwC')['Sum of Wartość'].sum()
        ytd_bgt = data_subset[(data_subset['Miesiąc'] <= miesiac) & (data_subset['Rodzaj danych'] == 'BGT')].groupby('BU PwC')['Sum of Wartość'].sum()
        
        if is_cost:
            ytd_act, ytd_bgt = ytd_act * -1, ytd_bgt * -1
            
        res = pd.DataFrame({'YTD ACT': ytd_act, 'YTD BGT': ytd_bgt}).fillna(0)
        res = res[(res['YTD ACT'] != 0) | (res['YTD BGT'] != 0)]
        res['% Realizacji'] = (res['YTD ACT'] / res['YTD BGT']) * 100
        res['Odchylenie'] = res['YTD ACT'] - res['YTD BGT']
        return res.sort_values('YTD ACT', ascending=False)

    # Nowa funkcja przygotowująca dane miesięczne do wykresu
    def get_monthly_trend(data_subset, is_cost=False, max_month=12):
        df_trend = data_subset[data_subset['Miesiąc'] <= max_month]
        if df_trend.empty:
            return pd.DataFrame()
        
        # Grupujemy po miesiącach i rodzaju danych (ACT/BGT)
        trend = df
