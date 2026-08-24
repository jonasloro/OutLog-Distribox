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

Tarefas de produção (setor Processamento) podem carregar Grupo + Marca.
Toda vez que uma tarefa entra em "Em Execução" o app marca o horário de
início (`iniciado_em`); quando ela é concluída, grava quanto tempo levou
num histórico (`historico_producao_tempo`), associado ao par Grupo+Marca —
é a base da previsão de tempo de produção do Dashboard Processamento.
"""
import pandas as pd
import psycopg2.extras
import streamlit as st

from core.database import obter_conexao_bd

STATUS_TAREFA = ["A Fazer", "Em Execução", "Concluída"]
SEM_RESPONSAVEL = ""

TIPOS_TAREFA_PADRAO = ["Triagem", "Etiquetagem", "Cadastro"]
CORES_TIPO_TAREFA = {
    "Triagem": "#4a90d9",
    "Etiquetagem": "#e0a030",
    "Cadastro": "#7cb342",
}

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

# Colunas adicionadas depois da criação original da tabela — ADD COLUMN IF
# NOT EXISTS pra não quebrar instalações que já tinham tarefas_app antes
# dessas colunas existirem.
SQL_ALTERACOES = [
    "ALTER TABLE tarefas_app ADD COLUMN IF NOT EXISTS grupo TEXT",
    "ALTER TABLE tarefas_app ADD COLUMN IF NOT EXISTS marca TEXT",
    "ALTER TABLE tarefas_app ADD COLUMN IF NOT EXISTS iniciado_em TIMESTAMP",
    "ALTER TABLE tarefas_app ADD COLUMN IF NOT EXISTS tipo TEXT",
]

SQL_CRIAR_HISTORICO = """
CREATE TABLE IF NOT EXISTS historico_producao_tempo (
    id SERIAL PRIMARY KEY,
    grupo TEXT NOT NULL,
    marca TEXT NOT NULL,
    minutos NUMERIC NOT NULL,
    concluido_em TIMESTAMP NOT NULL DEFAULT now()
);
"""


def _garantir_tabela(cur):
    try:
        cur.execute(SQL_CRIAR_TABELA)
    except Exception:
        pass
    for alteracao in SQL_ALTERACOES:
        try:
            cur.execute(alteracao)
        except Exception:
            pass
    try:
        cur.execute(SQL_CRIAR_HISTORICO)
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


def criar_tarefa(titulo, descricao, setor, responsavel, criado_por, status=None, grupo=None, marca=None, tipo=None):
    """Cria uma tarefa nova. Se `status` não for informado, usa 'Em Execução'
    quando já vem com responsável (estilo Monday: atribuir = já começou) ou
    'A Fazer' quando não vem. Se já nasce 'Em Execução', já marca o início
    (iniciado_em) — importante pra previsão de tempo funcionar mesmo em
    tarefas criadas direto na coluna 'Em Execução'."""
    status_final = status or ("Em Execução" if responsavel else "A Fazer")
    grupo = grupo or None
    marca = marca or None
    tipo = tipo or None
    conn = obter_conexao_bd()
    if conn is None:
        return False
    try:
        with conn.cursor() as cur:
            _garantir_tabela(cur)
            if status_final == "Em Execução":
                cur.execute(
                    "INSERT INTO tarefas_app (titulo, descricao, setor, responsavel, criado_por, status, grupo, marca, tipo, iniciado_em) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, now())",
                    (titulo, descricao, setor, responsavel, criado_por, status_final, grupo, marca, tipo),
                )
            else:
                cur.execute(
                    "INSERT INTO tarefas_app (titulo, descricao, setor, responsavel, criado_por, status, grupo, marca, tipo) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (titulo, descricao, setor, responsavel, criado_por, status_final, grupo, marca, tipo),
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
    """Atualiza qualquer combinação de titulo/descricao/status/responsavel/
    grupo/marca. `responsavel=""` grava NULL (limpa o responsável).

    Dois campos especiais, não gravados diretamente:
    - iniciar=True: marca iniciado_em = now() (só se ainda não tinha um
      início em aberto — não reinicia o cronômetro de uma tarefa já
      rodando).
    - concluir=True: fecha o ciclo — grava no histórico de tempo de
      produção quantos minutos essa tarefa levou (agora - iniciado_em),
      usando o Grupo/Marca que a tarefa tem no banco. Só grava histórico
      se a tarefa tinha iniciado_em E Grupo E Marca preenchidos; senão só
      limpa o iniciado_em silenciosamente (tarefa sem esses dados não
      entra na previsão, mas não trava a conclusão)."""
    iniciar = bool(campos.pop("iniciar", False))
    concluir = bool(campos.pop("concluir", False))

    campos_validos = {"titulo", "descricao", "status", "responsavel", "grupo", "marca", "tipo"}
    campos = {k: v for k, v in campos.items() if k in campos_validos}
    if "responsavel" in campos and campos["responsavel"] == "":
        campos["responsavel"] = None

    conn = obter_conexao_bd()
    if conn is None:
        return False
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            _garantir_tabela(cur)

            if concluir:
                cur.execute(
                    "SELECT grupo, marca, iniciado_em FROM tarefas_app WHERE id = %s",
                    (tarefa_id,),
                )
                atual = cur.fetchone()
                if atual and atual["iniciado_em"] and atual["grupo"] and atual["marca"]:
                    cur.execute(
                        "INSERT INTO historico_producao_tempo (grupo, marca, minutos, concluido_em) "
                        "VALUES (%s, %s, EXTRACT(EPOCH FROM (now() - %s)) / 60, now())",
                        (atual["grupo"], atual["marca"], atual["iniciado_em"]),
                    )
                campos["iniciado_em"] = None

            set_partes = [f"{col} = %s" for col in campos]
            valores = list(campos.values())
            if iniciar:
                set_partes.append("iniciado_em = COALESCE(iniciado_em, now())")
            if set_partes:
                set_partes.append("atualizado_em = now()")
                valores.append(tarefa_id)
                cur.execute(f"UPDATE tarefas_app SET {', '.join(set_partes)} WHERE id = %s", valores)
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


def calcular_previsao_tempo(grupo, marca):
    """Média (em minutos) do histórico de produção pra esse Grupo+Marca.
    Retorna None se não conseguiu conectar ou não tiver histórico ainda;
    senão {"media_minutos": float, "amostras": int}."""
    if not grupo or not marca:
        return None
    conn = obter_conexao_bd()
    if conn is None:
        return None
    try:
        with conn.cursor() as cur:
            _garantir_tabela(cur)
            cur.execute(
                "SELECT AVG(minutos), COUNT(*) FROM historico_producao_tempo WHERE grupo = %s AND marca = %s",
                (grupo, marca),
            )
            media, contagem = cur.fetchone()
        conn.close()
        if not contagem:
            return None
        return {"media_minutos": float(media), "amostras": int(contagem)}
    except Exception as e:
        try:
            conn.rollback()
            conn.close()
        except Exception:
            pass
        st.session_state.ultimo_erro_bd = f"falha ao calcular previsão de tempo: {e}"
        return None


def _aplicar_edicoes_tabela(df, estado, setor, criado_por, status_fixo_para_novas=None):
    """Lógica compartilhada entre a tabela única (renderizar_quadro_tarefas)
    e os 3 quadros separados (renderizar_paineis_tarefas): processa
    edited_rows/added_rows/deleted_rows de um st.data_editor e aplica no
    banco. Retorna True se algo mudou (pra quem chamou decidir se dá
    st.rerun())."""
    houve_mudanca = False

    for idx, mudancas in estado.get("edited_rows", {}).items():
        linha_original = df.iloc[idx]
        tarefa_id = linha_original["id"]
        campos_para_salvar = dict(mudancas)

        if "responsavel" in mudancas and "status" not in mudancas:
            novo_responsavel = mudancas["responsavel"]
            status_atual = linha_original["status"]
            if novo_responsavel and status_atual == "A Fazer":
                campos_para_salvar["status"] = "Em Execução"
            elif not novo_responsavel and status_atual == "Em Execução":
                campos_para_salvar["status"] = "A Fazer"
                campos_para_salvar["iniciado_em"] = None

        status_final = campos_para_salvar.get("status")
        if status_final == "Em Execução" and linha_original["status"] != "Em Execução":
            campos_para_salvar["iniciar"] = True
        if status_final == "Concluída" and linha_original["status"] != "Concluída":
            campos_para_salvar["concluir"] = True

        if atualizar_tarefa(tarefa_id, **campos_para_salvar):
            houve_mudanca = True
        else:
            st.error(f"Não foi possível salvar a alteração. `{st.session_state.get('ultimo_erro_bd')}`")

    for nova in estado.get("added_rows", []):
        titulo = (nova.get("titulo") or "").strip()
        if not titulo:
            continue
        responsavel = nova.get("responsavel") or None
        descricao = (nova.get("descricao") or "").strip()
        grupo = (nova.get("grupo") or "").strip() or None
        marca = (nova.get("marca") or "").strip() or None
        status_nova = status_fixo_para_novas or nova.get("status")
        if criar_tarefa(titulo, descricao, setor, responsavel, criado_por, status=status_nova, grupo=grupo, marca=marca):
            houve_mudanca = True
        else:
            st.error(f"Não foi possível criar a tarefa. `{st.session_state.get('ultimo_erro_bd')}`")

    for idx in estado.get("deleted_rows", []):
        tarefa_id = df.iloc[idx]["id"]
        if remover_tarefa(tarefa_id):
            houve_mudanca = True

    return houve_mudanca


def _df_de_tarefas(tarefas):
    linhas = [
        {
            "id": t["id"],
            "titulo": t["titulo"],
            "descricao": t["descricao"] or "",
            "responsavel": t["responsavel"] or SEM_RESPONSAVEL,
            "status": t["status"],
            "grupo": t.get("grupo") or "",
            "marca": t.get("marca") or "",
            "atualizado": t["atualizado_em"].strftime("%d/%m %H:%M") if t["atualizado_em"] else "",
        }
        for t in tarefas
    ]
    return pd.DataFrame(linhas, columns=["id", "titulo", "descricao", "responsavel", "status", "grupo", "marca", "atualizado"])


def renderizar_quadro_tarefas(setor, usuarios_disponiveis=None, mostrar_titulo=True):
    """Widget pronto: tabela única editável (estilo Monday 'Main Table'),
    com as três colunas de status misturadas na mesma tabela. Ver
    `renderizar_paineis_tarefas` pra três quadros separados por status.
    """
    if mostrar_titulo:
        st.markdown("<h4 style='color: #ffcc00;'>📋 Quadro de Tarefas</h4>", unsafe_allow_html=True)

    tarefas = carregar_tarefas(setor)
    if tarefas is None:
        st.warning(f"⚠️ Não foi possível carregar as tarefas. Detalhe: `{st.session_state.get('ultimo_erro_bd')}`")
        return

    usuarios_disponiveis = usuarios_disponiveis or []
    opcoes_responsavel = [SEM_RESPONSAVEL] + usuarios_disponiveis
    df = _df_de_tarefas(tarefas)

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
            "responsavel": st.column_config.SelectboxColumn("Responsável", options=opcoes_responsavel, width="small"),
            "status": st.column_config.SelectboxColumn("Status", options=STATUS_TAREFA, width="small"),
            "grupo": st.column_config.TextColumn("Grupo", width="small"),
            "marca": st.column_config.TextColumn("Marca", width="small"),
            "atualizado": st.column_config.TextColumn("Atualizado em", disabled=True, width="small"),
        },
    )

    estado = st.session_state.get(editor_key, {})
    if _aplicar_edicoes_tabela(df, estado, setor, st.session_state.get("usuario_atual")):
        st.rerun()


def renderizar_paineis_tarefas(setor, usuarios_disponiveis=None, tipos_disponiveis=None):
    """Três quadros separados (A Fazer / Em Execução / Concluída), em
    formato de cards (estilo Monday) — cada tarefa é um cartão com badge
    colorido de Tipo, e os controles (Responsável, mover, excluir) agem na
    hora, sem precisar de tabela editável. Pensado pra tela dedicada
    "Quadro de Tarefas" do setor Processamento.

    Tarefas de produção podem levar Tipo (Triagem/Etiquetagem/Cadastro por
    padrão) e Grupo + Marca — usados pela previsão de tempo do Dashboard
    Processamento assim que a tarefa é concluída.
    """
    tarefas = carregar_tarefas(setor)
    if tarefas is None:
        st.warning(f"⚠️ Não foi possível carregar as tarefas. Detalhe: `{st.session_state.get('ultimo_erro_bd')}`")
        return

    usuarios_disponiveis = usuarios_disponiveis or []
    tipos_disponiveis = tipos_disponiveis or TIPOS_TAREFA_PADRAO
    opcoes_responsavel = [SEM_RESPONSAVEL] + usuarios_disponiveis

    with st.expander("➕ Nova tarefa"):
        with st.form(key=f"form_nova_tarefa_paineis_{setor}", clear_on_submit=True):
            col_a, col_b = st.columns(2)
            with col_a:
                titulo_novo = st.text_input("Título")
                tipo_novo = st.selectbox("Tipo", tipos_disponiveis, key=f"tipo_novo_{setor}")
                responsavel_novo = st.selectbox("Responsável (opcional)", opcoes_responsavel, key=f"resp_novo_paineis_{setor}")
            with col_b:
                descricao_nova = st.text_area("Descrição (opcional)", height=68)
                grupo_novo = st.text_input("Grupo (opcional)", help="Usado na previsão de tempo")
                marca_novo = st.text_input("Marca (opcional)", help="Usado na previsão de tempo")
            enviar = st.form_submit_button("Criar tarefa", type="primary")
            if enviar:
                if not titulo_novo.strip():
                    st.error("Dê um título pra tarefa.")
                else:
                    resp = None if responsavel_novo == SEM_RESPONSAVEL else responsavel_novo
                    ok = criar_tarefa(
                        titulo_novo.strip(), descricao_nova.strip(), setor, resp,
                        st.session_state.get("usuario_atual"), tipo=tipo_novo,
                        grupo=grupo_novo.strip() or None, marca=marca_novo.strip() or None,
                    )
                    if ok:
                        st.success("Tarefa criada.")
                        st.rerun()
                    else:
                        st.error(f"Não foi possível criar a tarefa. `{st.session_state.get('ultimo_erro_bd')}`")

    emojis = {"A Fazer": "⬜", "Em Execução": "🟡", "Concluída": "✅"}
    colunas_status = st.columns(len(STATUS_TAREFA))

    for idx_status, status in enumerate(STATUS_TAREFA):
        tarefas_da_coluna = [t for t in tarefas if t["status"] == status]
        with colunas_status[idx_status]:
            st.markdown(f"<h4 style='color: #ffcc00;'>{emojis[status]} {status} ({len(tarefas_da_coluna)})</h4>", unsafe_allow_html=True)
            if not tarefas_da_coluna:
                st.caption("—")
            for t in tarefas_da_coluna:
                _renderizar_card_tarefa(t, status, setor, opcoes_responsavel)


def _renderizar_card_tarefa(t, status, setor, opcoes_responsavel):
    """Um cartão de tarefa dentro de renderizar_paineis_tarefas. Cada
    widget age na hora (compara valor novo x valor salvo e já grava),
    sem depender de st.data_editor — é o mesmo mecanismo simples e
    confiável do quadro de tarefas original."""
    tid = t["id"]
    tipo_atual = t.get("tipo")
    cor_tipo = CORES_TIPO_TAREFA.get(tipo_atual, "#555b6e")

    with st.container(border=True):
        if tipo_atual:
            st.markdown(
                f"<span style='background:{cor_tipo}; color:white; padding:2px 10px; "
                f"border-radius:10px; font-size:11px; font-weight:600;'>{tipo_atual}</span>",
                unsafe_allow_html=True,
            )
        st.markdown(f"**{t['titulo']}**")
        if t["descricao"]:
            st.caption(t["descricao"])
        if t.get("grupo") or t.get("marca"):
            st.caption(f"🏷️ {t.get('grupo') or '—'} / {t.get('marca') or '—'}")

        resp_atual = t["responsavel"] or SEM_RESPONSAVEL
        idx_resp = opcoes_responsavel.index(resp_atual) if resp_atual in opcoes_responsavel else 0
        novo_resp = st.selectbox(
            "Responsável", opcoes_responsavel, index=idx_resp,
            key=f"resp_{setor}_{tid}", label_visibility="collapsed",
        )
        if novo_resp != resp_atual:
            campos = {"responsavel": novo_resp}
            if novo_resp and status == "A Fazer":
                campos["status"] = "Em Execução"
                campos["iniciar"] = True
            elif not novo_resp and status == "Em Execução":
                campos["status"] = "A Fazer"
                campos["iniciado_em"] = None
            if atualizar_tarefa(tid, **campos):
                st.rerun()
            else:
                st.error(f"Não foi possível salvar. `{st.session_state.get('ultimo_erro_bd')}`")

        outros_status = [s for s in STATUS_TAREFA if s != status]
        col_mover, col_ir, col_del = st.columns([3, 1, 1])
        with col_mover:
            alvo = st.selectbox(
                "Mover para", outros_status, key=f"mover_{setor}_{tid}", label_visibility="collapsed",
            )
        with col_ir:
            if st.button("➡️", key=f"btn_mover_{setor}_{tid}", use_container_width=True):
                campos = {"status": alvo}
                if alvo == "Em Execução":
                    campos["iniciar"] = True
                elif alvo == "Concluída":
                    campos["concluir"] = True
                elif status == "Em Execução" and alvo == "A Fazer":
                    campos["iniciado_em"] = None
                if atualizar_tarefa(tid, **campos):
                    st.rerun()
                else:
                    st.error(f"Não foi possível mover a tarefa. `{st.session_state.get('ultimo_erro_bd')}`")
        with col_del:
            if st.button("🗑️", key=f"del_{setor}_{tid}", use_container_width=True):
                if remover_tarefa(tid):
                    st.rerun()
