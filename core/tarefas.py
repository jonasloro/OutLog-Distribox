"""Quadro de tarefas compartilhado entre os setores do app.

Cada setor (Recebimento, Qualidade, Processamento, Estocagem, Expedição,
Administração, e o módulo de Devoluções dentro de Expedição) pode ter suas
próprias tarefas, todas na mesma tabela `tarefas_app` do Supabase — dá pra
ver todo mundo junto (Visão Geral) ou filtrado por setor (cada Dashboard).
"""
import psycopg2.extras
import streamlit as st

from core.database import obter_conexao_bd

STATUS_TAREFA = ["A Fazer", "Em Execução", "Concluída"]

SQL_CRIAR_TABELA = """
CREATE TABLE IF NOT EXISTS tarefas_app (
    id SERIAL PRIMARY KEY,
    titulo TEXT NOT NULL,
    descricao TEXT,
    setor TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'A Fazer',
    responsavel TEXT,
    criado_por TEXT,
    criado_em TIMESTAMP NOT NULL DEFAULT now(),
    atualizado_em TIMESTAMP NOT NULL DEFAULT now()
);
"""


def _garantir_tabela(cur):
    try:
        cur.execute(SQL_CRIAR_TABELA)
    except Exception:
        pass


def carregar_tarefas(setor=None):
    conn = obter_conexao_bd()
    if conn is None:
        return None
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            _garantir_tabela(cur)
            conn.commit()
            if setor:
                cur.execute(
                    "SELECT * FROM tarefas_app WHERE setor = %s ORDER BY "
                    "CASE status WHEN 'Em Execução' THEN 0 WHEN 'A Fazer' THEN 1 ELSE 2 END, "
                    "atualizado_em DESC",
                    (setor,),
                )
            else:
                cur.execute(
                    "SELECT * FROM tarefas_app ORDER BY "
                    "CASE status WHEN 'Em Execução' THEN 0 WHEN 'A Fazer' THEN 1 ELSE 2 END, "
                    "atualizado_em DESC"
                )
            linhas = cur.fetchall()
        conn.close()
        return linhas
    except Exception as e:
        try:
            conn.rollback()
            conn.close()
        except Exception:
            pass
        st.session_state.ultimo_erro_bd = f"falha ao carregar tarefas: {e}"
        return None


