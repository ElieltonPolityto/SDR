import streamlit as st
import pandas as pd
import altair as alt
from datetime import timedelta
import os

# ─── Configuração da Página ──────────────────────────────────────────────────
st.set_page_config(
    page_title="Plotter Racks",
    page_icon=":fridge:",
    layout="wide",
)

st.subheader("Atacadão Bangu RJ - Análise SDR")

# ─── Paleta Plotter Racks ────────────────────────────────────────────────────
COLOR_PREV = "#112D4E"
COLOR_REAL = "#3F72AF"
COLOR_ECON = "#1177FC"
COLOR_BG   = "#E8E8E8"

# ─── Arquivos de entrada ─────────────────────────────────────────────────────
# Use as MESMAS chaves em ARQUIVOS e POTENCIAS (vão para a coluna "Origem")
ARQUIVOS = {
    "Câmara de Congelados - Eco2Pack L1": r"data/L1A01_cam_congelados.csv",
    # "Câmara de Congelados - Eco2Pack L2": r"data/L1A02_cam_congelados.csv",
}

# Verificar quais arquivos existem
ARQUIVOS_EXISTENTES = {}
for nome, caminho in ARQUIVOS.items():
    if os.path.exists(caminho):
        ARQUIVOS_EXISTENTES[nome] = caminho
    else:
        st.warning(f"Arquivo não encontrado: {caminho}")

if not ARQUIVOS_EXISTENTES:
    st.error("Nenhum arquivo de dados encontrado. Verifique os caminhos dos arquivos.")
    st.stop()

POTENCIAS = {
    "Câmara de Congelados - Eco2Pack L1": 10.0,
    # "Câmara de Congelados - Eco2Pack L2": 10.0,
}

CYCLES_DAY  = 4
CYCLE_HOURS = 45 / 60
SETPOINT    = -20.0

@st.cache_data
def load_all(paths: dict) -> pd.DataFrame:
    dfs = []
    for nome, caminho in paths.items():
        try:
            # Leitura CSV (ajuste encoding/decimal conforme sua origem de dados)
            df = pd.read_csv(caminho, sep=";", encoding="utf-8")

            if df.empty:
                st.warning(f"Arquivo vazio: {nome}")
                continue

            # Encontrar coluna de data/hora
            dtcol = None
            for c in df.columns:
                if "Data" in str(c) or "Hora" in str(c):
                    dtcol = c
                    break
            if dtcol is None:
                st.warning(f"Coluna de data/hora não encontrada em: {nome}")
                continue

            df = df.rename(columns={dtcol: "DataHora"})
            df["DataHora"] = pd.to_datetime(df["DataHora"], dayfirst=True, errors="coerce")
            df = df.dropna(subset=["DataHora"])  # remove datas inválidas
            if df.empty:
                st.warning(f"Nenhuma data válida encontrada em: {nome}")
                continue

            df["Origem"] = nome
            dfs.append(df)

        except Exception as e:
            st.error(f"Erro ao carregar {nome}: {str(e)}")
            continue

    if not dfs:
        st.error("Nenhum arquivo foi carregado com sucesso.")
        st.stop()

    return pd.concat(dfs).set_index("DataHora").sort_index()

# ─── Carregar dados ───────────────────────────────────────────────────────────
df_all = load_all(ARQUIVOS_EXISTENTES)

if df_all.empty:
    st.error("Nenhum dado válido encontrado.")
    st.stop()

# ─── Sidebar: filtros ─────────────────────────────────────────────────────────
st.sidebar.header("Seleção de Módulo")
st.sidebar.caption("Selecione o forçador ou o modo Eficiência Energética")

options = ["Eficiência Energética"] + list(ARQUIVOS_EXISTENTES.keys())
selecionados = st.sidebar.multiselect("Modo:", options, default=list(ARQUIVOS_EXISTENTES.keys()))

if "Eficiência Energética" in selecionados:
    selecionados = ["Eficiência Energética"]

mind, maxd = df_all.index.min().date(), df_all.index.max().date()
start_date, end_date = st.sidebar.date_input("Período", [mind, maxd], min_value=mind, max_value=maxd)
delta = st.sidebar.number_input("Delta tolerância (K)", 0.0, 10.0, 2.0, 0.1)

