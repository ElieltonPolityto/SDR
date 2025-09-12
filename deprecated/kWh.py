# kWh.py
# Comparativo de consumo energético – Máquina Step-In
# Degelo Inteligente (AIDA)  vs  Convencional
# Plotter Racks Refrigeração

import streamlit as st
import pandas as pd
import altair as alt
import os

# ─── 0. Configuração da página ───
st.set_page_config(page_title="Consumo camara congelados", layout="wide")

# ─── 1. Paleta de cores ───
COLOR_MODE = {"Com AIDA": "#3F72AF", "Sem AIDA": "#112D4E"}

# ─── 2. Arquivos ───
FILES = {
    "Com AIDA": r"C:\Users\elielton.polityto\Desktop\Relatorio_Muffato\AIDA\Relatorio_Muffato\Dados_27jul25\Dados\CSV\ConsumoComAIDA.xlsx",
    "Sem AIDA": r"C:\Users\elielton.polityto\Desktop\Relatorio_Muffato\AIDA\Relatorio_Muffato\Dados_27jul25\Dados\CSV\ConsumoSemAIDA.xlsx",
}

# ─── 3. Verificar existência ───
for nome, path in FILES.items():
    if not os.path.exists(path):
        st.error(f"Arquivo não encontrado: {path}")
        st.stop()

# ─── 4. Carregar dados ───
@st.cache_data
def load_file(label: str, path: str) -> pd.DataFrame:
    df = pd.read_excel(path, engine="openpyxl")

    # Primeira coluna → DataHora
    df = df.rename(columns={df.columns[0]: "DataHora"})

    # Detecta colunas kW e kWh por substring
    kw_col  = next((c for c in df.columns if "kw"  in c.lower() and "kwh" not in c.lower()), None)
    kwh_col = next((c for c in df.columns if "kwh" in c.lower()), None)
    if not kw_col or not kwh_col:
        raise ValueError(f"kW ou kWh não encontrados em '{label}'")

    df = df.rename(columns={kw_col: "kW", kwh_col: "kWh"})
    df["DataHora"] = pd.to_datetime(df["DataHora"], dayfirst=True, errors="coerce")
    df = df.dropna(subset=["DataHora"])
    df[["kW", "kWh"]] = df[["kW", "kWh"]].apply(pd.to_numeric, errors="coerce")
    df = df.dropna(subset=["kW", "kWh"]).set_index("DataHora").sort_index()

    # Dividir por 1.000
    df["kW"]  = df["kW"]  / 1_000
    df["kWh"] = df["kWh"] / 1_000

    # Zerar kWh acumulado
    df["kWh_Base0"] = df["kWh"] - df["kWh"].iloc[0]
    df["Sistema"] = label
    return df

# Carrega os dados
df_com = load_file("Com AIDA", FILES["Com AIDA"])
df_sem = load_file("Sem AIDA", FILES["Sem AIDA"])
df_all = pd.concat([df_com, df_sem])

# ─── 5. Totais de energia e economia (%) ───
E_com = df_com["kWh_Base0"].iloc[-1]
E_sem = df_sem["kWh_Base0"].iloc[-1]
economia_pct = (E_sem - E_com) / E_sem * 100 if E_sem else 0

# ─── 6. Métricas de topo ───
st.markdown("Consumo Câmara de congelados - Comparativo de 14 dias")
c1, c2, c3 = st.columns(3)
c1.metric("Energia Sem AIDA", f"{E_sem:,.2f} kWh")
c2.metric("Energia Com AIDA", f"{E_com:,.2f} kWh")
c3.metric("Economia Global",  f"{economia_pct:.1f} %")

st.caption(
    f"Sem AIDA: {df_sem.index.min().date()} → {df_sem.index.max().date()}  |  "
    f"Com AIDA: {df_com.index.min().date()} → {df_com.index.max().date()}"
)

# ─── 7. Potência instantânea ───
st.subheader("Potência Instantânea (kW)")
chart_kw = (
    alt.Chart(df_all.reset_index())
    .mark_line()
    .encode(
        x=alt.X("DataHora:T", title="Data e Hora"),
        y=alt.Y("kW:Q", title="kW"),
        color=alt.Color("Sistema:N", scale=alt.Scale(domain=list(COLOR_MODE),
                                                     range=list(COLOR_MODE.values())),
                        legend=alt.Legend(orient="top", direction="horizontal", title=None))
    )
    .properties(width=900, height=250)
)
st.altair_chart(chart_kw, use_container_width=False)

# ─── 8. Energia acumulada (base 0) ───
st.subheader("Energia Acumulada (kWh)")
chart_kwh = (
    alt.Chart(df_all.reset_index())
    .mark_line()
    .encode(
        x=alt.X("DataHora:T", title="Data e Hora"),
        y=alt.Y("kWh_Base0:Q", title="kWh acumulado"),
        color=alt.Color("Sistema:N", scale=alt.Scale(domain=list(COLOR_MODE),
                                                     range=list(COLOR_MODE.values())),
                        legend=alt.Legend(orient="top", direction="horizontal", title=None))
    )
    .properties(width=900, height=250)
)
st.altair_chart(chart_kwh, use_container_width=False)

