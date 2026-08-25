import pandas as pd
import streamlit as st

from ..tratamento import (
    desfazer_encaminhamento_bazar,
    indicadores_avarias_por_loja,
    listar_avarias,
    marcar_encaminhado_bazar,
)


def render() -> None:
    st.header("🔎 Qualidade — Defeitos (Avaria)")
    st.caption(
        "Toda peça marcada como AVARIA na tratativa de Devoluções (setor Expedição) "
        "aparece aqui automaticamente — não precisa lançar de novo."
    )

    avarias = listar_avarias()
    if not avarias:
        st.info("Nenhuma peça marcada como avaria ainda.")
        return

    df = pd.DataFrame(avarias)
    pendentes = df[df["encaminhado_bazar_em"].isna()].copy()
    encaminhadas = df[df["encaminhado_bazar_em"].notna()].copy()

    total_pendente = int(pendentes["quantidade"].sum()) if not pendentes.empty else 0

    st.markdown(
        f"""
        <div style="background:#3a2f0b; border:1px solid #ffcc00; border-radius:10px;
                    padding:16px 20px; margin-bottom:16px;">
            <div style="font-size:14px; color:#ffcc00;">🔍 Aguardando inspeção</div>
            <div style="font-size:36px; font-weight:700; color:#ffffff;">{total_pendente} peças</div>
            <div style="font-size:13px; color:#c9c9c9;">Ainda não foram inspecionadas nem encaminhadas ao bazar</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    total_pecas = int(df["quantidade"].sum())
    total_devolucoes = df["devolucao_id"].nunique()
    total_encaminhado = int(encaminhadas["quantidade"].sum()) if not encaminhadas.empty else 0

    c1, c2, c3 = st.columns(3)
    c1.metric("Peças em avaria (total)", total_pecas)
    c2.metric("Já encaminhadas ao bazar", total_encaminhado)
    c3.metric("Devoluções com avaria", total_devolucoes)

    st.subheader("Avaria por loja")
    indicadores = indicadores_avarias_por_loja()
    if indicadores:
        df_lojas = pd.DataFrame(indicadores).rename(columns={
            "loja": "Loja",
            "total_avaria": "Peças em avaria",
            "devolucoes_com_avaria": "Devoluções com avaria",
        })
        df_lojas["Loja"] = df_lojas["Loja"].fillna("Não informada")
        df_lojas["Média por devolução"] = (
            df_lojas["Peças em avaria"] / df_lojas["Devoluções com avaria"]
        ).round(1)
        st.dataframe(df_lojas, use_container_width=True, hide_index=True)
        st.bar_chart(df_lojas.set_index("Loja")["Peças em avaria"])
    else:
        st.info("Sem avarias vinculadas a loja ainda.")

    st.subheader(f"🔍 Aguardando inspeção ({len(pendentes)} lançamento(s))")
    if pendentes.empty:
        st.success("Nada pendente — todas as avarias já foram inspecionadas e encaminhadas ao bazar.")
    else:
        pendentes_exibicao = pendentes.assign(
            Encaminhar=False,
            Data=pendentes["data_documento"].apply(lambda d: d.strftime("%d/%m/%Y") if pd.notna(d) else "—"),
        )[["id", "Encaminhar", "Data", "numero_documento", "loja", "codigo_barras", "descricao", "grade", "quantidade", "observacao"]]
        pendentes_exibicao.columns = ["id", "Encaminhar", "Data", "Documento", "Loja", "Código", "Produto", "Grade", "Quantidade", "Observação"]

        editado = st.data_editor(
            pendentes_exibicao,
            key="qualidade_pendentes_editor",
            hide_index=True,
            use_container_width=True,
            column_config={
                "id": None,
                "Encaminhar": st.column_config.CheckboxColumn("Encaminhar ao bazar?"),
                "Documento": st.column_config.TextColumn(disabled=True),
                "Loja": st.column_config.TextColumn(disabled=True),
                "Código": st.column_config.TextColumn(disabled=True),
                "Produto": st.column_config.TextColumn(disabled=True),
                "Grade": st.column_config.TextColumn(disabled=True),
                "Quantidade": st.column_config.NumberColumn(disabled=True),
                "Observação": st.column_config.TextColumn(disabled=True),
                "Data": st.column_config.TextColumn(disabled=True),
            },
        )

        selecionados = editado[editado["Encaminhar"]]["id"].tolist()
        if st.button(f"✅ Marcar {len(selecionados)} selecionado(s) como encaminhado ao bazar", disabled=not selecionados, type="primary"):
            marcar_encaminhado_bazar(selecionados)
            st.success(f"{len(selecionados)} lançamento(s) marcado(s) como encaminhado ao bazar.")
            st.rerun()

    if not encaminhadas.empty:
        with st.expander(f"✅ Já encaminhadas ao bazar ({len(encaminhadas)} lançamento(s))"):
            dados_enc = [
                {
                    "id": r["id"],
                    "Data": r["data_documento"].strftime("%d/%m/%Y") if pd.notna(r.get("data_documento")) else "—",
                    "Documento": r["numero_documento"],
                    "Loja": r["loja"] or "—",
                    "Código": r["codigo_barras"],
                    "Produto": r["descricao"],
                    "Grade": r["grade"],
                    "Quantidade": r["quantidade"],
                    "Encaminhado em": r["encaminhado_bazar_em"].strftime("%d/%m/%Y %H:%M") if pd.notna(r.get("encaminhado_bazar_em")) else "—",
                }
                for _, r in encaminhadas.iterrows()
            ]
            df_enc = pd.DataFrame(dados_enc)
            st.dataframe(df_enc.drop(columns=["id"]), use_container_width=True, hide_index=True)

            desfazer_opcoes = [
                f"#{r['id']} — {r['Documento']} — {r['Produto']} ({r['Quantidade']} pçs)"
                for r in dados_enc
            ]
            desfazer_escolha = st.multiselect("Desfazer encaminhamento (voltar pra 'aguardando inspeção')", desfazer_opcoes, key="qualidade_desfazer")
            if desfazer_escolha and st.button("↩️ Desfazer selecionado(s)"):
                ids_desfazer = [dados_enc[desfazer_opcoes.index(x)]["id"] for x in desfazer_escolha]
                desfazer_encaminhamento_bazar(ids_desfazer)
                st.success("Desfeito — voltou pra aguardando inspeção.")
                st.rerun()

    st.subheader("Itens em avaria (todos)")
    f1, f2 = st.columns(2)
    lojas_disponiveis = sorted({str(r["loja"]) for r in avarias if r.get("loja")})
    filtro_loja = f1.selectbox("Loja", ["Todas"] + lojas_disponiveis, key="qualidade_filtro_loja")
    busca_doc = f2.text_input("Documento", key="qualidade_filtro_doc").strip().lower()

    filtrados = avarias
    if filtro_loja != "Todas":
        filtrados = [r for r in filtrados if str(r.get("loja")) == filtro_loja]
    if busca_doc:
        filtrados = [r for r in filtrados if busca_doc in str(r.get("numero_documento") or "").lower()]

    dados = [
        {
            "Data": r["data_documento"].strftime("%d/%m/%Y") if r.get("data_documento") else "—",
            "Documento": r["numero_documento"],
            "Loja": r["loja"] or "—",
            "Código": r["codigo_barras"],
            "Produto": r["descricao"],
            "Grade": r["grade"],
            "Quantidade": r["quantidade"],
            "Status": "✅ Encaminhado ao bazar" if r.get("encaminhado_bazar_em") else "🔍 Aguardando inspeção",
            "Observação": r["observacao"] or "",
        }
        for r in filtrados
    ]
    st.dataframe(pd.DataFrame(dados), use_container_width=True, hide_index=True)
