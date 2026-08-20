"""Conexão com o banco de dados principal (PostgreSQL/Supabase).

Extraído de app.py sem alterar nenhuma linha de lógica — só movido de
lugar. Depende de PSYCOPG2_DISPONIVEL e psycopg2, que continuam
importados em app.py; para manter este módulo independente, ele faz a
própria checagem de import.
"""
import streamlit as st

try:
    import psycopg2
    PSYCOPG2_DISPONIVEL = True
except ImportError:
    PSYCOPG2_DISPONIVEL = False


def _obter_config_bd():
    """Retorna as credenciais do banco a partir dos Secrets do Streamlit."""
    try:
        if "SUPABASE_HOST" in st.secrets:
            return {
                "host": st.secrets["SUPABASE_HOST"],
                "port": int(st.secrets.get("SUPABASE_PORT", 5432)),
                "dbname": st.secrets.get("SUPABASE_DATABASE", "postgres"),
                "user": st.secrets["SUPABASE_USER"],
                "password": st.secrets["SUPABASE_PASSWORD"],
            }

        if "postgres" in st.secrets:
            cfg = st.secrets["postgres"]
            return {
                "host": cfg["host"],
                "port": int(cfg.get("port", 5432)),
                "dbname": cfg.get("dbname", "postgres"),
                "user": cfg["user"],
                "password": cfg["password"],
            }
    except Exception as e:
        st.session_state.ultimo_erro_bd = f"Secrets do banco inválidos/incompletos: {e}"
        return None

    st.session_state.ultimo_erro_bd = (
        "Secrets do banco não configurados. Use SUPABASE_HOST, SUPABASE_PORT, "
        "SUPABASE_DATABASE, SUPABASE_USER e SUPABASE_PASSWORD em "
        "Settings → Secrets do Streamlit."
    )
    return None


def obter_conexao_bd():
    if not PSYCOPG2_DISPONIVEL:
        st.session_state.ultimo_erro_bd = (
            "biblioteca 'psycopg2-binary' não instalada — "
            "adicione psycopg2-binary ao requirements.txt do repositório"
        )
        return None

    cfg = _obter_config_bd()
    if cfg is None:
        return None

    try:
        conn = psycopg2.connect(
            host=cfg["host"],
            port=cfg["port"],
            dbname=cfg["dbname"],
            user=cfg["user"],
            password=cfg["password"],
            sslmode="require",
            connect_timeout=10,
        )
        st.session_state.ultimo_erro_bd = None
        return conn
    except Exception as e:
        st.session_state.ultimo_erro_bd = f"falha ao conectar no Postgres/Supabase: {e}"
        return None


def testar_conexao_bd():
    """Testa a conexão e fecha o socket para não deixar conexões penduradas."""
    conn = obter_conexao_bd()
    if conn is None:
        return False
    try:
        conn.close()
        return True
    except Exception as e:
        st.session_state.ultimo_erro_bd = f"falha ao fechar conexão de teste: {e}"
        return False
