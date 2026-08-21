"""Mapeamento entre o 'Grupo' do relatório do SGO (classificação do ERP,
ex: 'Camisetas', 'Calças') e o tipo de casulo (aramado_P/M/G, metal_raso,
metal_profundo, madeira) em que essa mercadoria normalmente é guardada.

Não existe um jeito automático de bater os dois — o Grupo do SGO e as
categorias da tabela de capacidade são parecidos mas não idênticos — então
esse mapeamento é feito manualmente pelo usuário, uma vez por Grupo, e fica
salvo. É a peça que falta pro indicador 'quantos casulos a mercadoria em
trânsito vai precisar' (usa a densidade fixa já cadastrada por tipo).
"""
import streamlit as st

from core.database import obter_conexao_bd

TIPOS_CASULO = ["aramado_P", "aramado_M", "aramado_G", "metal_raso", "metal_profundo", "madeira"]

SQL_CRIAR_TABELA = """
CREATE TABLE IF NOT EXISTS mapa_grupo_tipo_casulo (
    grupo TEXT PRIMARY KEY,
    tipo_estrutural TEXT NOT NULL,
    atualizado_em TIMESTAMP NOT NULL DEFAULT now()
);
"""


def _garantir_tabela(cur):
    try:
        cur.execute(SQL_CRIAR_TABELA)
    except Exception:
        pass


def carregar_mapa_grupo_tipo():
    """Retorna {grupo: tipo_estrutural}. None se não conseguiu conectar."""
    conn = obter_conexao_bd()
    if conn is None:
        return None
    try:
        with conn.cursor() as cur:
            _garantir_tabela(cur)
            conn.commit()
            cur.execute("SELECT grupo, tipo_estrutural FROM mapa_grupo_tipo_casulo")
            linhas = cur.fetchall()
        conn.close()
        return {row["grupo"]: row["tipo_estrutural"] for row in linhas}
    except Exception as e:
        try:
            conn.rollback()
            conn.close()
        except Exception:
            pass
        st.session_state.ultimo_erro_bd = f"falha ao carregar mapa grupo→tipo: {e}"
        return None


def salvar_mapeamento_grupo(grupo, tipo_estrutural):
    conn = obter_conexao_bd()
    if conn is None:
        return False
    try:
        with conn.cursor() as cur:
            _garantir_tabela(cur)
            cur.execute(
                """
                INSERT INTO mapa_grupo_tipo_casulo (grupo, tipo_estrutural, atualizado_em)
                VALUES (%s, %s, now())
                ON CONFLICT (grupo) DO UPDATE SET
                    tipo_estrutural = EXCLUDED.tipo_estrutural,
                    atualizado_em = now()
                """,
                (grupo, tipo_estrutural),
            )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        try:
            conn.rollback()
            conn.close()
        except Exception:
            pass
        st.session_state.ultimo_erro_bd = f"falha ao salvar mapeamento: {e}"
        return False


def remover_mapeamento_grupo(grupo):
    conn = obter_conexao_bd()
    if conn is None:
        return False
    try:
        with conn.cursor() as cur:
            _garantir_tabela(cur)
            cur.execute("DELETE FROM mapa_grupo_tipo_casulo WHERE grupo = %s", (grupo,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        try:
            conn.rollback()
            conn.close()
        except Exception:
            pass
        st.session_state.ultimo_erro_bd = f"falha ao remover mapeamento: {e}"
        return False
