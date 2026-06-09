import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

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
                # Sprawdzamy czy plik Excel ma zakładkę 'Stos danych'
                xl = pd.ExcelFile(uploaded_file)
                if 'Stos danych' in xl.sheet_names:
                    df = pd.read_excel(uploaded_file, sheet_name='Stos danych')
                else:
                    # Jeśli nie ma takiej nazwy, wczytaj pierwszą stronę
                    df = pd.read_excel(uploaded_file)
            
            # Dodatkowe zabezpieczenie: sprawdzenie czy mamy kolumnę "Rok"
            if 'Rok' not in df.columns:
                st.error("Błąd: Wgrany plik lub zakładka nie zawiera kolumny 'Rok'. Upewnij się, że wgrywasz zakładkę 'Stos danych'.")
                st.stop()
                
        except Exception as e:
            st.error(f"Wystąpił błąd przy wczytywaniu pliku: {e}")
            st.stop()
            
    # Filtry w pasku bocznym
    lata = df['Rok'].dropna().astype(int).unique()
    rok = st.sidebar.selectbox("Wybierz rok", sorted(lata, reverse=True))
    miesiac = st.sidebar.slider("Wybierz miesiąc zamknięcia (YTD)", 1, 12, 4)

    # Definicje linii P&L
    cost_lines = [
        'Total Cost of Goods Sold', 'Total Cost of Sales & Marketing',
        'Cost of General Administration', 'Depreciation & Amortization', 'Holding Cost',
        'Cost of General Administration - Bonuses', 'Cost of General Administration - Change in reserves on bonuses'
    ]
    
    df_rok = df[df['Rok'] == rok]
    
    # Funkcja pomocnicza do obliczeń YTD
    def calculate_ytd(data_subset, is_cost=False):
        ytd_act = data_subset[(data_subset['Miesiąc'] <= miesiac) & (data_subset['Rodzaj danych'] == 'ACT')].groupby('BU PwC')['Sum of Wartość'].sum()
        ytd_bgt = data_subset[(data_subset['Miesiąc'] <= miesiac) & (data_subset['Rodzaj danych'] == 'BGT')].groupby('BU PwC')['Sum of Wartość'].sum()
        
        if is_cost:
            ytd_act, ytd_bgt = ytd_act * -1, ytd_bgt * -1
            
        res = pd.DataFrame({'YTD ACT': ytd_act, 'YTD BGT': ytd_bgt}).fillna(0)
        # Usuwamy puste wiersze
        res = res[(res['YTD ACT'] != 0) | (res['YTD BGT'] != 0)]
        res['% Realizacji'] = (res['YTD ACT'] / res['YTD BGT']) * 100
        res['Odchylenie'] = res['YTD ACT'] - res['YTD BGT']
        return res.sort_values('YTD ACT', ascending=False)

    # Tworzymy 3 zakładki w aplikacji
    tab1, tab2, tab3 = st.tabs(["📉 Koszty", "📈 Przychody", "🚀 Delivery Communication"])

    with tab1:
        st.subheader(f"Wydatki Kosztowe (YTD do miesiąca {miesiac})")
        df_costs = df_rok[df_rok['Mapping P&L Line - level 1'].isin(cost_lines)]
        res_costs = calculate_ytd(df_costs, is_cost=True)
        
        st.dataframe(res_costs.style.format({
            'YTD ACT': '{:,.0f} PLN', 'YTD BGT': '{:,.0f} PLN', 
            'Odchylenie': '{:,.0f} PLN', '% Realizacji': '{:.1f}%'
        }).background_gradient(subset=['Odchylenie'], cmap='RdYlGn_r'))

    with tab2:
        st.subheader(f"Wykonanie Przychodów (YTD do miesiąca {miesiac})")
        df_rev = df_rok[df_rok['Mapping P&L Line - level 1'] == 'Total Revenue']
        res_rev = calculate_ytd(df_rev, is_cost=False)
        
        st.dataframe(res_rev.style.format({
            'YTD ACT': '{:,.0f} PLN', 'YTD BGT': '{:,.0f} PLN', 
            'Odchylenie': '{:,.0f} PLN', '% Realizacji': '{:.1f}%'
        }).background_gradient(subset=['Odchylenie'], cmap='RdYlGn')) # Tu na odwrót - na zielono jeśli na plusie

    with tab3:
        st.subheader("Skonsolidowany wynik: Delivery Communication")
        target_bus = ['BU BSS Delivery', 'BU OSS Delivery', 'BU Cross Services Delivery', 'BU IA&A Delivery', 'BU Smart BSS/IoT Connect']
        
        df_deliv = df_rok[df_rok['BU PwC'].isin(target_bus)].copy()
        df_deliv['BU PwC'] = 'Delivery Communication (SUMA)'
        
        df_deliv_costs = df_deliv[df_deliv['Mapping P&L Line - level 1'].isin(cost_lines)]
        df_deliv_rev = df_deliv[df_deliv['Mapping P&L Line - level 1'] == 'Total Revenue']
        
        c_res = calculate_ytd(df_deliv_costs, is_cost=True)
        r_res = calculate_ytd(df_deliv_rev, is_cost=False)
        
        col1, col2 = st.columns(2)
        with col1:
            st.info("KOSZTY")
            st.dataframe(c_res.style.format({'YTD ACT': '{:,.0f}', 'YTD BGT': '{:,.0f}', 'Odchylenie': '{:,.0f}', '% Realizacji': '{:.1f}%'}))
        with col2:
            st.success("PRZYCHODY")
            st.dataframe(r_res.style.format({'YTD ACT': '{:,.0f}', 'YTD BGT': '{:,.0f}', 'Odchylenie': '{:,.0f}', '% Realizacji': '{:.1f}%'}))

else:
    st.info("Czekam na wgranie pliku w panelu bocznym po lewej stronie 👈")
