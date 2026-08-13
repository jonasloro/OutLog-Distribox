import streamlit as st

# ============================================================
# CONFIGURAÇÃO DA PÁGINA
# ============================================================

st.set_page_config(
    page_title="OutLog",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)


# ============================================================
# CSS
# ============================================================

st.markdown("""
<style>

    /* Fundo geral */
    .stApp {
        background-color: #0b0d12;
    }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        background-color: #1d1f29;
    }

    /* Título */
    .outlog-title {
        text-align: center;
        color: #ffcc00;
        font-size: 42px;
        font-weight: 800;
        margin-bottom: 0;
    }

    .outlog-subtitle {
        text-align: center;
        color: #9aa0b3;
        letter-spacing: 4px;
        font-size: 13px;
        margin-top: 5px;
    }

    /* Cards */
    .card {
        background: #171a23;
        border: 1px solid #292d3a;
        border-radius: 12px;
        padding: 25px;
        margin-bottom: 20px;
    }

    .card-title {
        color: #ffcc00;
        font-size: 18px;
        font-weight: 700;
    }

    .card-value {
        color: white;
        font-size: 32px;
        font-weight: 800;
    }

</style>
""", unsafe_allow_html=True)


# ============================================================
# ESTADO DA NAVEGAÇÃO
# ============================================================

if "pagina" not in st.session_state:
    st.session_state.pagina = "🏠 Dashboard"


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.markdown(
        """
        <div style="text-align:center;">
            <div style="font-size:70px;">📦</div>
            <h2 style="color:#ffcc00; margin-top:-10px;">OUTLOG</h2>
        </div>
        """,
        unsafe_allow_html=True
    )

    st.markdown("---")

    st.markdown(
        "<h3 style='color:#ffcc00;'>⚙️ NAVEGAÇÃO</h3>",
        unsafe_allow_html=True
    )

    paginas = [
        "🏠 Dashboard",
        "📦 Visualizador de Casulos",
        "🔎 Consulta Rápida",
        "📊 Estatísticas",
        "🧪 Simulador de Capacidade",
        "📥 Entrada de Dados",
        "📋 Relatórios",
        "🛠️ Gerenciador"
    ]

    for pagina in paginas:
        if st.button(
            pagina,
            use_container_width=True,
            key=f"nav_{pagina}"
        ):
            st.session_state.pagina = pagina
            st.rerun()

    st.markdown("---")

    st.success("Sistema online")

    st.caption("OutLog • Gestão de Peças por Casulo")


# ============================================================
# CABEÇALHO
# ============================================================

st.markdown(
    """
    <div style="text-align:center;">
        <div style="font-size:80px;">📦</div>
        <div class="outlog-title">OutLog</div>
        <div class="outlog-subtitle">
            GESTÃO DE PEÇAS POR CASULO
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

st.write("")


# ============================================================
# DASHBOARD
# ============================================================

if st.session_state.pagina == "🏠 Dashboard":

    st.markdown(
        "<h2 style='text-align:center;color:#ffcc00;'>📊 Dashboard Geral</h2>",
        unsafe_allow_html=True
    )

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown(
            """
            <div class="card">
                <div class="card-title">Casulos</div>
                <div class="card-value">0</div>
            </div>
            """,
            unsafe_allow_html=True
        )

    with col2:
        st.markdown(
            """
            <div class="card">
                <div class="card-title">Peças</div>
                <div class="card-value">0</div>
            </div>
            """,
            unsafe_allow_html=True
        )

    with col3:
        st.markdown(
            """
            <div class="card">
                <div class="card-title">Ocupação</div>
                <div class="card-value">0%</div>
            </div>
            """,
            unsafe_allow_html=True
        )

    with col4:
        st.markdown(
            """
            <div class="card">
                <div class="card-title">Capacidade</div>
                <div class="card-value">0</div>
            </div>
            """,
            unsafe_allow_html=True
        )

    st.markdown("---")

    st.info(
        "🚀 O novo OutLog foi iniciado. "
        "As próximas etapas irão conectar o sistema ao Supabase."
    )


# ============================================================
# OUTRAS PÁGINAS — PLACEHOLDERS
# ============================================================

elif st.session_state.pagina == "📦 Visualizador de Casulos":

    st.header("📦 Visualizador de Casulos")
    st.info("Módulo será desenvolvido na próxima etapa.")


elif st.session_state.pagina == "🔎 Consulta Rápida":

    st.header("🔎 Consulta Rápida")
    st.info("Módulo será desenvolvido na próxima etapa.")


elif st.session_state.pagina == "📊 Estatísticas":

    st.header("📊 Estatísticas")
    st.info("Módulo será desenvolvido na próxima etapa.")


elif st.session_state.pagina == "🧪 Simulador de Capacidade":

    st.header("🧪 Simulador de Capacidade")
    st.info("Módulo será desenvolvido na próxima etapa.")


elif st.session_state.pagina == "📥 Entrada de Dados":

    st.header("📥 Entrada de Dados")
    st.info("Módulo será desenvolvido na próxima etapa.")


elif st.session_state.pagina == "📋 Relatórios":

    st.header("📋 Relatórios")
    st.info("Módulo será desenvolvido na próxima etapa.")


elif st.session_state.pagina == "🛠️ Gerenciador":

    st.header("🛠️ Gerenciador")

    st.warning(
        "Área administrativa. "
        "O sistema de autenticação será implementado posteriormente."
    )
