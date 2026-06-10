# --- POCZĄTEK KODU ---
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

    # POPRAWIONA (PIERWOTNA) LISTA KOSZTÓW
    cost_lines = [
        'Total Cost of Goods Sold', 
        'Total Cost of Sales & Marketing',
        'Cost of General Administration', 
        'Depreciation & Amortization', 
        'Holding Cost',
        'Cost of General Administration - Bonuses', 
        'Cost of General Administration - Change in reserves on bonuses',
        'Cost of General Administration - Pension provision and vacation accrual'
    ]
    
    salary_pattern = 'Salaries|Bonuses|vacation'
    
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
        ytd_bgt = data_subset[(data_subset['Miesiąc'] <= miesiac) & (data_subset['Rodzaj danych'] == 'BGT')].groupby('BU PwC')['Sum of Wartość'].sum()
        ytd_ly = data_ly_subset[(data_ly_subset['Miesiąc'] <= miesiac) & (data_ly_subset['Rodzaj danych'] == 'ACT')].groupby('BU PwC')['Sum of Wartość'].sum()
        
        if is_cost:
            ytd_act, ytd_bgt, ytd_ly = ytd_act * -1, ytd_bgt * -1, ytd_ly * -1
            
        res = pd.DataFrame({'YTD ACT': ytd_act, 'YTD BGT': ytd_bgt, 'YTD LY': ytd_ly}).fillna(0)
        res = res[(res['YTD ACT'] != 0) | (res['YTD BGT'] != 0) | (res['YTD LY'] != 0)]
        res['% Realizacji BGT'] = (res['YTD ACT'] / res['YTD BGT'].replace(0, np.nan)) * 100
        res['Odchylenie do BGT'] = res['YTD ACT'] - res['YTD BGT']
        
        if pokaz_yoy:
            res['Zmiana kwotowa YoY'] = res['YTD ACT'] - res['YTD LY']
            res['Dynamika YoY (%)'] = (res['YTD ACT'] / res['YTD LY'].replace(0, np.nan) - 1) * 100
            
        return res.sort_values('YTD ACT', ascending=False)

    def calculate_margin(data_rok, data_ly):
        df_costs = data_rok[data_rok['Mapping P&L Line - level 1'].isin(cost_lines)]
        df_rev = data_rok[data_rok['Mapping P&L Line - level 1'] == 'Total Revenue']
        df_costs_ly = data_ly[data_ly['Mapping P&L Line - level 1'].isin(cost_lines)]
        df_rev_ly = data_ly[data_ly['Mapping P&L Line - level 1'] == 'Total Revenue']
        
        res_costs = calculate_ytd(df_costs, df_costs_ly, is_cost=True)
        res_rev = calculate_ytd(df_rev, df_rev_ly, is_cost=False)
        
        margin = pd.DataFrame(index=res_rev.index.union(res_costs.index)).fillna(0)
        
        for col in ['YTD ACT', 'YTD BGT', 'YTD LY']:
            margin[f'Przychody {col}'] = res_rev[col] if col in res_rev.columns else 0
            margin[f'Koszty {col}'] = res_costs[col] if col in res_costs.columns else 0
            margin[f'Przychody {col}'] = margin[f'Przychody {col}'].fillna(0)
            margin[f'Koszty {col}'] = margin[f'Koszty {col}'].fillna(0)
            margin[f'Marża {col}'] = margin[f'Przychody {col}'] - margin[f'Koszty {col}']
            margin[f'Marża % {col}'] = (margin[f'Marża {col}'] / margin[f'Przychody {col}'].replace(0, np.nan)) * 100
            
        margin['Odchylenie Marży do BGT'] = margin['Marża YTD ACT'] - margin['Marża YTD BGT']
        if pokaz_yoy:
            margin['Zmiana Marży YoY'] = margin['Marża YTD ACT'] - margin['Marża YTD LY']
        
        return margin

    def get_monthly_trend(data_subset, data_ly_subset, is_cost=False, max_month=12):
        df_trend = data_subset[data_subset['Miesiąc'] <= max_month]
        df_trend_ly = data_ly_subset[data_ly_subset['Miesiąc'] <= max_month]
        
        trend = df_trend.groupby(['Miesiąc', 'Rodzaj danych'])['Sum of Wartość'].sum().unstack(fill_value=0) if not df_trend.empty else pd.DataFrame()
        trend_ly = df_trend_ly[df_trend_ly['Rodzaj danych'] == 'ACT'].groupby('Miesiąc')['Sum of Wartość'].sum() if not df_trend_ly.empty else pd.Series()
        
        if is_cost:
            trend = trend * -1
            trend_ly = trend_ly * -1
            
        for col in ['ACT', 'BGT']:
            if col not in trend.columns:
                trend[col] = 0
                
        trend['LY'] = trend_ly
        trend['LY'] = trend['LY'].fillna(0)
        
        trend = trend / 1e6 
        trend = trend[['ACT', 'BGT', 'LY']]
        
        all_months = list(range(1, max_month + 1))
        trend = trend.reindex(all_months).fillna(0)
        
        if wykresy_narastajaco:
            trend = trend.cumsum()
        
        miesiące_nazwy = {1: 'Sty', 2: 'Lut', 3: 'Mar', 4: 'Kwi', 5: 'Maj', 6: 'Cze', 
                          7: 'Lip', 8: 'Sie', 9: 'Wrz', 10: 'Paź', 11: 'Lis', 12: 'Gru'}
        trend.index = trend.index.map(miesiące_nazwy)
        
        return trend

    def draw_side_by_side_bar_chart(trend_data, title, is_cost=True):
        fig, ax = plt.subplots(figsize=(10, 3.5))
        x = np.arange(len(trend_data.index))
        
        color_act = '#2b5c8f'
        color_bgt = '#e28743'
        color_ly = '#a5b1c2'

        if pokaz_yoy:
            width = 0.25
            ax.bar(x - width, trend_data['LY'], width, label='Zeszły Rok (LY)', color=color_ly)
            ax.bar(x, trend_data['ACT'], width, label='Wykonanie (ACT)', color=color_act)
            ax.bar(x + width, trend_data['BGT'], width, label='Budżet (BGT)', color=color_bgt)
        else:
            width = 0.35
            ax.bar(x - width/2, trend_data['ACT'], width, label='Wykonanie (ACT)', color=color_act)
            ax.bar(x + width/2, trend_data['BGT'], width, label='Budżet (BGT)', color=color_bgt)
        
        ax.set_ylabel('mln PLN', fontsize=9)
        tytul_wykresu = f"{title} (Skumulowane YTD)" if wykresy_narastajaco else title
        ax.set_title(tytul_wykresu, fontsize=11, fontweight='bold', color='#1a365d')
        ax.set_xticks(x)
        ax.set_xticklabels(trend_data.index, fontsize=9)
        ax.legend(fontsize=9)
        ax.grid(axis='y', linestyle='--', alpha=0.5)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        
        plt.tight_layout()
        st.pyplot(fig)

    # Tworzymy 4 zakładki w aplikacji
    tab1, tab2, tab3, tab4 = st.tabs(["📉 Koszty", "📈 Przychody", "💰 Zyskowność", "🚀 Delivery Communication"])

    if pokaz_yoy:
        cols_std = ['YTD ACT', 'YTD BGT', '% Realizacji BGT', 'Odchylenie do BGT', 'YTD LY', 'Zmiana kwotowa YoY', 'Dynamika YoY (%)']
        format_std = {'YTD ACT': '{:,.0f}', 'YTD BGT': '{:,.0f}', 'YTD LY': '{:,.0f}', 'Odchylenie do BGT': '{:,.0f}', 'Zmiana kwotowa YoY': '{:,.0f}', '% Realizacji BGT': '{:.1f}%', 'Dynamika YoY (%)': '{:.1f}%'}
    else:
        cols_std = ['YTD ACT', 'YTD BGT', '% Realizacji BGT', 'Odchylenie do BGT']
        format_std = {'YTD ACT': '{:,.0f}', 'YTD BGT': '{:,.0f}', 'Odchylenie do BGT': '{:,.0f}', '% Realizacji BGT': '{:.1f}%'}

    with tab1:
        st.subheader(f"Wydatki Kosztowe - CAŁOŚĆ (YTD do miesiąca {miesiac})")
        if wybrane_bu:
            df_costs = df_rok_filtered[df_rok_filtered['Mapping P&L Line - level 1'].isin(cost_lines)]
            df_costs_ly = df_ly_filtered[df_ly_filtered['Mapping P&L Line - level 1'].isin(cost_lines)]
            
            res_costs = calculate_ytd(df_costs, df_costs_ly, is_cost=True)
            
            style_c = res_costs[cols_std].style.format(format_std)
            if podswietl_delivery:
                style_c = style_c.apply(highlight_delivery, axis=1)
            style_c = style_c.background_gradient(subset=['Odchylenie do BGT'], cmap='RdYlGn_r')
            
            st.dataframe(style_c, use_container_width=True)
            
            with st.expander("👀 Pokaż szczegóły: Koszty samych wypłat i premii (Wynagrodzenia)"):
                df_payroll = df_rok_filtered[df_rok_filtered['Mapping P&L Line - level 2'].str.contains(salary_pattern, case=False, na=False)]
                df_payroll_ly = df_ly_filtered[df_ly_filtered['Mapping P&L Line - level 2'].str.contains(salary_pattern, case=False, na=False)]
                
                res_payroll = calculate_ytd(df_payroll, df_payroll_ly, is_cost=True)
                if not res_payroll.empty:
                    style_p = res_payroll[cols_std].style.format(format_std)
                    if podswietl_delivery:
                        style_p = style_p.apply(highlight_delivery, axis=1)
                    style_p = style_p.background_gradient(subset=['Odchylenie do BGT'], cmap='RdYlGn_r')
                    st.dataframe(style_p, use_container_width=True)
                else:
                    st.info("Brak kosztów wynagrodzeń w wybranych jednostkach.")
            
            st.divider()
            for bu in wybrane_bu:
                df_bu_costs = df_costs[df_costs['BU PwC'] == bu]
                df_bu_costs_ly = df_costs_ly[df_costs_ly['BU PwC'] == bu]
                trend_costs = get_monthly_trend(df_bu_costs, df_bu_costs_ly, is_cost=True, max_month=miesiac)
                
                if not trend_costs.empty and (trend_costs.sum().sum() != 0):
                    draw_side_by_side_bar_chart(trend_costs, title=f"KOSZTY: {bu}", is_cost=True)
        else:
            st.warning("Wybierz przynajmniej jedno BU z panelu po lewej stronie.")

    with tab2:
        st.subheader(f"Wykonanie Przychodów (YTD do miesiąca {miesiac})")
        if wybrane_bu:
            df_rev = df_rok_filtered[df_rok_filtered['Mapping P&L Line - level 1'] == 'Total Revenue']
            df_rev_ly = df_ly_filtered[df_ly_filtered['Mapping P&L Line - level 1'] == 'Total Revenue']
            
            res_rev = calculate_ytd(df_rev, df_rev_ly, is_cost=False)
            
            style_r = res_rev[cols_std].style.format(format_std)
            if podswietl_delivery:
                style_r = style_r.apply(highlight_delivery, axis=1)
            style_r = style_r.background_gradient(subset=['Odchylenie do BGT'], cmap='RdYlGn')
            
            st.dataframe(style_r, use_container_width=True)
            
            st.divider()
            for bu in wybrane_bu:
                df_bu_rev = df_rev[df_rev['BU PwC'] == bu]
                df_bu_rev_ly = df_rev_ly[df_rev_ly['BU PwC'] == bu]
                trend_rev = get_monthly_trend(df_bu_rev, df_bu_rev_ly, is_cost=False, max_month=miesiac)
                
                if not trend_rev.empty and (trend_rev.sum().sum() != 0):
                    draw_side_by_side_bar_chart(trend_rev, title=f"PRZYCHODY: {bu}", is_cost=False)
        else:
            st.warning("Wybierz przynajmniej jedno BU z panelu po lewej stronie.")

    with tab3:
        st.subheader(f"Kalkulacja Zyskowności / Marży (YTD do miesiąca {miesiac})")
        if wybrane_bu:
            margin_df = calculate_margin(df_rok_filtered, df_ly_filtered)
            
            if pokaz_yoy:
                cols_margin = ['Przychody YTD ACT', 'Koszty YTD ACT', 'Marża YTD ACT', 'Marża YTD BGT', 'Marża YTD LY', 'Marża % YTD ACT', 'Marża % YTD BGT', 'Marża % YTD LY', 'Odchylenie Marży do BGT', 'Zmiana Marży YoY']
            else:
                cols_margin = ['Przychody YTD ACT', 'Koszty YTD ACT', 'Marża YTD ACT', 'Marża YTD BGT', 'Marża % YTD ACT', 'Marża % YTD BGT', 'Odchylenie Marży do BGT']
                
            format_margin = {
                'Przychody YTD ACT': '{:,.0f}', 'Koszty YTD ACT': '{:,.0f}',
                'Marża YTD ACT': '{:,.0f}', 'Marża YTD BGT': '{:,.0f}', 'Marża YTD LY': '{:,.0f}',
                'Marża % YTD ACT': '{:.1f}%', 'Marża % YTD BGT': '{:.1f}%', 'Marża % YTD LY': '{:.1f}%',
                'Odchylenie Marży do BGT': '{:,.0f}', 'Zmiana Marży YoY': '{:,.0f}'
            }
            
            style_m = margin_df[cols_margin].style.format(format_margin)
            if podswietl_delivery:
                style_m = style_m.apply(highlight_delivery, axis=1)
            style_m = style_m.background_gradient(subset=['Odchylenie Marży do BGT'], cmap='RdYlGn')
            
            st.dataframe(style_m, use_container_width=True)
        else:
            st.warning("Wybierz przynajmniej jedno BU z panelu po lewej stronie.")

    with tab4:
        st.subheader("Skonsolidowany wynik: Delivery Communication")
        st.caption("Uwaga: Ten widok to z góry zdefiniowana suma 5 jednostek Delivery.")
        
        df_deliv = df_rok[df_rok['BU PwC'].isin(target_bus)].copy()
        df_deliv['BU PwC'] = 'Delivery Communication (SUMA)'
        df_deliv_ly = df_ly[df_ly['BU PwC'].isin(target_bus)].copy()
        df_deliv_ly['BU PwC'] = 'Delivery Communication (SUMA)'
        
        df_deliv_costs = df_deliv[df_deliv['Mapping P&L Line - level 1'].isin(cost_lines)]
        df_deliv_costs_ly = df_deliv_ly[df_deliv_ly['Mapping P&L Line - level 1'].isin(cost_lines)]
        df_deliv_rev = df_deliv[df_deliv['Mapping P&L Line - level 1'] == 'Total Revenue']
        df_deliv_rev_ly = df_deliv_ly[df_deliv_ly['Mapping P&L Line - level 1'] == 'Total Revenue']
        
        c_res = calculate_ytd(df_deliv_costs, df_deliv_costs_ly, is_cost=True)
        r_res = calculate_ytd(df_deliv_rev, df_deliv_rev_ly, is_cost=False)
        
        col1, col2 = st.columns(2)
        with col1:
            st.info("KOSZTY (YTD)")
            style_deliv_c = c_res[cols_std].style.format(format_std)
            if podswietl_delivery:
                style_deliv_c = style_deliv_c.apply(highlight_delivery, axis=1)
            st.dataframe(style_deliv_c)
            
            with st.expander("👀 Pokaż szczegóły: Koszty samych wypłat i premii"):
                df_deliv_payroll = df_deliv[df_deliv['Mapping P&L Line - level 2'].str.contains(salary_pattern, case=False, na=False)]
                df_deliv_payroll_ly = df_deliv_ly[df_deliv_ly['Mapping P&L Line - level 2'].str.contains(salary_pattern, case=False, na=False)]
                res_deliv_payroll = calculate_ytd(df_deliv_payroll, df_deliv_payroll_ly, is_cost=True)
                if not res_deliv_payroll.empty:
                    st.dataframe(res_deliv_payroll[cols_std].style.format(format_std).background_gradient(subset=['Odchylenie do BGT'], cmap='RdYlGn_r'))
            
            trend_deliv_costs = get_monthly_trend(df_deliv_costs, df_deliv_costs_ly, is_cost=True, max_month=miesiac)
            if not trend_deliv_costs.empty:
                 draw_side_by_side_bar_chart(trend_deliv_costs, title="KOSZTY: Delivery (Skonsolidowane)", is_cost=True)
                 
        with col2:
            st.success("PRZYCHODY (YTD)")
            style_deliv_r = r_res[cols_std].style.format(format_std)
            if podswietl_delivery:
                style_deliv_r = style_deliv_r.apply(highlight_delivery, axis=1)
            st.dataframe(style_deliv_r)
            
            trend_deliv_rev = get_monthly_trend(df_deliv_rev, df_deliv_rev_ly, is_cost=False, max_month=miesiac)
            if not trend_deliv_rev.empty:
                 draw_side_by_side_bar_chart(trend_deliv_rev, title="PRZYCHODY: Delivery (Skonsolidowane)", is_cost=False)

else:
    st.info("Czekam na wgranie pliku w panelu bocznym po lewej stronie 👈")
# --- KONIEC KODU ---
