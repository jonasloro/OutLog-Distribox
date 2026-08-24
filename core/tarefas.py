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

Toda tarefa exige uma Quantidade Prevista (peças) já na criação. Ao
concluir, pede a Quantidade Real (quanto foi executado de verdade) — os
dois números ficam salvos lado a lado pra comparar previsto x realizado.
Tarefas de Processamento podem nascer de um lote pendente do relatório do
SGO (sugestão pré-preenchida com Grupo/Descrição/Quantidade do lote,
rastreada por `lote_sgo` pra não sugerir duas vezes o mesmo lote). Cards
concluídos há mais de 1 dia somem da visualização em cards (não são
apagados do banco, só saem do quadro — "arquivamento" automático).
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
    "ALTER TABLE tarefas_app ADD COLUMN IF NOT EXISTS quantidade_prevista INTEGER",
    "ALTER TABLE tarefas_app ADD COLUMN IF NOT EXISTS quantidade_real INTEGER",
    "ALTER TABLE tarefas_app ADD COLUMN IF NOT EXISTS concluido_em TIMESTAMP",
    "ALTER TABLE tarefas_app ADD COLUMN IF NOT EXISTS lote_sgo TEXT",
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
    """Carrega as tarefas do setor (ou todas, se `setor` for None).
    Concluídas há mais de 1 dia são "arquivadas": ficam no banco (histórico
    de tempo/quantidade continua valendo), mas somem daqui pra não lotar o
    quadro pra sempre."""
    conn = obter_conexao_bd()
    if conn is None:
        return None
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            _garantir_tabela(cur)
            conn.commit()
            filtro_arquivamento = (
                "(status <> 'Concluída' OR concluido_em IS NULL OR concluido_em >= now() - interval '1 day')"
            )
            if setor:
                cur.execute(
                    f"SELECT * FROM tarefas_app WHERE setor = %s AND {filtro_arquivamento} ORDER BY "
                    "CASE status WHEN 'Em Execução' THEN 0 WHEN 'A Fazer' THEN 1 ELSE 2 END, "
                    "atualizado_em DESC",
                    (setor,),
                )
            else:
                cur.execute(
                    f"SELECT * FROM tarefas_app WHERE {filtro_arquivamento} ORDER BY "
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


def criar_tarefa(titulo, descricao, setor, responsavel, criado_por, status=None, grupo=None, marca=None, tipo=None, quantidade_prevista=None, lote_sgo=None):
    """Cria uma tarefa nova. Se `status` não for informado, usa 'Em Execução'
    quando já vem com responsável (estilo Monday: atribuir = já começou) ou
    'A Fazer' quando não vem. Se já nasce 'Em Execução', já marca o início
    (iniciado_em) — importante pra previsão de tempo funcionar mesmo em
    tarefas criadas direto na coluna 'Em Execução'.

    `quantidade_prevista` é exigido pela UI (não pelo banco, pra não quebrar
    linhas antigas) — todo formulário de criação, manual ou vindo de
    sugestão do SGO, obriga esse número antes de deixar criar."""
    status_final = status or ("Em Execução" if responsavel else "A Fazer")
    grupo = grupo or None
    marca = marca or None
    tipo = tipo or None
    lote_sgo = lote_sgo or None
    conn = obter_conexao_bd()
    if conn is None:
        return False
    try:
        with conn.cursor() as cur:
            _garantir_tabela(cur)
            if status_final == "Em Execução":
                cur.execute(
                    "INSERT INTO tarefas_app (titulo, descricao, setor, responsavel, criado_por, status, grupo, marca, tipo, quantidade_prevista, lote_sgo, iniciado_em) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())",
                    (titulo, descricao, setor, responsavel, criado_por, status_final, grupo, marca, tipo, quantidade_prevista, lote_sgo),
                )
            else:
                cur.execute(
                    "INSERT INTO tarefas_app (titulo, descricao, setor, responsavel, criado_por, status, grupo, marca, tipo, quantidade_prevista, lote_sgo) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (titulo, descricao, setor, responsavel, criado_por, status_final, grupo, marca, tipo, quantidade_prevista, lote_sgo),
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
    grupo/marca/tipo/quantidade_prevista/quantidade_real/concluido_em/
    lote_sgo. `responsavel=""` grava NULL (limpa o responsável).

    Dois campos especiais, não gravados diretamente:
    - iniciar=True: marca iniciado_em = now() (só se ainda não tinha um
      início em aberto — não reinicia o cronômetro de uma tarefa já
      rodando).
    - concluir=True: fecha o ciclo — grava no histórico de tempo de
      produção quantos minutos essa tarefa levou (agora - iniciado_em),
      usando o Grupo/Marca que a tarefa tem no banco, marca concluido_em
      = now() (usado pro arquivamento automático 1 dia depois) e limpa
      iniciado_em. Só grava histórico de TEMPO se a tarefa tinha
      iniciado_em E Grupo E Marca preenchidos; senão só limpa o
      iniciado_em silenciosamente (tarefa sem esses dados não entra na
      previsão de tempo, mas não trava a conclusão). Passe também
      quantidade_real=N junto quando concluir=True, pra registrar quanto
      foi executado de verdade."""
    iniciar = bool(campos.pop("iniciar", False))
    concluir = bool(campos.pop("concluir", False))

    campos_validos = {
        "titulo", "descricao", "status", "responsavel", "grupo", "marca", "tipo",
        "quantidade_prevista", "quantidade_real", "concluido_em", "lote_sgo",
    }
    campos = {k: v for k, v in campos.items() if k in campos_validos}
    if "responsavel" in campos and campos["responsavel"] == "":
        campos["responsavel"] = None

    conn = obter_conexao_bd()
    if conn is None:
        return False
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            _garantir_tabela(cur)

            extra_set_sql = []
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
                extra_set_sql.append("concluido_em = now()")

            set_partes = [f"{col} = %s" for col in campos]
            valores = list(campos.values())
            if iniciar:
                set_partes.append("iniciado_em = COALESCE(iniciado_em, now())")
            set_partes.extend(extra_set_sql)
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
        quantidade_prevista = nova.get("quantidade_prevista")
        if not quantidade_prevista or quantidade_prevista <= 0:
            st.error(f"Tarefa '{titulo}' não foi criada: Quantidade Prevista é obrigatória.")
            continue
        responsavel = nova.get("responsavel") or None
        descricao = (nova.get("descricao") or "").strip()
        grupo = (nova.get("grupo") or "").strip() or None
        marca = (nova.get("marca") or "").strip() or None
        status_nova = status_fixo_para_novas or nova.get("status")
        if criar_tarefa(titulo, descricao, setor, responsavel, criado_por, status=status_nova, grupo=grupo, marca=marca, quantidade_prevista=int(quantidade_prevista)):
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
            "quantidade_prevista": t.get("quantidade_prevista"),
            "quantidade_real": t.get("quantidade_real"),
            "atualizado": t["atualizado_em"].strftime("%d/%m %H:%M") if t["atualizado_em"] else "",
        }
        for t in tarefas
    ]
    return pd.DataFrame(linhas, columns=["id", "titulo", "descricao", "responsavel", "status", "grupo", "marca", "quantidade_prevista", "quantidade_real", "atualizado"])


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
        column_order=["titulo", "descricao", "responsavel", "status", "quantidade_prevista", "quantidade_real", "atualizado"],
        column_config={
            "id": None,
            "titulo": st.column_config.TextColumn("Tarefa", required=True, width="medium"),
            "descricao": st.column_config.TextColumn("Descrição", width="large"),
            "responsavel": st.column_config.SelectboxColumn("Responsável", options=opcoes_responsavel, width="small"),
            "status": st.column_config.SelectboxColumn("Status", options=STATUS_TAREFA, width="small"),
            "grupo": st.column_config.TextColumn("Grupo", width="small"),
            "marca": st.column_config.TextColumn("Marca", width="small"),
            "quantidade_prevista": st.column_config.NumberColumn("Qtd Prevista", required=True, min_value=1, step=1, width="small"),
            "quantidade_real": st.column_config.NumberColumn("Qtd Real", min_value=0, step=1, width="small", help="Preencher ao concluir"),
            "atualizado": st.column_config.TextColumn("Atualizado em", disabled=True, width="small"),
        },
    )

    estado = st.session_state.get(editor_key, {})
    if _aplicar_edicoes_tabela(df, estado, setor, st.session_state.get("usuario_atual")):
        st.rerun()


def renderizar_paineis_tarefas(setor, usuarios_disponiveis=None, tipos_disponiveis=None, sugestoes_sgo=None):
    """Três quadros separados (A Fazer / Em Execução / Concluída), em
    formato de cards (estilo Monday) — cada tarefa é um cartão com badge
    colorido de Tipo, e os controles (Responsável, mover, excluir) agem na
    hora, sem precisar de tabela editável. Pensado pra tela dedicada
    "Quadro de Tarefas" do setor Processamento.

    Tarefas de produção podem levar Tipo (Triagem/Etiquetagem/Cadastro por
    padrão) e Grupo + Marca — usados pela previsão de tempo do Dashboard
    Processamento assim que a tarefa é concluída. Toda tarefa exige uma
    Quantidade Prevista já na criação; ao mover pra Concluída, pede a
    Quantidade Real antes de confirmar. Cards concluídos somem do quadro
    depois de 1 dia (carregar_tarefas já filtra isso).

    `sugestoes_sgo`, se passado, é uma lista de dicts {lote, grupo,
    descricao, quantidade, marca} — lotes do relatório do SGO já na fase
    Processamento que ainda não viraram tarefa (dedup por lote_sgo). Cada
    um vira um botão de criação rápida, pré-preenchido."""
    tarefas = carregar_tarefas(setor)
    if tarefas is None:
        st.warning(f"⚠️ Não foi possível carregar as tarefas. Detalhe: `{st.session_state.get('ultimo_erro_bd')}`")
        return

    usuarios_disponiveis = usuarios_disponiveis or []
    tipos_disponiveis = tipos_disponiveis or TIPOS_TAREFA_PADRAO
    opcoes_responsavel = [SEM_RESPONSAVEL] + usuarios_disponiveis

    if sugestoes_sgo:
        lotes_ja_importados = {t.get("lote_sgo") for t in tarefas if t.get("lote_sgo")}
        pendentes = [s for s in sugestoes_sgo if s.get("lote") not in lotes_ja_importados]
        if pendentes:
            with st.expander(f"📥 Sugestões do SGO — Processamento ({len(pendentes)} pendente(s))", expanded=False):
                st.caption("Lotes do relatório do SGO já na fase Processamento. Escolha o Tipo e confirme a Quantidade Prevista (vem preenchida com a quantidade do lote) pra criar a tarefa.")
                for s in pendentes:
                    lote, grupo, descricao, quantidade, marca = s.get("lote"), s.get("grupo"), s.get("descricao"), s.get("quantidade"), s.get("marca")
                    with st.container(border=True):
                        st.markdown(f"**{descricao or grupo}**")
                        st.caption(f"Lote {lote} · Grupo: {grupo or '—'} · Marca: {marca or 'não reconhecida'}")
                        col_tipo, col_qtd, col_btn = st.columns([2, 1, 1])
                        with col_tipo:
                            tipo_sugestao = st.selectbox("Tipo", tipos_disponiveis, key=f"sugestao_tipo_{setor}_{lote}", label_visibility="collapsed")
                        with col_qtd:
                            qtd_sugestao = st.number_input(
                                "Quantidade Prevista", min_value=1, step=1,
                                value=int(quantidade) if quantidade else 1,
                                key=f"sugestao_qtd_{setor}_{lote}", label_visibility="collapsed",
                            )
                        with col_btn:
                            if st.button("➕ Criar", key=f"sugestao_criar_{setor}_{lote}", use_container_width=True):
                                ok = criar_tarefa(
                                    descricao or grupo or f"Lote {lote}", "", setor, None,
                                    st.session_state.get("usuario_atual"), tipo=tipo_sugestao,
                                    grupo=grupo, marca=marca, quantidade_prevista=int(qtd_sugestao),
                                    lote_sgo=lote,
                                )
                                if ok:
                                    st.success("Tarefa criada a partir do SGO.")
                                    st.rerun()
                                else:
                                    st.error(f"Não foi possível criar. `{st.session_state.get('ultimo_erro_bd')}`")

    with st.expander("➕ Nova tarefa manual"):
        with st.form(key=f"form_nova_tarefa_paineis_{setor}", clear_on_submit=True):
            col_a, col_b = st.columns(2)
            with col_a:
                titulo_novo = st.text_input("Título")
                tipo_novo = st.selectbox("Tipo", tipos_disponiveis, key=f"tipo_novo_{setor}")
                responsavel_novo = st.selectbox("Responsável (opcional)", opcoes_responsavel, key=f"resp_novo_paineis_{setor}")
                quantidade_prevista_nova = st.number_input("Quantidade Prevista (obrigatório)", min_value=1, step=1, value=1)
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
                        quantidade_prevista=int(quantidade_prevista_nova),
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
            if status == "Concluída":
                st.caption("Some daqui 1 dia depois de concluída (fica no histórico).")
            if not tarefas_da_coluna:
                st.caption("—")
            for t in tarefas_da_coluna:
                _renderizar_card_tarefa(t, status, setor, opcoes_responsavel)


def _renderizar_card_tarefa(t, status, setor, opcoes_responsavel):
    """Um cartão de tarefa dentro de renderizar_paineis_tarefas. Cada
    widget age na hora (compara valor novo x valor salvo e já grava),
    sem depender de st.data_editor — é o mesmo mecanismo simples e
    confiável do quadro de tarefas original.

    Mover pra "Concluída" é em duas etapas: escolher o alvo já revela um
    campo de Quantidade Real, e só grava quando confirmar — não dá pra
    concluir sem informar quanto foi executado de verdade."""
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

        qtd_prevista = t.get("quantidade_prevista")
        qtd_real = t.get("quantidade_real")
        if qtd_real is not None:
            st.caption(f"🎯 Previsto: {qtd_prevista} · ✅ Real: {qtd_real}")
        elif qtd_prevista is not None:
            st.caption(f"🎯 Previsto: {qtd_prevista} pçs")

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
        alvo = st.selectbox(
            "Mover para", outros_status, key=f"mover_{setor}_{tid}", label_visibility="collapsed",
        )

        if alvo == "Concluída":
            qtd_real_input = st.number_input(
                "Quantidade Real (obrigatório pra concluir)", min_value=0, step=1,
                value=int(qtd_prevista) if qtd_prevista else 0,
                key=f"qtdreal_{setor}_{tid}",
            )
            if st.button("✅ Confirmar conclusão", key=f"btn_concluir_{setor}_{tid}", use_container_width=True):
                campos = {"status": "Concluída", "concluir": True, "quantidade_real": int(qtd_real_input)}
                if atualizar_tarefa(tid, **campos):
                    st.rerun()
                else:
                    st.error(f"Não foi possível concluir. `{st.session_state.get('ultimo_erro_bd')}`")
        else:
            col_ir, col_del = st.columns([3, 1])
            with col_ir:
                if st.button("➡️ Mover", key=f"btn_mover_{setor}_{tid}", use_container_width=True):
                    campos = {"status": alvo}
                    if alvo == "Em Execução":
                        campos["iniciar"] = True
                    if status == "Em Execução" and alvo == "A Fazer":
                        campos["iniciado_em"] = None
                    if status == "Concluída" and alvo != "Concluída":
                        campos["concluido_em"] = None
                    if atualizar_tarefa(tid, **campos):
                        st.rerun()
                    else:
                        st.error(f"Não foi possível mover a tarefa. `{st.session_state.get('ultimo_erro_bd')}`")
            with col_del:
                if st.button("🗑️", key=f"del_{setor}_{tid}", use_container_width=True):
                    if remover_tarefa(tid):
                        st.rerun()
