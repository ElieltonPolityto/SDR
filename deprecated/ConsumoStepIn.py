# Consumo step in.py
# Apresentação comparativa de eficiência (%) e economia de energia
# Sistema Step-In com e sem AIDA — Plotter Racks Refrigeração

import streamlit as st
import pandas as pd
import altair as alt
import os

# ─── 0. Configuração da página ───────────────────────────────────────────────
st.set_page_config(
    page_title="Step-In: Degelo Inteligente vs Sem AIDA",
    layout="wide"
)

# ─── 1. Paleta de cores ───────────────────────────────────────────────────────
COLOR_SYS = {
    "Com degelo inteligente": "#3F72AF",
    "Sem degelo inteligente":   "#112D4E"
}
COLOR_ECON = "#FCA311"

# ─── 2. Arquivos Step-In ──────────────────────────────────────────────────────
FILES = {
    "Com degelo inteligente": r"C:\Users\elielton.polityto\Desktop\Relatorio_Muffato\AIDA\Relatorio_Muffato\Dados_27jul25\Dados\CSV\StepIn2.xlsx",
    "Sem degelo inteligente": r"C:\Users\elielton.polityto\Desktop\Relatorio_Muffato\AIDA\Relatorio_Muffato\Dados_27jul25\Dados\CSV\StepIn2_SEM_AIDA.xlsx",
}

# ─── 3. Verificação de existência ─────────────────────────────────────────────
ARQ_OK = {k: v for k, v in FILES.items() if os.path.exists(v)}
if not ARQ_OK:
    for nome, path in FILES.items():
        if nome not in ARQ_OK:
            st.error(f"Arquivo não encontrado: {path}")
    st.stop()

# ─── 4. Carregamento e mapeamento ─────────────────────────────────────────────
@st.cache_data
def load_data(paths):
    dfs = []
    for sistema, path in paths.items():
        df = pd.read_excel(path, engine="openpyxl")
        df.columns = df.columns.str.strip()

        # 4.1 detectar coluna de data/hora
        dt_col = next((c for c in df.columns if "data" in c.lower()), None)
        if not dt_col:
            raise ValueError(f"Coluna de data não encontrada em '{sistema}'")
        df = df.rename(columns={dt_col: "DataHora"})

        # 4.2 mapeamento por substring
        mapping = {
            "comp cap":        "CapComp1",
            "degelo 1":        "Degelo1",
            "temp ambiente 1": "TempAmb1",
            "degelo 2":        "Degelo2",
            "temp ambiente 2": "TempAmb2",
        }
        rename = {}
        for key, new in mapping.items():
            col = next((c for c in df.columns if key in c.lower()), None)
            if col is None:
                raise ValueError(f"Coluna contendo '{key}' não encontrada em '{sistema}'")
            rename[col] = new
        df = df.rename(columns=rename)

        # 4.3 converter DataHora e filtrar inválidos
        df["DataHora"] = pd.to_datetime(df["DataHora"], dayfirst=True, errors="coerce")
        df = df.dropna(subset=["DataHora"])
        df["Sistema"] = sistema
        dfs.append(df)

    return pd.concat(dfs).set_index("DataHora").sort_index()

df = load_data(ARQ_OK)

# ─── 5. Conversão de tipos ────────────────────────────────────────────────────
for col in ["CapComp1", "Degelo1", "TempAmb1", "Degelo2", "TempAmb2"]:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

# ─── 6. Detectar início de degelo (0 → 1) ────────────────────────────────────
for deg in ["Degelo1", "Degelo2"]:
    if deg in df.columns:
        df[f"{deg}_ant"] = df[deg].shift(1).fillna(0)
        df[f"{deg}_ini"] = (df[f"{deg}_ant"] == 0) & (df[deg] == 1)

df["Dia"] = df.index.date

# ─── 7. Seleção de sistema ────────────────────────────────────────────────────
sistemas = st.sidebar.multiselect(
    "Selecione o sistema",
    options=list(ARQ_OK.keys()),
    default=list(ARQ_OK.keys())
)
if not sistemas:
    st.stop()
df = df[df["Sistema"].isin(sistemas)]

# ─── 8. Cálculo de métricas ──────────────────────────────────────────────────
# Evaporador 1
evt1     = df[df["Degelo1_ini"]]
deg1_day = evt1.groupby(["Sistema", "Dia"]).size().rename("QtdDeg1")

# **Capacidade média EXCLUINDO todos os instantes em que Degelo1 == 1**
cap1_no  = (
    df[df["Degelo1"] == 0]                      # filtra apenas momentos sem degelo
    .groupby(["Sistema", "Dia"])["CapComp1"]    # agrupa
    .mean()                                     # calcula média
    .rename("Cap1Media")
)

# Evaporador 2
evt2     = df[df["Degelo2_ini"]]
deg2_day = evt2.groupby(["Sistema", "Dia"]).size().rename("QtdDeg2")

# **Capacidade média EXCLUINDO todos os instantes em que Degelo2 == 1**
cap2_no  = (
    df[df["Degelo2"] == 0]
    .groupby(["Sistema", "Dia"])["CapComp1"]
    .mean()
    .rename("Cap2Media")
)

# ─── 9. Resumo executivo ──────────────────────────────────────────────────────
st.header("Resumo Step-In")
summary = pd.concat([
    deg1_day.groupby("Sistema").mean().rename("Média Deg1/dia"),
    cap1_no.groupby("Sistema").mean().rename("Média Cap1 (%)"),
    deg2_day.groupby("Sistema").mean().rename("Média Deg2/dia"),
    cap2_no.groupby("Sistema").mean().rename("Média Cap2 (%)")
], axis=1)
st.table(summary.style.format("{:.2f}"))