# ─── Cálculos ────────────────────────────────────────────────────────────────

def calc_metrics(df_sel, pot_kw, start_date, end_date):
    df = df_sel.copy()

    # Verificar se a coluna "Degelo" existe
    if "Degelo" not in df.columns:
        st.warning("Coluna 'Degelo' não encontrada nos dados.")
        return 0, 0, 0, 0, 0, 0

    # Normaliza Degelo (0/1)
    df["DefrostStatus"] = pd.to_numeric(df["Degelo"], errors="coerce").fillna(0)

    # Evento = transição 0→1
    df["Event"] = df["DefrostStatus"].diff() == 1
    eventos = int(df["Event"].sum())

    dias = (end_date - start_date).days + 1
    ciclos = CYCLES_DAY * dias

    cons_prev = pot_kw * CYCLE_HOURS * ciclos
    cons_real = pot_kw * CYCLE_HOURS * eventos

    econ_kwh = cons_prev - cons_real
    econ_pct = (econ_kwh / cons_prev * 100) if cons_prev else 0

    return cons_prev, cons_real, econ_kwh, econ_pct, ciclos, eventos

# ─── Gráficos ────────────────────────────────────────────────────────────────

def barras_prev_real(dfc: pd.DataFrame):
    base = dfc.melt(id_vars="Sistema", value_vars=["Previsto", "Real"],
                    var_name="Categoria", value_name="Valor")
    bars = alt.Chart(base).mark_bar(size=35).encode(
        x=alt.X("Sistema:N", title=None),
        y=alt.Y("Valor:Q", title="Energia (kWh)"),
        color=alt.Color("Categoria:N", scale=alt.Scale(
            domain=["Previsto", "Real"], range=[COLOR_PREV, COLOR_REAL])),
        xOffset="Categoria:N",
    )
    labels = alt.Chart(base).mark_text(dy=-5, fontSize=12).encode(
        x="Sistema:N", y="Valor:Q", detail="Categoria:N",
        text=alt.Text("Valor:Q", format=".0f"),
    )
    return bars + labels

# ─── Modo Eficiência Energética (agregado) ───────────────────────────────────
if selecionados == ["Eficiência Energética"]:
    tot_prev = tot_real = tot_ciclos = tot_ev = 0

    for amb, pot in POTENCIAS.items():
        #df_sel = df_all[df_all["Origem"] == amb].loc[start_date:end_date]
        df_sel = df_all[df_all["Origem"]==amb].loc[start_date:end_date], pot, start_date, end_date
        if df_sel.empty:
            st.info(f"Sem dados para {amb} no período.")
            continue
        #prev, real, _, _, ciclos, ev = calc_metrics(df_sel, pot, start_date, end_date)
        prev, real, _, _, ciclos, ev = calc_metrics(df_sel, pot, start_date, end_date)
        tot_prev += prev; tot_real += real; tot_ciclos += ciclos; tot_ev += ev

    tot_pct = (tot_prev - tot_real) / tot_prev * 100 if tot_prev else 0

    st.subheader("Total - Eficiência Energética")
    c1, c2 = st.columns([3, 1])
    with c1:
        df_tot = pd.DataFrame([{ "Sistema": "Total", "Previsto": tot_prev, "Real": tot_real }])
        st.altair_chart(
            barras_prev_real(df_tot).properties(height=300).configure_view(strokeOpacity=0),
            use_container_width=True,
        )
    with c2:
        st.metric("Economia (%)", f"{tot_pct:.1f}%",
                  delta=f"Prev: {tot_prev:.1f} kWh  Real: {tot_real:.1f} kWh")
        st.markdown(
            f"Degelos agendados: **{tot_ciclos}**  •  Degelos realizados: **{tot_ev}**"
        )
    st.markdown("---")

    # Por Ambiente
    for amb, pot in POTENCIAS.items():
        df_sel = df_all[df_all["Origem"] == amb].loc[start_date:end_date]
        if df_sel.empty:
            continue
        prev, real, _, pct, ciclos, ev = calc_metrics(df_sel, pot, start_date, end_date)
        

        st.subheader(amb)
        col1, col2 = st.columns([3, 1])
        with col1:
            dfc = pd.DataFrame([{ "Sistema": amb, "Previsto": prev, "Real": real }])
            st.altair_chart(
                barras_prev_real(dfc).properties(height=250).configure_view(strokeOpacity=0),
                use_container_width=True,
            )
        with col2:
            st.metric("Economia (%)", f"{pct:.1f}%",
                      delta=f"Prev: {prev:.1f} kWh  Real: {real:.1f} kWh")
            st.markdown(
                f"Degelos agendados: **{ciclos}**  •  Degelos realizados: **{ev}**"
            )
        st.markdown("---")

    st.stop()

