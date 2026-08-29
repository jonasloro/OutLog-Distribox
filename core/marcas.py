"""Lista de marcas conhecidas por Grupo, extraída do relatório 'Resumo de
Estoque do Grupo' (o mesmo PDF usado em Importar Relatório de Estoque). É
usada pra reconhecer automaticamente a Marca de um item do relatório do
SGO a partir da Descrição — o SGO não tem coluna Marca própria.

Reprocessada por completo a cada novo upload do Resumo de Estoque do
Grupo (ver app.py, tela "Importar Relatório de Estoque"): a tabela inteira
é substituída, não é editável manualmente e não fica "incremental".
"""
import streamlit as st

from core.database import obter_conexao_bd

SQL_CRIAR_TABELA = """
CREATE TABLE IF NOT EXISTS marcas_por_grupo (
    grupo TEXT NOT NULL,
    marca TEXT NOT NULL,
    PRIMARY KEY (grupo, marca)
);
"""


def _garantir_tabela(cur):
    try:
        cur.execute(SQL_CRIAR_TABELA)
    except Exception:
        pass


def salvar_marcas_por_grupo(marcas_por_grupo):
    """Substitui TODO o conteúdo da tabela pelo dicionário {grupo: [marcas]}
    recém-extraído do PDF — reprocessamento completo, não incremental.

    Grava em blocos multi-valor (não linha por linha) — com executemany()
    o psycopg2 manda uma instrução por linha, uma de cada vez; um relatório
    com milhares de combinações Grupo+Marca levava bem mais tempo assim."""
    conn = obter_conexao_bd()
    if conn is None:
        return False
    try:
        with conn.cursor() as cur:
            _garantir_tabela(cur)
            cur.execute("DELETE FROM marcas_por_grupo")
            linhas = [(g, m) for g, marcas in marcas_por_grupo.items() for m in marcas]
            tamanho_bloco = 500
            for i in range(0, len(linhas), tamanho_bloco):
                bloco = linhas[i:i + tamanho_bloco]
                marcadores = ", ".join(["(%s, %s)"] * len(bloco))
                valores = [v for par in bloco for v in par]
                cur.execute(
                    f"INSERT INTO marcas_por_grupo (grupo, marca) VALUES {marcadores} "
                    "ON CONFLICT DO NOTHING",
                    valores,
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
        st.session_state.ultimo_erro_bd = f"falha ao salvar marcas por grupo: {e}"
        return False


def carregar_marcas_por_grupo():
    """Retorna {grupo: [marcas]}. None se não conseguiu conectar."""
    conn = obter_conexao_bd()
    if conn is None:
        return None
    try:
        with conn.cursor() as cur:
            _garantir_tabela(cur)
            conn.commit()
            cur.execute("SELECT grupo, marca FROM marcas_por_grupo ORDER BY grupo, marca")
            linhas = cur.fetchall()
        conn.close()
        mapa = {}
        for grupo, marca in linhas:
            mapa.setdefault(grupo, []).append(marca)
        return mapa
    except Exception as e:
        try:
            conn.rollback()
            conn.close()
        except Exception:
            pass
        st.session_state.ultimo_erro_bd = f"falha ao carregar marcas por grupo: {e}"
        return None


def extrair_marca_da_descricao(grupo, descricao, marcas_por_grupo=None):
    """Acha, entre as marcas conhecidas daquele Grupo, qual aparece dentro
    da Descrição. Prioriza o nome de marca mais longo primeiro, pra não
    casar por engano um nome que é prefixo de outro (ex.: 'DIMY' dentro de
    algo que na verdade é 'DIMY PROMO' já vira só 'DIMY' na lista, então
    esse caso específico não ocorre, mas a ordenação protege casos
    parecidos com outras marcas).

    O Grupo do relatório do SGO costuma ser mais genérico que o Grupo do
    Resumo de Estoque (ex.: SGO tem só "CAMISETA", enquanto o Resumo tem
    "CAMISETA FEMIN", "CAMISETA MC MASC", "CAMISETA ML MASC" separados).
    Se não achar o Grupo exato, cai pra um fallback: junta as marcas de
    TODOS os grupos do Resumo que começam com o Grupo do SGO."""
    if not grupo or not descricao:
        return None
    mapa = marcas_por_grupo if marcas_por_grupo is not None else (st.session_state.get("marcas_por_grupo") or {})
    grupo_upper = grupo.strip().upper()

    candidatas = mapa.get(grupo) or mapa.get(grupo_upper)
    if not candidatas:
        candidatas = []
        vistas = set()
        for chave, marcas in mapa.items():
            if chave.strip().upper().startswith(grupo_upper):
                for m in marcas:
                    if m not in vistas:
                        vistas.add(m)
                        candidatas.append(m)

    descricao_upper = descricao.upper()
    for marca in sorted(candidatas, key=len, reverse=True):
        if marca in descricao_upper:
            return marca
    return None
