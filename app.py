import streamlit as st
import psycopg2


st.set_page_config(
    page_title="OutLog",
    page_icon="📦",
    layout="wide"
)


def conectar_supabase():
    """
    Conecta ao PostgreSQL do Supabase usando o Session Pooler.
    As credenciais ficam protegidas nos Secrets do Streamlit.
    """

    try:
        conn = psycopg2.connect(
            host=st.secrets["SUPABASE_HOST"],
            port=int(st.secrets["SUPABASE_PORT"]),
            database=st.secrets["SUPABASE_DATABASE"],
            user=st.secrets["SUPABASE_USER"],
            password=st.secrets["SUPABASE_PASSWORD"],
            sslmode="require"
        )

        return conn

    except Exception as e:
        st.error(f"Erro ao conectar ao Supabase: {e}")
        return None


st.title("📦 OutLog")
st.subheader("Teste de conexão com o Supabase")


conn = conectar_supabase()


if conn is None:

    st.error("🔴 Não foi possível conectar ao banco.")

else:

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

            st.success(
                "✅ Conexão funcionando! Os 21 casulos foram encontrados."
            )

        else:

            st.warning(
                f"Conexão funcionando, mas foram encontrados "
                f"{total_casulos} registros."
            )

    except Exception as e:

        st.error(
            f"Conectou ao banco, mas ocorreu um erro na consulta: {e}"
        )

    finally:

        conn.close()
