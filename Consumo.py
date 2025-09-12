# Consumo.py
# Comparativo de capacidade de compressão com e sem degelo inteligente
# Plotter Racks Refrigeração — apresentação para diretoria

import streamlit as st
import pandas as pd
import altair as alt
import os

# ─── 0. CONFIGURAÇÃO DA PÁGINA ────────────────────────────────────────────────
st.set_page_config(
    page_title="AIDA - Resultados Camara de Congelados",
    layout="wide"
)

# ─── 1. DEFINIÇÕES GLOBAIS ────────────────────────────────────────────────────
COLOR_SYS = {
    "Com degelo inteligente": "#3F72AF",
    "Sem degelo inteligente":   "#112D4E"
}
COLOR_ECON = "#FCA311"

ARQUIVOS = {
    "Com degelo inteligente":    r"C:\Users\elielton.polityto\Desktop\Relatorio_Muffato\AIDA\Relatorio_Muffato\Dados_27jul25\Dados\CSV\CamCong2.xlsx",
    "Sem degelo inteligente":    r"C:\Users\elielton.polityto\Desktop\Relatorio_Muffato\AIDA\Relatorio_Muffato\Dados_27jul25\Dados\CSV\CamCong2_SEM_AIDA.xlsx",
}

# ─── 2. VERIFICAÇÃO DE ARQUIVOS ───────────────────────────────────────────────
ARQ_OK = {k: v for k, v in ARQUIVOS.items() if os.path.exists(v)}
for nome in ARQUIVOS:
    if nome not in ARQ_OK:
        st.warning(f"Não encontrado: {ARQUIVOS[nome]}")
if not ARQ_OK:
    st.error("Nenhum arquivo válido. Verifique os caminhos.")
    st.stop()

# ─── 3. CARREGAMENTO E PREPARAÇÃO ─────────────────────────────────────────────
@st.cache_data
def load_and_prepare(paths):
    all_dfs = []
    for sistema, path in paths.items():
        df = pd.read_excel(path, engine="openpyxl")
        # Detecta coluna de data/hora
        dtcol = next((c for c in df.columns if "Data" in c or "Hora" in c), None)
        if dtcol is None:
            st.error(f"Coluna de data/hora não encontrada em '{sistema}'")
            st.stop()
        # Renomeia e converte
        df = df.rename(columns={
            dtcol:        "DataHora",
            "Comp Cap 1": "CapComp",
            "degelo":     "Degelo",
            "Temp Amb 1": "TempAmb"
        })
        df["DataHora"] = pd.to_datetime(df["DataHora"], dayfirst=True, errors="coerce")
        df = df.dropna(subset=["DataHora"])
        df["Sistema"] = sistema
        all_dfs.append(df[["DataHora","Sistema","CapComp","Degelo","TempAmb"]])
    # Concatena tudo e indexa por tempo
    return pd.concat(all_dfs).set_index("DataHora").sort_index()

df = load_and_prepare(ARQ_OK)

# ─── 4. DETECÇÃO DE EVENTOS DE DEGELO ────────────────────────────────────────
df["DegAnt"]       = df["Degelo"].shift(1).fillna(0)
df["InicioDegelo"] = (df["DegAnt"] == 0) & (df["Degelo"] == 1)
df["Dia"]          = df.index.date
df_events = df[df["InicioDegelo"]]

# ─── 5. FILTRO PELO SISTEMA SELECIONADO ──────────────────────────────────────
sistemas = st.sidebar.multiselect(
    "Selecione o sistema",
    options=list(ARQ_OK.keys()),
    default=list(ARQ_OK.keys())
)
if not sistemas:
    st.error("Selecione ao menos um sistema.")
    st.stop()

df_sel        = df[df["Sistema"].isin(sistemas)]
df_events_sel = df_events[df_events["Sistema"].isin(sistemas)]

# ─── 6. CÁLCULO DE MÉTRICAS PRINCIPAIS ───────────────────────────────────────
# 6.1. Quantidade de ciclos de degelo por dia
deg_per_day = df_events_sel.groupby(["Sistema","Dia"]).size().rename("QtdDegelo")
# 6.2. Capacidade média excluindo períodos de degelo
cap_media_no_deg = (
    df_sel[df_sel["Degelo"] == 0]
    .groupby(["Sistema","Dia"])["CapComp"]
    .mean()
    .rename("CapMedia")
)

# ─── 7. RESUMO EXECUTIVO (TABELA) ─────────────────────────────────────────────
st.header("Resumo Comparativo - Cam Congelados")
summary = pd.concat([
    deg_per_day.groupby("Sistema").mean().rename("Média Degelos/dia"),
    cap_media_no_deg.groupby("Sistema").mean().rename("Média Capacidade (%)")
], axis=1)
st.table(summary.style.format("{:.2f}"))

# ─── 8. VISÕES GRÁFICAS — SEQUÊNCIA LÓGICA ────────────────────────────────────

