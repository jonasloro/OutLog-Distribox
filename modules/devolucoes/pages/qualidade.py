import pandas as pd
import streamlit as st

from ..tratamento import indicadores_avarias_por_loja, listar_avarias


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
    total_pecas = int(df["quantidade"].sum())
    total_devolucoes = df["devolucao_id"].nunique()
    media_por_devolucao = total_pecas / total_devolucoes if total_devolucoes else 0

    c1, c2, c3 = st.columns(3)
    c1.metric("Peças em avaria (total)", total_pecas)
    c2.metric("Devoluções com avaria", total_devolucoes)
    c3.metric("Média de peças em avaria por devolução", f"{media_por_devolucao:.1f}")

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

    st.subheader("Itens em avaria")
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
            "Observação": r["observacao"] or "",
        }
        for r in filtrados
    ]
    st.dataframe(pd.DataFrame(dados), use_container_width=True, hide_index=True)