# ─── Modo Análise por Ambiente ───────────────────────────────────────────────
for origem in selecionados:
    if origem == "Eficiência Energética":
        continue

    pot = POTENCIAS.get(origem)
    if pot is None:
        st.warning(f"Potência não definida para '{origem}'. Ajuste POTENCIAS.")
        continue

    df_sel = df_all[df_all["Origem"] == origem].loc[start_date:end_date]
    if df_sel.empty:
        st.warning(f"Nenhum dado encontrado para {origem} no período selecionado.")
        continue

    st.header(f"Análise – {origem}")

    required_cols = ["Temp ambiente", "Degelo"]
    missing_cols = [col for col in required_cols if col not in df_sel.columns]
    if missing_cols:
        st.error(f"Colunas necessárias não encontradas em {origem}: {missing_cols}")
        continue

    # Temperatura & Eventos de Degelo
    df_sel["Temp ambiente"] = pd.to_numeric(df_sel["Temp ambiente"], errors="coerce").ffill()
    df_sel["Degelo"] = pd.to_numeric(df_sel["Degelo"], errors="coerce").fillna(0)
    df_sel["Event"] = df_sel["Degelo"].diff() == 1
    events = df_sel.index[df_sel["Event"]]

    if df_sel["Temp ambiente"].isna().all():
        st.warning(f"Nenhum dado de temperatura válido encontrado para {origem}")
    else:
        rects = pd.DataFrame({
            "start": events,
            "end":   events + pd.Timedelta(minutes=15),
            "y1":    df_sel["Temp ambiente"].min(),
            "y2":    df_sel["Temp ambiente"].max(),
        })
        overlay = (
            alt.Chart(rects).mark_rect(color=COLOR_ECON, opacity=0.3).encode(
                x="start:T", x2="end:T", y="y1:Q", y2="y2:Q"
            )
            if not events.empty else None
        )
        line = alt.Chart(df_sel.reset_index()).mark_line(interpolate="monotone").encode(
            x="DataHora:T",
            y=alt.Y("Temp ambiente:Q", title="Temperatura (°C)"),
        )
        st.subheader("Temperatura e Eventos de Degelo")
        if overlay is not None:
            st.altair_chart((overlay + line).properties(height=350).interactive(), use_container_width=True)
        else:
            st.altair_chart(line.properties(height=350).interactive(), use_container_width=True)

    # Performance de Temperatura
    recovery = pd.Series(False, index=df_sel.index)
    for t0 in events:
        recovery |= (df_sel.index > t0 + timedelta(minutes=45)) & (df_sel.index <= t0 + timedelta(minutes=75))

    periods = {
        "Operação (08–21h)": ((df_sel.index.hour >= 8) & (df_sel.index.hour < 21) & (df_sel.index.weekday < 5)),
        "Fora (21–08h)":     (((df_sel.index.hour >= 21) | (df_sel.index.hour < 8)) & (df_sel.index.weekday < 5)),
        "Fim de Semana":     (df_sel.index.weekday >= 5),
    }

    perf_list = []
    for nome_p, mask in periods.items():
        valid = mask & (~recovery)
        s = df_sel.loc[valid, "Temp ambiente"]
        if s.empty or s.isna().all():
            perf_list.append({"Período": nome_p, "Média (°C)": "N/A", "Performance (%)": "N/A"})
        else:
            perf_pct = ((s - SETPOINT).abs() <= delta).mean() * 100
            perf_list.append({"Período": nome_p, "Média (°C)": round(s.mean(), 1), "Performance (%)": round(perf_pct, 1)})

    st.subheader("Performance de Temperatura da Câmara")
    st.table(pd.DataFrame(perf_list).set_index("Período"))
    st.markdown("---")