"""
Módulo de Recebimento: Funcionalidades de entrada de mercadoria no CD.
Responsável por marcar cards/lotes como recebidos e integrar com o SGO.
"""

import pandas as pd
import streamlit as st
from datetime import datetime
from zoneinfo import ZoneInfo

FUSO_BRASILIA = ZoneInfo("America/Sao_Paulo")

def marcar_como_recebido(lote_id, data_recebimento=None, observacoes=""):
    """
    Marca um lote/card do SGO como recebido no CD.
    
    Args:
        lote_id (str): ID do lote (do SGO)
        data_recebimento (datetime): Data/hora do recebimento (default: agora em Brasília)
        observacoes (str): Observações sobre o recebimento
        
    Returns:
        bool: True se marcado com sucesso, False se falhou
    """
    if data_recebimento is None:
        data_recebimento = datetime.now(FUSO_BRASILIA)
    
    df_sgo = st.session_state.get("sgo_relatorio_df")
    if df_sgo is None or df_sgo.empty:
        st.error("⚠️ Nenhum relatório SGO carregado — não há lotes pra marcar como recebidos.")
        return False
    
    # Localiza o lote no DataFrame
    lote_mask = df_sgo["Lote"].astype(str) == str(lote_id)
    if not lote_mask.any():
        st.error(f"⚠️ Lote '{lote_id}' não encontrado no relatório SGO.")
        return False
    
    # Atualiza status pra "Recebido" e grava a data
    df_sgo.loc[lote_mask, "StatusOriginal"] = "Recebido"
    df_sgo.loc[lote_mask, "DataChegada"] = data_recebimento.date()
    
    # Log da ação
    usuario = st.session_state.get("usuario_atual", "desconhecido")
    st.session_state.log_recebimentos_sessao = st.session_state.get("log_recebimentos_sessao", [])
    st.session_state.log_recebimentos_sessao.insert(0, {
        "lote": lote_id,
        "usuario": usuario,
        "quando": data_recebimento.strftime("%d/%m/%Y %H:%M:%S"),
        "observacoes": observacoes,
    })
    
    st.session_state.sgo_relatorio_df = df_sgo
    return True


def renderizar_painel_recebimento_card(lote_id, lote_grupo, lote_descricao, lote_qtd, lote_fase):
    """
    Renderiza um card individual pra mostrar um lote e permitir marcá-lo como recebido.
    
    Usado no Dashboard Recebimento e na tela "Recebimento Manual".
    """
    import streamlit as st
    
    col1, col2, col3 = st.columns([2, 2, 1])
    
    with col1:
        st.markdown(f"""
        <div style='background:#11161d; border:1px solid #283845; border-radius:8px; padding:12px;'>
            <div style='color:#ffcc00; font-weight:bold; font-size:13px;'>📦 Lote: {lote_id}</div>
            <div style='color:#c5c6c7; font-size:12px; margin-top:4px;'>{lote_grupo}</div>
            <div style='color:#8892b0; font-size:11px; margin-top:2px;'>{lote_descricao}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div style='background:#11161d; border:1px solid #283845; border-radius:8px; padding:12px;'>
            <div style='color:#8892b0; font-size:10px; text-transform:uppercase; letter-spacing:0.5px;'>Quantidade</div>
            <div style='color:#ffcc00; font-weight:bold; font-size:18px; margin-top:4px;'>{lote_qtd:,} un</div>
            <div style='color:#8892b0; font-size:10px; margin-top:4px;'>Etapa: <b>{lote_fase}</b></div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        if st.button(
            "✅ Marcar\nRecebido",
            key=f"receber_{lote_id}",
            use_container_width=True,
            type="primary"
        ):
            if marcar_como_recebido(lote_id, observacoes=f"Marcado via Dashboard"):
                st.success(f"✅ Lote {lote_id} marcado como recebido!")
                st.rerun()
            else:
                st.error(f"❌ Não foi possível marcar o lote {lote_id}.")


def renderizar_dashboard_recebimento_simplificado():
    """
    Dashboard simplificado de Recebimento:
    - Mostra lotes em trânsito (chegando)
    - Permite marcar como recebido
    - Integra com o SGO
    """
    import streamlit as st
    
    df_sgo = st.session_state.get("sgo_relatorio_df")
    
    if df_sgo is None or df_sgo.empty:
        st.info("📄 Importe um relatório do SGO em 🚚 SGO — Próximas Entradas pra começar.")
        return
    
    # Filtra lotes em trânsito (ainda não chegaram)
    em_transito = df_sgo[df_sgo["Fase"] == "🚚 Em Trânsito"].copy()
    
    if em_transito.empty:
        st.success("✅ Nenhum lote em trânsito no momento — tudo foi recebido ou já está em processamento.")
        return
    
    st.markdown("#### Lotes a Receber")
    st.caption(f"{len(em_transito)} lote(s) em trânsito")
    
    # Ordena por data prevista (mais urgentes primeiro)
    em_transito = em_transito.sort_values("Data", ascending=True, na_position="last")
    
    for _, linha in em_transito.iterrows():
        renderizar_painel_recebimento_card(
            lote_id=linha.get("Lote", "?"),
            lote_grupo=linha.get("Grupo", "?"),
            lote_descricao=linha.get("Descrição", ""),
            lote_qtd=int(linha.get("Quantidade", 0)),
            lote_fase=linha.get("Fase", "?"),
        )
        st.write("")  # Espaço entre cards
