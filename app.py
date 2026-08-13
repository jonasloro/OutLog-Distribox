import streamlit as st
import psycopg2

# ============================================================
# CONFIGURAÇÃO DA PÁGINA
# ============================================================

st.set_page_config(
    page_title="OutLog",
    page_icon="📦",
    layout="wide"
)


# ============================================================
# FUNÇÃO DE CONEXÃO COM O SUPABASE
# ============================================================

def conectar_supabase():
    """
    Abre uma conexão com o PostgreSQL do Supabase.

    As credenciais ficam nos Secrets do Streamlit.
    """

    try:
        conn = psycopg2.connect(
            host=st.secrets["SUPABASE_HOST"],
            port=st.secrets["SUPABASE_PORT"],
            database=st.secrets["SUPABASE_DATABASE"],
            user=st.secrets["SUPABASE_USER"],
            password=st.secrets["SUPABASE_PASSWORD"]
        )

        return conn

    except Exception as e:
        st.error(f"Erro ao conectar ao Supabase: {e}")
        return None


# ============================================================
# TESTE DA CONEXÃO
# ============================================================

st.title("📦 OutLog")

st.subheader("Teste de conexão com o Supabase")

conn = conectar_supabase()

if conn:

    st.success("🟢 Conectado ao Supabase!")

    try:

        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM public.casulos_estrutura")

        total = cursor.fetchone()[0]

        cursor.close()
        conn.close()

        st.metric(
            "Casulos cadastrados",
            total
        )

    except Exception as e:

        st.error(
            f"Conectou ao Supabase, mas ocorreu um erro na consulta: {e}"
        )

else:

    st.warning(
        "Não foi possível estabelecer conexão com o banco."
    )