# 8.1 Capacidade vs início de degelo
st.subheader("1) Capacidade x Eventos de Degelo")
chart1 = (
    alt.Chart(df_sel.reset_index())
      .mark_line()
      .encode(
          x=alt.X("DataHora:T", title="Data", axis=alt.Axis(format="%a %d")),
          y=alt.Y("CapComp:Q", title="Capacidade (kW)"),
          color=alt.Color(
              "Sistema:N",
              scale=alt.Scale(domain=list(COLOR_SYS), range=list(COLOR_SYS.values())),
              legend=alt.Legend(orient="top", direction="horizontal", title=None)
          )
      )
      .properties(width=800, height=300)
)
points1 = (
    alt.Chart(df_events_sel.reset_index())
      .mark_circle(size=40, color=COLOR_ECON)
      .encode(x="DataHora:T", y="CapComp:Q")
)
st.altair_chart(chart1 + points1, use_container_width=False)

# 8.2 Degelos por dia
st.subheader("2) Frequência de Degelos por Dia")
chart2 = (
    alt.Chart(deg_per_day.reset_index())
      .mark_bar()
      .encode(
          x=alt.X("Dia:T", title="Dia", axis=alt.Axis(format="%a %d")),
          y=alt.Y("QtdDegelo:Q", title="Ciclos Degelo/dia", scale=alt.Scale(domain=[0,4])),
          color=alt.Color(
              "Sistema:N",
              scale=alt.Scale(domain=list(COLOR_SYS), range=list(COLOR_SYS.values())),
              legend=alt.Legend(orient="top", direction="horizontal", title=None)
          )
      )
      .properties(width=800, height=250)
)
st.altair_chart(chart2, use_container_width=False)

# 8.3 Capacidade média sem degelo
st.subheader("3) Capacidade Média por Dia (sem degelo)")
chart3 = (
    alt.Chart(cap_media_no_deg.reset_index())
      .mark_line(point=True)
      .encode(
          x=alt.X("Dia:T", title="Dia", axis=alt.Axis(format="%a %d")),
          y=alt.Y("CapMedia:Q", title="Capacidade Média (%)"),
          color=alt.Color(
              "Sistema:N",
              scale=alt.Scale(domain=list(COLOR_SYS), range=list(COLOR_SYS.values())),
              legend=alt.Legend(orient="top", direction="horizontal", title=None)
          )
      )
      .properties(width=800, height=250)
)
st.altair_chart(chart3, use_container_width=False)

# 8.4 Correlação Degelos × Capacidade
st.subheader("4) Correlação: Ciclos Degelo × Capacidade Média")
df_corr = pd.concat([deg_per_day, cap_media_no_deg], axis=1).dropna()
df_corr.columns = ["QtdDegelo","CapMedia"]
chart4 = (
    alt.Chart(df_corr.reset_index())
      .mark_circle(size=80)
      .encode(
          x=alt.X(
              "QtdDegelo:Q",
              title="Degelos/dia",
              scale=alt.Scale(domain=[1,4], nice=False),
              axis=alt.Axis(values=[1,2,3,4], format="d")
          ),
          y=alt.Y("CapMedia:Q", title="Capacidade Média (kW)"),
          color=alt.Color(
              "Sistema:N",
              scale=alt.Scale(domain=list(COLOR_SYS), range=list(COLOR_SYS.values())),
              legend=alt.Legend(orient="top", direction="horizontal", title=None)
          )
      )
      .properties(width=800, height=300)
)
st.altair_chart(chart4, use_container_width=False)

# 8.5 Tendência no Tempo: TempAmb vs CapComp
st.subheader("5) Tendência: Temperatura Ambiente vs Capacidade")
df_fold = df_sel.reset_index()[["DataHora","Sistema","TempAmb","CapComp"]]
chart5 = (
    alt.Chart(df_fold)
      .transform_fold(["TempAmb","CapComp"], as_=["Variável","Valor"])
      .mark_line()
      .encode(
          x=alt.X("DataHora:T", title="Data", axis=alt.Axis(format="%a %d")),
          y=alt.Y("Valor:Q", title="Valor"),
          color=alt.Color(
              "Variável:N",
              scale=alt.Scale(domain=["TempAmb","CapComp"], range=[COLOR_SYS["Sem degelo inteligente"], COLOR_SYS["Com degelo inteligente"]]),
              legend=alt.Legend(orient="top", title="")
          ),
          strokeDash=alt.StrokeDash("Variável:N")
      )
      .properties(width=800, height=300)
)
st.altair_chart(chart5, use_container_width=False)

# ─── FIM: Insights e Próximos Passos ──────────────────────────────────────────
st.markdown("""
**Conclusão:**  
O sistema com AIDA executou menos ciclos de degelo, reduzindo em média de 4 para 1,87 ciclos por dia.

Com  da redução de ciclos, a capacidade média do compressor diminuiu em torno de 6%

Diminuir a frequência de degelos não impactou negativamente o desempenho do sistema

**Próximos passos:**  
1. Aplicar sistema na instlação Atacadão Boa Vista  

""")