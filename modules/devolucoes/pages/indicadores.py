from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st

from ..database import listar_devolucoes
from ..tratamento import listar_avarias

CORES = px.colors.qualitative.Set2


def render() -> None:
    st.header("📊 Indicadores")

    registros = listar_devolucoes()
    if not registros:
        st.info("Registre pelo menos uma devolução para gerar indicadores.")
        return

    df = pd.DataFrame(registros)
    df["loja"] = df["loja"].fillna("Não informada")
    df["data_documento"] = pd.to_datetime(df["data_documento"], errors="coerce")

    # ---------- filtros: aqui é onde dá pra "combinar" lojas ----------
    lojas_disponiveis = sorted(df["loja"].unique())
    f1, f2, f3 = st.columns([2, 1, 1])
    lojas_selecionadas = f1.multiselect(
        "Lojas (combine quantas quiser — vazio = todas)",
        lojas_disponiveis,
        default=[],
        key="indicadores_lojas",
    )
    datas_validas = df["data_documento"].dropna()
    data_min = datas_validas.min().date() if not datas_validas.empty else date.today()
    data_max = datas_validas.max().date() if not datas_validas.empty else date.today()
    data_inicial = f2.date_input("De", value=data_min, key="indicadores_data_ini")
    data_final = f3.date_input("Até", value=data_max, key="indicadores_data_fim")
    if data_inicial > data_final:
        data_inicial, data_final = data_final, data_inicial

    filtro = df.copy()
    if lojas_selecionadas:
        filtro = filtro[filtro["loja"].isin(lojas_selecionadas)]
    mask_data = filtro["data_documento"].isna() | (
        (filtro["data_documento"].dt.date >= data_inicial) & (filtro["data_documento"].dt.date <= data_final)
    )
    filtro = filtro[mask_data]

    if filtro.empty:
        st.warning("Nenhuma devolução nesse filtro.")
        return

    # ---------- KPIs ----------
    total_loja = int(filtro["total_pecas_loja"].sum())
    total_cd = int(filtro["total_pecas_entrada"].sum())
    total_anapolis = int(filtro["total_pecas_anapolis"].sum())
    total_encontrado = total_cd + total_anapolis
    pct_divergencia = (abs(total_encontrado - total_loja) / total_loja * 100) if total_loja else 0.0

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Devoluções", len(filtro))
    k2.metric("Peças da loja", f"{total_loja:,}")
    k3.metric("Peças encontradas (CD+Anápolis)", f"{total_encontrado:,}")
    k4.metric("Diferença acumulada", f"{total_encontrado - total_loja:,}")
    k5.metric("Divergência", f"{pct_divergencia:.1f}%")

    st.divider()

    # ---------- gráfico 1: peças por origem, por loja (combinável) ----------
    st.subheader("Peças recebidas por loja, por origem")
    df_origem = (
        filtro.groupby("loja")[["total_pecas_loja", "total_pecas_entrada", "total_pecas_anapolis"]]
        .sum()
        .reset_index()
        .rename(columns={
            "total_pecas_loja": "Loja (enviado)",
            "total_pecas_entrada": "Entrada CD",
            "total_pecas_anapolis": "Entrada Anápolis",
        })
    )
    df_origem_long = df_origem.melt(id_vars="loja", var_name="Origem", value_name="Peças")
    fig_origem = px.bar(
        df_origem_long, x="loja", y="Peças", color="Origem", barmode="group",
        color_discrete_sequence=CORES, text_auto=True,
    )
    fig_origem.update_layout(xaxis_title="Loja", legend_title="Origem", height=420)
    st.plotly_chart(fig_origem, use_container_width=True)

    col_a, col_b = st.columns(2)

    with col_a:
        st.subheader("Devoluções ao longo do tempo")
        df_tempo = filtro.dropna(subset=["data_documento"]).copy()
        if df_tempo.empty:
            st.info("Sem datas suficientes para o gráfico de tendência.")
        else:
            df_tempo["mes"] = df_tempo["data_documento"].dt.to_period("M").dt.to_timestamp()
            if lojas_selecionadas and len(lojas_selecionadas) > 1:
                df_linha = df_tempo.groupby(["mes", "loja"]).size().reset_index(name="Devoluções")
                fig_tempo = px.line(
                    df_linha, x="mes", y="Devoluções", color="loja", markers=True,
                    color_discrete_sequence=CORES,
                )
            else:
                df_linha = df_tempo.groupby("mes").size().reset_index(name="Devoluções")
                fig_tempo = px.line(df_linha, x="mes", y="Devoluções", markers=True)
            fig_tempo.update_layout(xaxis_title="Mês", height=380)
            st.plotly_chart(fig_tempo, use_container_width=True)

    with col_b:
        st.subheader("Distribuição por status")
        df_status = filtro["status"].value_counts().reset_index()
        df_status.columns = ["Status", "Quantidade"]
        fig_status = px.pie(
            df_status, names="Status", values="Quantidade", hole=0.45,
            color_discrete_sequence=CORES,
        )
        fig_status.update_layout(height=380)
        st.plotly_chart(fig_status, use_container_width=True)

    st.subheader("Diferença (Loja − Encontrado) por loja")
    df_dif = filtro.groupby("loja")["diferenca_total"].sum().reset_index().sort_values("diferenca_total")
    fig_dif = px.bar(
        df_dif, x="diferenca_total", y="loja", orientation="h",
        color="diferenca_total", color_continuous_scale=["#e74c3c", "#8892b0", "#45a29e"],
        labels={"diferenca_total": "Diferença", "loja": "Loja"},
    )
    fig_dif.update_layout(height=max(320, 28 * len(df_dif)), coloraxis_showscale=False)
    st.plotly_chart(fig_dif, use_container_width=True)

    # ---------- avarias, no mesmo filtro de loja/data ----------
    st.divider()
    st.subheader("Avaria (defeito) por loja")
    try:
        avarias = listar_avarias()
    except Exception as e:
        avarias = []
        st.warning(f"Não foi possível carregar dados de avaria: {e}")

    if avarias:
        df_av = pd.DataFrame(avarias)
        df_av["loja"] = df_av["loja"].fillna("Não informada")
        df_av["data_documento"] = pd.to_datetime(df_av["data_documento"], errors="coerce")
        if lojas_selecionadas:
            df_av = df_av[df_av["loja"].isin(lojas_selecionadas)]
        mask_av = df_av["data_documento"].isna() | (
            (df_av["data_documento"].dt.date >= data_inicial) & (df_av["data_documento"].dt.date <= data_final)
        )
        df_av = df_av[mask_av]

        if df_av.empty:
            st.info("Nenhuma avaria nesse filtro.")
        else:
            av1, av2 = st.columns(2)
            av1.metric("Peças em avaria (filtro atual)", int(df_av["quantidade"].sum()))
            av2.metric("Devoluções com avaria (filtro atual)", df_av["devolucao_id"].nunique())

            df_av_loja = df_av.groupby("loja")["quantidade"].sum().reset_index().sort_values("quantidade", ascending=False)
            fig_av = px.bar(
                df_av_loja, x="loja", y="quantidade", color="loja",
                color_discrete_sequence=CORES, text_auto=True,
            )
            fig_av.update_layout(xaxis_title="Loja", yaxis_title="Peças em avaria", showlegend=False, height=380)
            st.plotly_chart(fig_av, use_container_width=True)
    else:
        st.info("Nenhuma avaria registrada ainda.")
