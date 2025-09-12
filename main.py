import streamlit as st
import pandas as pd
import altair as alt
from datetime import timedelta
import os



# ─── Paleta Plotter Racks ────────────────────────────────────────────────────
COLOR_PREV = "#112D4E"
COLOR_REAL = "#3F72AF"
COLOR_ECON = "#1177FC"
COLOR_BG   = "#E8E8E8"

# Titulo da caixa de seleção da instalação
st.sidebar.header("Seleção da instalação", help='Selecione a instalação que deseja analisar')


# Opções disponiveis: 'Eficinência Energética' + lista com as chaves do dicionário de arquivos existentes
options = ["Atacadão Bangu RJ", "Atacadão Palmas TO"]
selecionado = st.sidebar.selectbox("Selecione a instalação:", options, index=0)

# ─── Configuração da Página ──────────────────────────────────────────────────
st.set_page_config(
    page_title=f"Plotter Racks - Análise SDR -{selecionado} :male_mage: ",
   # subheader="Atacadão Bangu RJ - Análise SDR",
    layout="wide"
)

# Titulo da página!
st.header(f"Plotter Racks - Análise SDR -{selecionado} :snowflake: :heavy_dollar_sign:")

# Altera a base de dados conforme seleção do 
match selecionado:
    case "Atacadão Bangu RJ": # Primeira posição da lista - Atacadão Bangu RJ
        ARQUIVOS = {
                "Cam Congelados Eco2Pack L1": r"data/atacadao_bangu_RJ/L1A01_cam_congelados.csv",
                "Cam Congelados Eco2Pack L2": r"data/atacadao_bangu_RJ/L2A01_cam_congelados.csv",
                    } # Recebe os arquivos 
    case "Atacadão Palmas TO":
        ARQUIVOS = {
                "Cam Congelados Eco2Pack L1": r"data/atacadao_palmas_TO/L1.csv",
                "Cam Congelados Eco2Pack L2": r"data/atacadao_palmas_TO/L2.csv",
                "Cam Congelados Eco2Pack L3": r"data/atacadao_palmas_TO/L3.csv",
                    } # Recebe os arquivos 
    case _:
        ARQUIVOS = {}                


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
    "Cam Congelados Eco2Pack L1": 10.0,
    "Cam Congelados Eco2Pack L2": 10.0,
    "Cam Congelados Eco2Pack L3": 10.0,
}

CYCLES_DAY  = 4
CYCLE_HOURS = 45 / 60
SETPOINT    = -20.0

@st.cache_data
def load_all(paths):
    dfs = []
    for nome, caminho in paths.items():
        try:
            #df = pd.read_excel(caminho, engine="openpyxl")
            df = pd.read_csv(caminho, sep=";", encoding="utf-8", na_values='---')
            # Verificar se o DataFrame não está vazio
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
            df["DataHora"] = pd.to_datetime(df["DataHora"], dayfirst=False, errors="coerce")            
            # Remover linhas com data inválida
            df = df.dropna(subset=["DataHora"])            
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

# ─── Verificar se os arquivos existem ────────────────────────────────────────
# chama a função load_all com base no dicionário 'ARQUIVOS_EXISTENTES'
df_all = load_all(ARQUIVOS_EXISTENTES)


# Checa se o dicionário foi corretamente carregado
if df_all.empty:
    st.error("Nenhum dado válido encontrado.")
    st.stop()

# Titulo da caixa de seleção
st.sidebar.header("Seleção de Módulo", help='Selecione o forçador ou o modo eficiencia energética')

# Opções disponiveis: 'Eficinência Energética' + lista com as chaves do dicionário de arquivos existentes
options = ["Eficiência Energética"] + list(ARQUIVOS_EXISTENTES.keys())
selecionados = st.sidebar.multiselect("Modo:", options, default=list(ARQUIVOS_EXISTENTES.keys()))

if "Eficiência Energética" in selecionados:
    selecionados = ["Eficiência Energética"]

# Pega as menores e maiores datas do data frame, cm base na coluna data
mind, maxd = df_all.index.min().date(), df_all.index.max().date()

start_date, end_date = st.sidebar.date_input("Período", [mind, maxd], min_value=mind, max_value=maxd)
delta = st.sidebar.number_input("Delta tolerância (K)", 0.0, 10.0, 2.0, 0.1)

