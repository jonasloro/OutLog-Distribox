"""Configuração explícita de acesso temporário sem login para demonstração.

Nunca ativar automaticamente quando o banco de dados estiver indisponível:
a indisponibilidade do Supabase não deve abrir o sistema ao público.
"""
import os

import streamlit as st


def modo_demonstracao_ativo() -> bool:
    """Sem login apenas com OUTLOG_DEMO_MODE=true no servidor ou Secrets."""
    valor = os.getenv("OUTLOG_DEMO_MODE", "")
    if not valor:
        try:
            valor = st.secrets.get("OUTLOG_DEMO_MODE", "")
        except (FileNotFoundError, KeyError, OSError):
            valor = ""
    return str(valor).strip().lower() in {"1", "true", "sim", "yes", "on"}
