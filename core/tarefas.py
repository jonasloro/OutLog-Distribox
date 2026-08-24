"""Quadro de tarefas compartilhado entre os setores do app.

Cada setor (Recebimento, Qualidade, Processamento, Estocagem, Expedição,
Administração, e o módulo de Devoluções dentro de Expedição) pode ter suas
próprias tarefas, todas na mesma tabela `tarefas_app` do Supabase — dá pra
ver todo mundo junto (Visão Geral) ou filtrado por setor (cada Dashboard).

View em tabela editável (estilo Monday): cada tarefa é uma linha; preencher
a coluna Responsável move a tarefa automaticamente pra "Em Execução", e
limpar o Responsável volta pra "A Fazer". O Status também pode ser mudado
manualmente (ex.: marcar como Concluída) — nesse caso a mudança manual tem
prioridade sobre a automática feita na mesma edição.
"""
import pandas as pd
import psycopg2.extras
import streamlit as st

from core.database import obter_conexao_bd

STATUS_TAREFA = ["A Fazer", "Em Execução", "Concluída"]
SEM_RESPONSAVEL = ""

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


def criar_tarefa(titulo, descricao, setor, responsavel, criado_por, status=None):
    """Cria uma tarefa nova. Se `status` não for informado, usa 'Em Execução'
    quando já vem com responsável (estilo Monday: atribuir = já começou) ou
    'A Fazer' quando não vem."""
    status_final = status or ("Em Execução" if responsavel else "A Fazer")
    conn = obter_conexao_bd()
    if conn is None:
        return False
    try:
        with conn.cursor() as cur:
            _garantir_tabela(cur)
            cur.execute(
                "INSERT INTO tarefas_app (titulo, descricao, setor, responsavel, criado_por, status) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (titulo, descricao, setor, responsavel, criado_por, status_final),
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


def atualizar_tarefa(tarefa_id, **campos):
    """Atualiza qualquer combinação de titulo/descricao/status/responsavel.
    Passe só os campos que mudaram, ex.: atualizar_tarefa(5, status="Concluída").
    `responsavel=""` grava NULL (limpa o responsável)."""
    campos_validos = {"titulo", "descricao", "status", "responsavel"}
    campos = {k: v for k, v in campos.items() if k in campos_validos}
    if not campos:
        return True
    if "responsavel" in campos and campos["responsavel"] == "":
        campos["responsavel"] = None

    conn = obter_conexao_bd()
    if conn is None:
        return False
    try:
        with conn.cursor() as cur:
            _garantir_tabela(cur)
            set_sql = ", ".join(f"{col} = %s" for col in campos) + ", atualizado_em = now()"
            valores = list(campos.values()) + [tarefa_id]
            cur.execute(f"UPDATE tarefas_app SET {set_sql} WHERE id = %s", valores)
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
    """Widget pronto: tabela editável (estilo Monday 'Main Table').

    - Editar a coluna Responsável e sair da célula já aplica a mudança.
    - Preencher Responsável numa tarefa 'A Fazer' move ela pra 'Em Execução'
      automaticamente; limpar o Responsável de uma tarefa 'Em Execução' volta
      ela pra 'A Fazer'. Mudar o Status manualmente na mesma edição tem
      prioridade sobre essa regra automática.
    - Última linha em branco serve pra criar tarefa nova (basta preencher o
      Título; Responsável é opcional).
    - Apagar uma linha (menu de contexto da tabela) remove a tarefa.
    """
    if mostrar_titulo:
        st.markdown("<h4 style='color: #ffcc00;'>📋 Quadro de Tarefas</h4>", unsafe_allow_html=True)

    tarefas = carregar_tarefas(setor)
    if tarefas is None:
        st.warning(f"⚠️ Não foi possível carregar as tarefas. Detalhe: `{st.session_state.get('ultimo_erro_bd')}`")
        return

    usuarios_disponiveis = usuarios_disponiveis or []
    opcoes_responsavel = [SEM_RESPONSAVEL] + usuarios_disponiveis

    linhas = [
        {
            "id": t["id"],
            "titulo": t["titulo"],
            "descricao": t["descricao"] or "",
            "responsavel": t["responsavel"] or SEM_RESPONSAVEL,
            "status": t["status"],
            "atualizado": t["atualizado_em"].strftime("%d/%m %H:%M") if t["atualizado_em"] else "",
        }
        for t in tarefas
    ]
    df = pd.DataFrame(linhas, columns=["id", "titulo", "descricao", "responsavel", "status", "atualizado"])

    editor_key = f"tabela_tarefas_{setor}"
    st.data_editor(
        df,
        key=editor_key,
        hide_index=True,
        num_rows="dynamic",
        use_container_width=True,
        column_order=["titulo", "descricao", "responsavel", "status", "atualizado"],
        column_config={
            "id": None,
            "titulo": st.column_config.TextColumn("Tarefa", required=True, width="medium"),
            "descricao": st.column_config.TextColumn("Descrição", width="large"),
            "responsavel": st.column_config.SelectboxColumn(
                "Responsável", options=opcoes_responsavel, width="small",
            ),
            "status": st.column_config.SelectboxColumn(
                "Status", options=STATUS_TAREFA, width="small",
            ),
            "atualizado": st.column_config.TextColumn("Atualizado em", disabled=True, width="small"),
        },
    )

    estado = st.session_state.get(editor_key, {})
    houve_mudanca = False

    # Linhas editadas (por índice da linha na tabela mostrada)
    for idx, mudancas in estado.get("edited_rows", {}).items():
        linha_original = df.iloc[idx]
        tarefa_id = linha_original["id"]
        campos_para_salvar = dict(mudancas)

        # Regra automática: se mexeu no responsável e não mexeu no status
        # na mesma edição, deriva o status.
        if "responsavel" in mudancas and "status" not in mudancas:
            novo_responsavel = mudancas["responsavel"]
            status_atual = linha_original["status"]
            if novo_responsavel and status_atual == "A Fazer":
                campos_para_salvar["status"] = "Em Execução"
            elif not novo_responsavel and status_atual == "Em Execução":
                campos_para_salvar["status"] = "A Fazer"

        if atualizar_tarefa(tarefa_id, **campos_para_salvar):
            houve_mudanca = True
        else:
            st.error(f"Não foi possível salvar a alteração. `{st.session_state.get('ultimo_erro_bd')}`")

    # Linhas novas (adicionadas na última linha em branco da tabela)
    for nova in estado.get("added_rows", []):
        titulo = (nova.get("titulo") or "").strip()
        if not titulo:
            continue
        responsavel = nova.get("responsavel") or None
        descricao = (nova.get("descricao") or "").strip()
        if criar_tarefa(titulo, descricao, setor, responsavel, st.session_state.get("usuario_atual")):
            houve_mudanca = True
        else:
            st.error(f"Não foi possível criar a tarefa. `{st.session_state.get('ultimo_erro_bd')}`")

    # Linhas removidas
    for idx in estado.get("deleted_rows", []):
        tarefa_id = df.iloc[idx]["id"]
        if remover_tarefa(tarefa_id):
            houve_mudanca = True

    if houve_mudanca:
        st.rerun()
