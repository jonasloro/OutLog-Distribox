import streamlit as st
import psycopg2


st.set_page_config(
    page_title="OutLog",
    page_icon="📦",
    layout="wide"
)


def conectar_supabase():
    """Conecta ao PostgreSQL do Supabase usando a connection string do Streamlit."""
    try:
        conn = psycopg2.connect(
            st.secrets["SUPABASE_DB_URL"]
        )
        return conn

    except Exception as e:
        st.error(f"Erro ao conectar ao Supabase: {e}")
        return None


st.title("📦 OutLog")
st.subheader("Teste de conexão com o Supabase")


conn = conectar_supabase()


if conn:

    st.success("🟢 Conectado ao Supabase!")

    try:

        with conn.cursor() as cursor:

            cursor.execute(
                "SELECT COUNT(*) FROM public.casulos_estrutura"
            )

            total_casulos = cursor.fetchone()[0]


        st.metric(
            "Casulos cadastrados",
            total_casulos
        )

        if total_casulos == 21:
            st.success("✅ Banco conectado e tabela casulos_estrutura encontrada!")

    except Exception as e:

        st.error(
            f"Conectou ao banco, mas houve erro na consulta: {e}"
        )

    finally:

        conn.close()

else:

    st.warning("🔴 Não foi possível conectar ao banco.")