def calc_metrics(df_sel, pot_kw, start_date, end_date):
    df = df_sel.copy()
    
    # Verificar se a coluna "Degelo" existe
    if "Degelo" not in df.columns:
        st.warning("Coluna 'Degelo' não encontrada nos dados.")
        return 0, 0, 0, 0, 0, 0

    # troca os erros NaN por 0 (false)    
    df["DefrostStatus"] = pd.to_numeric(df["Degelo"], errors="coerce").fillna(0)

    # Checa a transição de 0 para 1 no status de degelo, para indicar que o degelo iniciou
    df["Event"] = df["DefrostStatus"].diff() == 1

    # Conta a quantidade de eventos de início de degelo
    eventos = int(df["Event"].sum())

    # Totaliza a quantidade de dias
    dias = (end_date - start_date).days + 1

    # Totaliza a quandtidade de ciclos prevista
    ciclos = CYCLES_DAY * dias

    # consumo previsto se degelo por agenda
    cons_prev = pot_kw * CYCLE_HOURS * ciclos

    # consumo real, com o degelo pelo SDR
    cons_real = pot_kw * CYCLE_HOURS * eventos

    # Economia prevista em termos absolutos (kwh) e percentuais
    econ_kwh = cons_prev - cons_real
    econ_pct = econ_kwh / cons_prev * 100 if cons_prev else 0 

    # Retorna os dados
    return cons_prev, cons_real, econ_kwh, econ_pct, ciclos, eventos

def barras_prev_real(dfc):
    base = dfc.melt(id_vars="Sistema", value_vars=["Previsto","Real"],
                    var_name="Categoria", value_name="Valor")
    bars = alt.Chart(base).mark_bar(size=35).encode(
        x=alt.X("Sistema:N", title=None),
        y=alt.Y("Valor:Q", title="Energia (kWh)"),
        color=alt.Color("Categoria:N", scale=alt.Scale(
            domain=["Previsto","Real"], range=[COLOR_PREV, COLOR_REAL])),
        xOffset="Categoria:N"
    )
    labels = alt.Chart(base).mark_text(dy=-5, fontSize=12).encode(
        x="Sistema:N", y="Valor:Q", detail="Categoria:N",
        text=alt.Text("Valor:Q", format=".0f")
    )
    return bars + labels

if selecionados == ["Eficiência Energética"]:
    # Total
    tot_prev = tot_real = tot_ciclos = tot_ev = 0
    for amb, pot in POTENCIAS.items():
        df_sel = df_all[df_all["Origem"]==amb].loc[start_date:end_date]
        prev, real, _, _, ciclos, ev = calc_metrics(df_sel, pot, start_date, end_date)
        tot_prev += prev
        tot_real += real
        tot_ciclos += ciclos
        tot_ev += ev
    tot_pct = (tot_prev - tot_real) / tot_prev * 100 if tot_prev else 0

    st.subheader("Total - Eficiência Energética")
    c1, c2 = st.columns([3,1])
    with c1:
        df_tot = pd.DataFrame([{"Sistema":"Total","Previsto":tot_prev,"Real":tot_real}])
        st.altair_chart(barras_prev_real(df_tot).properties(height=300).configure_view(strokeOpacity=0),
                        use_container_width=True)
    with c2:
        st.metric("Economia (%)", f"{tot_pct:.1f}%",
                  delta=f"Prev: {tot_prev:.1f} kWh  Real: {tot_real:.1f} kWh")
        st.markdown(
            f"Degelos agendados: **{tot_ciclos}**  •  Degelos realizados: **{tot_ev}**"
        )
    st.markdown("---")

    # Por Ambiente
    for amb, pot in POTENCIAS.items():
        #prev, real, _, pct, ciclos, ev = calc_metrics(df_all[df_all["Origem"]==amb].loc[start_date:end_date], pot)
        prev, real, _, pct, ciclos, ev = calc_metrics(df_all[df_all["Origem"]==amb].loc[start_date:end_date], pot, start_date, end_date)
        st.subheader(amb)
        col1, col2 = st.columns([3,1])
        with col1:
            dfc = pd.DataFrame([{"Sistema":amb,"Previsto":prev,"Real":real}])
            st.altair_chart(barras_prev_real(dfc).properties(height=250).configure_view(strokeOpacity=0),
                            use_container_width=True)
        with col2:
            st.metric("Economia (%)", f"{pct:.1f}%",
                      delta=f"Prev: {prev:.1f} kWh  Real: {real:.1f} kWh")
            st.markdown(
                f"Degelos agendados: **{ciclos}**  •  Degelos realizados: **{ev}**"
            )
        st.markdown("---")

    st.stop()

