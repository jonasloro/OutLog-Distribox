"""Autenticação e cadastro de usuários (hash de senha + tabela no banco).

Extraído de app.py sem alterar lógica — só movido de lugar.
"""
import binascii
import hashlib
import hmac
import os

import streamlit as st

from core.database import obter_conexao_bd


def gerar_hash_senha(senha_texto_puro):
    """PBKDF2-HMAC-SHA256 com salt aleatório — não precisa de bcrypt/passlib,
    só o que já vem no Python padrão."""
    salt = os.urandom(16)
    hash_bytes = hashlib.pbkdf2_hmac('sha256', senha_texto_puro.encode('utf-8'), salt, 200_000)
    return binascii.hexlify(salt).decode() + ':' + binascii.hexlify(hash_bytes).decode()


def verificar_senha(senha_texto_puro, hash_armazenado):
    try:
        salt_hex, hash_hex = hash_armazenado.split(':')
        salt = binascii.unhexlify(salt_hex)
        hash_esperado = binascii.unhexlify(hash_hex)
        hash_calculado = hashlib.pbkdf2_hmac('sha256', senha_texto_puro.encode('utf-8'), salt, 200_000)
        return hmac.compare_digest(hash_calculado, hash_esperado)
    except Exception:
        return False


def carregar_usuarios_do_banco():
    conn = obter_conexao_bd()
    if conn is None:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT usuario, senha_hash, papel FROM usuarios")
            linhas = cur.fetchall()
        conn.close()
    except Exception as e:
        try:
            conn.close()
        except Exception:
            pass
        st.session_state.ultimo_erro_bd = str(e)
        return None
    return {usuario: {"senha_hash": senha_hash, "papel": papel} for usuario, senha_hash, papel in linhas}


def criar_usuario_no_banco(usuario, senha_hash, papel):
    conn = obter_conexao_bd()
    if conn is None:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO usuarios (usuario, senha_hash, papel, criado_em) VALUES (%s, %s, %s, now())",
                (usuario, senha_hash, papel)
            )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        try:
            conn.close()
        except Exception:
            pass
        st.session_state.ultimo_erro_bd = str(e)
        return False


def remover_usuario_no_banco(usuario):
    conn = obter_conexao_bd()
    if conn is None:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM usuarios WHERE usuario=%s", (usuario,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        try:
            conn.close()
        except Exception:
            pass
        st.session_state.ultimo_erro_bd = str(e)
        return False
