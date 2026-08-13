import streamlit as st
import psycopg2

st.set_page_config(
    page_title="OutLog",
    page_icon="📦",
    layout="wide"
)


def conectar_supabase():
    """Conecta ao PostgreSQL do Supabase usando os Secrets do Streamlit."""
    try:
        return psycopg2.connect(
            host=st.secrets["SUPABASE_HOST"],
            port=st.secrets["SUPABASE_PORT"],
            database=st.secrets["SUPABASE_DATABASE"],
            user=st.secrets["SUPABASE_USER"],
            password=st.secrets["SUPABASE_PASSWORD"]
        )
    except Exception as e:
        st.error(f"Erro ao conectar ao Supabase: {e}")
        return None


st.title("📦 OutLog")
st.subheader("Teste de conexão com o Supabase")

conn = conectar_supabase()

if conn is None:
    st.warning("🔴 Não foi possível conectar ao banco.")
else:
    st.success("🟢 Conectado ao Supabase!")

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM public.casulos_estrutura"
            )

            total = cursor.fetchone()[0]

        st.metric(
            "Casulos cadastrados no banco",
            total
        )

    except Exception as e:
        st.error(f"Erro ao consultar o banco: {e}")

    finally:
        conn.close()