# ─── Modo Análise por Ambiente ────────────────────────────────────────────────
for origem in selecionados:
    pot = POTENCIAS[origem]
    df_sel = df_all[df_all["Origem"]==origem].loc[start_date:end_date]

    # Verificar se há dados para este ambiente
    if df_sel.empty:
        st.warning(f"Nenhum dado encontrado para {origem} no período selecionado.")
        continue

    st.header(f"Análise – {origem}")

    # Verificar se as colunas necessárias existem
    required_cols = ["Temp ambiente", "Degelo"]
    missing_cols = [col for col in required_cols if col not in df_sel.columns]
    if missing_cols:
        st.error(f"Colunas necessárias não encontradas em {origem}: {missing_cols}")
        continue

    # Temperatura & Eventos de Degelo
    df_sel["Temp ambiente"] = pd.to_numeric(
        df_sel["Temp ambiente"], errors="coerce"
    ).fillna(method="ffill")
    df_sel["Degelo"] = pd.to_numeric(
        df_sel["Degelo"], errors="coerce"
    ).fillna(0)
    df_sel["Event"] = df_sel["Degelo"].diff() == 1
    events = df_sel.index[df_sel["Event"]]

    # Verificar se há dados válidos para o gráfico
    if df_sel["Temp ambiente"].isna().all():
        st.warning(f"Nenhum dado de temperatura válido encontrado para {origem}")
    else:
        rects = pd.DataFrame({
            "start": events,
            "end":   events + pd.Timedelta(minutes=15),
            "y1":    df_sel["Temp ambiente"].min(),
            "y2":    df_sel["Temp ambiente"].max()
        })
        
        # Verificar se há eventos para mostrar
        if not events.empty:
            overlay = alt.Chart(rects).mark_rect(color=COLOR_ECON, opacity=0.3).encode(
                x="start:T", x2="end:T", y="y1:Q", y2="y2:Q"
            )
        else:
            overlay = None
            
        line = alt.Chart(df_sel.reset_index()).mark_line(interpolate="monotone").encode(
            x="DataHora:T",
            y=alt.Y("Temp ambiente:Q", title="Temperatura (°C)")
        )
        
        st.subheader("Temperatura e Eventos de Degelo")
        if overlay is not None:
            st.altair_chart((overlay + line).properties(height=350).interactive(),
                            use_container_width=True)
        else:
            st.altair_chart(line.properties(height=350).interactive(),
                            use_container_width=True)

    # Performance de Temperatura
    recovery = pd.Series(False, index=df_sel.index)
    for t0 in events:
        recovery |= (df_sel.index > t0 + timedelta(minutes=45)) & \
                    (df_sel.index <= t0 + timedelta(minutes=75))

    periods = {
        "Operação (08–21h)": ((df_sel.index.hour >= 8) & (df_sel.index.hour < 21) & (df_sel.index.weekday < 5)),
        "Fora (21–08h)":     (((df_sel.index.hour >= 21) | (df_sel.index.hour < 8)) & (df_sel.index.weekday < 5)),
        "Fim de Semana":     (df_sel.index.weekday >= 5)
    }
    perf_list = []
    for nome_p, mask in periods.items():
        valid = mask & (~recovery)
        s = df_sel.loc[valid, "Temp ambiente"]
        
        # Verificar se há dados válidos para este período
        if s.empty or s.isna().all():
            perf_list.append({
                "Período": nome_p,
                "Média (°C)": "N/A",
                "Performance (%)": "N/A"
            })
        else:
            perf_pct = ((s - SETPOINT).abs() <= delta).mean() * 100
            perf_list.append({
                "Período": nome_p,
                "Média (°C)": round(s.mean(), 1),
                "Performance (%)": round(perf_pct, 1)
            })

    st.subheader("Performance de Temperatura da Câmara")
    st.table(pd.DataFrame(perf_list).set_index("Período"))
    st.markdown("---")
