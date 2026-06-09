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

    def get_monthly_trend(data_subset, is_cost=False, max_month=12):
        df_trend = data_subset[data_subset['Miesiąc'] <= max_month]
        if df_trend.empty:
            return pd.DataFrame()
        
        trend = df_trend.groupby(['Miesiąc', 'Rodzaj danych'])['Sum of Wartość'].sum().unstack(fill_value=0)
        
        if is_cost:
            trend = trend * -1
            
        for col in ['ACT', 'BGT']:
            if col not in trend.columns:
                trend[col] = 0
                
        trend = trend / 1e6 
        trend = trend[['ACT', 'BGT']]
        
        miesiące_nazwy = {1: 'Sty', 2: 'Lut', 3: 'Mar', 4: 'Kwi', 5: 'Maj', 6: 'Cze', 
                          7: 'Lip', 8: 'Sie', 9: 'Wrz', 10: 'Paź', 11: 'Lis', 12: 'Gru'}
        trend.index = trend.index.map(miesiące_nazwy)
        
        return trend

    # Funkcja rysująca wykres grupowany
    def draw_side_by_side_bar_chart(trend_data, title, is_cost=True):
        fig, ax = plt.subplots(figsize=(10, 3.5))
        x = np.arange(len(trend_data.index))
        width = 0.35
        
        color_act = '#2b5c8f'
        color_bgt = '#e28743'

        ax.bar(x - width/2, trend_data['ACT'], width, label='Wykonanie (ACT)', color=color_act)
        ax.bar(x + width/2, trend_data['BGT'], width, label='Budżet (BGT)', color=color_bgt)
        
        ax.set_ylabel('mln PLN', fontsize=9)
        ax.set_title(title, fontsize=11, fontweight='bold', color='#1a365d')
        ax.set_xticks(x)
        ax.set_xticklabels(trend_data.index, fontsize=9)
        ax.legend(fontsize=9)
        ax.grid(axis='y', linestyle='--', alpha=0.5)
        
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        
        plt.tight_layout()
        st.pyplot(fig)

    # Tworzymy 3 zakładki w aplikacji
    tab1, tab2, tab3 = st.tabs(["📉 Koszty", "📈 Przychody", "🚀 Delivery Communication"])

    with tab1:
        st.subheader(f"Wydatki Kosztowe (YTD do miesiąca {miesiac})")
        if wybrane_bu:
            df_costs = df_rok_filtered[df_rok_filtered['Mapping P&L Line - level 1'].isin(cost_lines)]
            res_costs = calculate_ytd(df_costs, is_cost=True)
            
            st.dataframe(res_costs.style.format({
                'YTD ACT': '{:,.0f} PLN', 'YTD BGT': '{:,.0f} PLN', 
                'Odchylenie': '{:,.0f} PLN', '% Realizacji': '{:.1f}%'
            }).background_gradient(subset=['Odchylenie'], cmap='RdYlGn_r'), use_container_width=True)
            
            st.divider()
            st.markdown("#### 📊 Miesięczna realizacja Kosztów (ACT vs BGT)")
            
            for bu in wybrane_bu:
                df_bu_costs = df_costs[df_costs['BU PwC'] == bu]
                trend_costs = get_monthly_trend(df_bu_costs, is_cost=True, max_month=miesiac)
                
                if not trend_costs.empty and (trend_costs.sum().sum() != 0):
                    draw_side_by_side_bar_chart(trend_costs, title=f"KOSZTY: {bu}", is_cost=True)
                else:
                    st.info(f"Brak kosztów do wyświetlenia dla: {bu}")
        else:
            st.warning("Wybierz przynajmniej jedno BU z panelu po lewej stronie.")

    with tab2:
        st.subheader(f"Wykonanie Przychodów (YTD do miesiąca {miesiac})")
        if wybrane_bu:
            df_rev = df_rok_filtered[df_rok_filtered['Mapping P&L Line - level 1'] == 'Total Revenue']
            res_rev = calculate_ytd(df_rev, is_cost=False)
            
            st.dataframe(res_rev.style.format({
                'YTD ACT': '{:,.0f} PLN', 'YTD BGT': '{:,.0f} PLN', 
                'Odchylenie': '{:,.0f} PLN', '% Realizacji': '{:.1f}%'
            }).background_gradient(subset=['Odchylenie'], cmap='RdYlGn'), use_container_width=True)
            
            st.divider()
            st.markdown("#### 📊 Miesięczna realizacja Przychodów (ACT vs BGT)")
            
            for bu in wybrane_bu:
                df_bu_rev = df_rev[df_rev['BU PwC'] == bu]
                trend_rev = get_monthly_trend(df_bu_rev, is_cost=False, max_month=miesiac)
                
                if not trend_rev.empty and (trend_rev.sum().sum() != 0):
                    draw_side_by_side_bar_chart(trend_rev, title=f"PRZYCHODY: {bu}", is_cost=False)
                else:
                    st.info(f"Brak przychodów do wyświetlenia dla: {bu}")
        else:
            st.warning("Wybierz przynajmniej jedno BU z panelu po lewej stronie.")

    with tab3:
        st.subheader("Skonsolidowany wynik: Delivery Communication")
        st.caption("Uwaga: Ten widok to z góry zdefiniowana suma 5 jednostek Delivery, globalny filtr BU go nie zmienia.")
        
        target_bus = ['BU BSS Delivery', 'BU OSS Delivery', 'BU Cross Services Delivery', 'BU IA&A Delivery', 'BU Smart BSS/IoT Connect']
        
        df_deliv = df_rok[df_rok['BU PwC'].isin(target_bus)].copy()
        df_deliv['BU PwC'] = 'Delivery Communication (SUMA)'
        
        df_deliv_costs = df_deliv[df_deliv['Mapping P&L Line - level 1'].isin(cost_lines)]
        df_deliv_rev = df_deliv[df_deliv['Mapping P&L Line - level 1'] == 'Total Revenue']
        
        c_res = calculate_ytd(df_deliv_costs, is_cost=True)
        r_res = calculate_ytd(df_deliv_rev, is_cost=False)
        
        col1, col2 = st.columns(2)
        with col1:
            st.info("KOSZTY (YTD)")
            st.dataframe(c_res.style.format({'YTD ACT': '{:,.0f}', 'YTD BGT': '{:,.0f}', 'Odchylenie': '{:,.0f}', '% Realizacji': '{:.1f}%'}))
            
            trend_deliv_