# ─── 10. Gráficos — sequência lógica ──────────────────────────────────────────
def plot_evaporador(idx, deg_day, cap_no, evt):
    # 1) Capacidade (%) vs início de degelo
    st.subheader(f"Evaporador {idx}: Capacidade (%) vs Início de Degelo")
    base = (
        alt.Chart(df.reset_index())
        .mark_line()
        .encode(
            x=alt.X("DataHora:T", axis=alt.Axis(format="%a %d")),
            y=alt.Y("CapComp1:Q", title="Capacidade (%)"),
            color=alt.Color("Sistema:N",
                            scale=alt.Scale(domain=list(COLOR_SYS), range=list(COLOR_SYS.values())),
                            legend=alt.Legend(orient="top", direction="horizontal", title=None))
        )
        .properties(width=800, height=250)
    )
    points = (
        alt.Chart(evt.reset_index())
        .mark_circle(size=40, color=COLOR_ECON)
        .encode(x="DataHora:T", y="CapComp1:Q")
    )
    st.altair_chart(base + points, use_container_width=False)

    # 2) Degelos por dia
    st.subheader(f"Evaporador {idx}: Degelos por Dia")
    ch1 = (
        alt.Chart(deg_day.reset_index())
        .mark_bar()
        .encode(
            x=alt.X("Dia:T", axis=alt.Axis(format="%a %d")),
            y=alt.Y(f"QtdDeg{idx}:Q", title="Ciclos Degelo/dia"),
            color=alt.Color("Sistema:N",
                            scale=alt.Scale(domain=list(COLOR_SYS), range=list(COLOR_SYS.values())),
                            legend=alt.Legend(orient="top", direction="horizontal", title=None))
        )
        .properties(width=800, height=200)
    )
    st.altair_chart(ch1, use_container_width=False)

    # 3) Capacidade média por dia (sem degelo)
    st.subheader(f"Evaporador {idx}: Capacidade Média por Dia (sem degelo) (%)")
    ch2 = (
        alt.Chart(cap_no.reset_index())
        .mark_line(point=True)
        .encode(
            x=alt.X("Dia:T", axis=alt.Axis(format="%a %d")),
            y=alt.Y(f"{cap_no.name}:Q", title="Média Capacidade (%)"),
            color=alt.Color("Sistema:N",
                            scale=alt.Scale(domain=list(COLOR_SYS), range=list(COLOR_SYS.values())),
                            legend=alt.Legend(orient="top", direction="horizontal", title=None))
        )
        .properties(width=800, height=200)
    )
    st.altair_chart(ch2, use_container_width=False)

    # 4) Correlação degelos × capacidade média
    st.subheader(f"Evaporador {idx}: Correlação Ciclos Degelo × Capacidade Média (%)")
    dfc = pd.concat([deg_day, cap_no], axis=1).dropna()
    dfc.columns = [f"QtdDeg{idx}", cap_no.name]
    ch3 = (
        alt.Chart(dfc.reset_index())
        .mark_circle(size=80)
        .encode(
            x=alt.X(
                f"QtdDeg{idx}:Q",
                title="Degelos/dia",
                scale=alt.Scale(domain=[1, 4], nice=False),
                axis=alt.Axis(values=[1, 2, 3, 4], format="d")
            ),
            y=alt.Y(f"{cap_no.name}:Q", title="Média Capacidade (%)"),
            color=alt.Color("Sistema:N",
                            scale=alt.Scale(domain=list(COLOR_SYS), range=list(COLOR_SYS.values())),
                            legend=alt.Legend(orient="top", direction="horizontal", title=None))
        )
        .properties(width=800, height=300)
    )
    st.altair_chart(ch3, use_container_width=False)

plot_evaporador(1, deg1_day, cap1_no, evt1)
plot_evaporador(2, deg2_day, cap2_no, evt2)

# ─── 11. Tendência no tempo ──────────────────────────────────────────────────
st.subheader("Temperatura e Capacidade ao Longo do Tempo")
dfm = df.reset_index()[["DataHora", "Sistema", "TempAmb1", "CapComp1"]]
fold = (
    alt.Chart(dfm)
    .transform_fold(["TempAmb1", "CapComp1"], as_=["Variável", "Valor"])
    .mark_line()
    .encode(
        x=alt.X("DataHora:T", axis=alt.Axis(format="%a %d")),
        y=alt.Y("Valor:Q", title="Valor"),
        color=alt.Color("Variável:N",
                        scale=alt.Scale(
                            domain=["TempAmb1", "CapComp1"],
                            range=[COLOR_SYS["Sem degelo inteligente"], COLOR_SYS["Com degelo inteligente"]]
                        ),
                        legend=alt.Legend(orient="top", title="")
        ),
        strokeDash=alt.StrokeDash("Variável:N")
    )
    .properties(width=800, height=300)
)
st.altair_chart(fold, use_container_width=False)

# ─── FIM: Insights e Próximos Passos ──────────────────────────────────────────
st.markdown("""
**Conclusão:**  
O sistema com AIDA executou menos ciclos de degelo, reduzindo em média de 4 para 2 ciclos por dia.

Com  da redução de ciclos, a capacidade média do compressor diminuiu em torno de 4%

Diminuir a frequência de degelos não impactou negativamente o desempenho do sistema

**Próximos passos:**  
1. Aplicar sistema na instlação Atacadão Boa Vista  

""")