def criar_tarefa(titulo, descricao, setor, responsavel, criado_por):
    conn = obter_conexao_bd()
    if conn is None:
        return False
    try:
        with conn.cursor() as cur:
            _garantir_tabela(cur)
            cur.execute(
                "INSERT INTO tarefas_app (titulo, descricao, setor, responsavel, criado_por) "
                "VALUES (%s, %s, %s, %s, %s)",
                (titulo, descricao, setor, responsavel, criado_por),
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
        st.session_state.ultimo_erro_bd = f"falha ao criar tarefa: {e}"
        return False


def atualizar_tarefa(tarefa_id, status=None, responsavel=None):
    conn = obter_conexao_bd()
    if conn is None:
        return False
    try:
        with conn.cursor() as cur:
            _garantir_tabela(cur)
            if status is not None:
                cur.execute(
                    "UPDATE tarefas_app SET status = %s, atualizado_em = now() WHERE id = %s",
                    (status, tarefa_id),
                )
            if responsavel is not None:
                cur.execute(
                    "UPDATE tarefas_app SET responsavel = %s, atualizado_em = now() WHERE id = %s",
                    (responsavel, tarefa_id),
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
        st.session_state.ultimo_erro_bd = f"falha ao atualizar tarefa: {e}"
        return False


def remover_tarefa(tarefa_id):
    conn = obter_conexao_bd()
    if conn is None:
        return False
    try:
        with conn.cursor() as cur:
            _garantir_tabela(cur)
            cur.execute("DELETE FROM tarefas_app WHERE id = %s", (tarefa_id,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        try:
            conn.rollback()
            conn.close()
        except Exception:
            pass
        st.session_state.ultimo_erro_bd = f"falha ao remover tarefa: {e}"
        return False


def renderizar_quadro_tarefas(setor, usuarios_disponiveis=None, mostrar_titulo=True):
    """Widget pronto: 3 colunas (A Fazer / Em Execução / Concluída), com
    formulário de nova tarefa e botões pra mover/remover. `setor` é usado
    tanto pra filtrar quanto pra gravar a tarefa nova nesse setor.
    """
    if mostrar_titulo:
        st.markdown("<h4 style='color: #ffcc00;'>📋 Quadro de Tarefas</h4>", unsafe_allow_html=True)

    tarefas = carregar_tarefas(setor)
    if tarefas is None:
        st.warning(f"⚠️ Não foi possível carregar as tarefas. Detalhe: `{st.session_state.get('ultimo_erro_bd')}`")
        return

    usuarios_disponiveis = usuarios_disponiveis or []
    opcoes_responsavel = ["(sem responsável)"] + usuarios_disponiveis

    with st.expander("➕ Nova tarefa"):
        with st.form(key=f"form_nova_tarefa_{setor}", clear_on_submit=True):
            titulo_novo = st.text_input("Título")
            descricao_nova = st.text_area("Descrição (opcional)", height=80)
            responsavel_novo = st.selectbox("Responsável", opcoes_responsavel, key=f"resp_novo_{setor}")
            enviar = st.form_submit_button("Criar tarefa", type="primary")
            if enviar:
                if not titulo_novo.strip():
                    st.error("Dê um título pra tarefa.")
                else:
                    resp = None if responsavel_novo == "(sem responsável)" else responsavel_novo
                    if criar_tarefa(titulo_novo.strip(), descricao_nova.strip(), setor, resp, st.session_state.get("usuario_atual")):
                        st.success("Tarefa criada.")
                        st.rerun()
                    else:
                        st.error(f"Não foi possível criar a tarefa. `{st.session_state.get('ultimo_erro_bd')}`")

    if not tarefas:
        st.caption("Nenhuma tarefa cadastrada pra este setor ainda.")
        return

    colunas_status = st.columns(len(STATUS_TAREFA))
    for idx, status in enumerate(STATUS_TAREFA):
        with colunas_status[idx]:
            emoji = {"A Fazer": "⬜", "Em Execução": "🟡", "Concluída": "✅"}[status]
            st.markdown(f"**{emoji} {status}**")
            tarefas_da_coluna = [t for t in tarefas if t["status"] == status]
            if not tarefas_da_coluna:
                st.caption("—")
            for t in tarefas_da_coluna:
                responsavel_txt = t["responsavel"] or "sem responsável"
                with st.container(border=True):
                    st.markdown(f"**{t['titulo']}**")
                    if t["descricao"]:
                        st.caption(t["descricao"])
                    st.caption(f"👤 {responsavel_txt}")

                    if status == "A Fazer":
                        # Estilo Monday: "pegar a tarefa" atribui o usuário atual
                        # e já move pra Em Execução, numa ação só.
                        if st.button(
                            "🚀 Iniciar tarefa", key=f"btn_iniciar_{setor}_{t['id']}",
                            use_container_width=True, type="primary",
                        ):
                            usuario_atual = st.session_state.get("usuario_atual")
                            if atualizar_tarefa(t["id"], status="Em Execução", responsavel=usuario_atual):
                                st.rerun()
                        with st.expander("Mover manualmente"):
                            outros_status = [s for s in STATUS_TAREFA if s != status]
                            novo_status = st.selectbox(
                                "Mover para", outros_status, key=f"mover_{setor}_{t['id']}",
                                label_visibility="collapsed",
                            )
                            if st.button("➡️ Mover", key=f"btn_mover_{setor}_{t['id']}", use_container_width=True):
                                if atualizar_tarefa(t["id"], status=novo_status):
                                    st.rerun()
                    else:
                        outros_status = [s for s in STATUS_TAREFA if s != status]
                        c1, c2 = st.columns(2)
                        with c1:
                            novo_status = st.selectbox(
                                "Mover para", outros_status, key=f"mover_{setor}_{t['id']}",
                                label_visibility="collapsed",
                            )
                        with c2:
                            if st.button("➡️", key=f"btn_mover_{setor}_{t['id']}", use_container_width=True):
                                if atualizar_tarefa(t["id"], status=novo_status):
                                    st.rerun()

                    if st.button("🗑️ Remover", key=f"btn_remover_{setor}_{t['id']}", use_container_width=True):
                        if remover_tarefa(t["id"]):
                            st.rerun()
