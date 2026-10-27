# --- POCZĄTEK KODU ---
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import plotly.express as px
import io
import zipfile
from matplotlib.backends.backend_pdf import PdfPages

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
                st.error("Błąd: Wgrany plik lub zakładka nie zawiera kolumny 'Rok'.")
                st.stop()
                
        except Exception as e:
            st.error(f"Wystąpił błąd przy wczytywaniu pliku: {e}")
            st.stop()
            
    # --- FILTRY W PASKU BOCZNYM ---
    lata = df['Rok'].dropna().astype(int).unique()
    rok = st.sidebar.selectbox("Wybierz analizowany rok", sorted(lata, reverse=True))
    miesiac = st.sidebar.slider("Wybierz miesiąc zamknięcia (YTD)", 1, 12, 4)
    
    st.sidebar.markdown("---")
    pokaz_yoy = st.sidebar.checkbox("📊 Pokaż porównanie z ubiegłym rokiem (YoY)", value=False)
    podswietl_delivery = st.sidebar.checkbox("🎨 Wyróżnij jednostki Delivery (błękit)", value=False)
    wykresy_narastajaco = st.sidebar.checkbox("📈 Wykresy narastająco (Kumulacja YTD)", value=True)
    st.sidebar.markdown("---")
    
    # Filtr BU
    lista_bu = sorted(df['BU PwC'].dropna().astype(str).unique())
    wybrane_bu = st.sidebar.multiselect("Filtruj po BU", options=lista_bu, default=lista_bu)

    # LISTA KOSZTÓW GŁÓWNYCH (EBITDA)
    cost_lines = [
        'Total Cost of Goods Sold', 
        'Total Cost of Sales & Marketing',
        'Cost of General Administration', 
        'Cost of General Administration - Bonuses', 
        'Cost of General Administration - Change in reserves on bonuses',
        'Cost of General Administration - Pension provision and vacation accrual'
    ]
    
    # LISTA COMPENSATION COGS (Level 2)
    cogs_comp_lines = [
        'Cost of Goods Sold - Salaries & Social Security Tax',
        'Cost of Goods Sold - Bonuses'
    ]
    
    # LISTA BILLED REVENUE (Level 2)
    billed_rev_lines = [
        'Billed revenue'
    ]
    
    target_bus = ['BU BSS Delivery', 'BU OSS Delivery', 'BU Cross Services Delivery', 'BU IA&A Delivery', 'BU Smart BSS/IoT Connect']
    
    def highlight_delivery(row):
        if row.name in target_bus or 'Delivery Communication' in str(row.name):
            return ['background-color: #e6f2ff'] * len(row)
        return [''] * len(row)

    # Dane bieżące
    df_rok = df[df['Rok'] == rok]
    df_rok_filtered = df_rok[df_rok['BU PwC'].isin(wybrane_bu)]
    
    # Dane z ubiegłego roku (LY)
    df_ly = df[df['Rok'] == (rok - 1)]
    df_ly_filtered = df_ly[df_ly['BU PwC'].isin(wybrane_bu)]
    
    # --- FUNKCJE POMOCNICZE ---
    def calculate_ytd(data_subset, data_ly_subset, is_cost=False):
        ytd_act = data_subset[(data_subset['Miesiąc'] <= miesiac) & (data_subset['Rodzaj danych'] == 'ACT')].groupby('BU PwC')['Sum of Wartość'].sum()
        ytd_bgt = data_subset[(data_subset['Miesiąc'] <= miesiac) & (data
