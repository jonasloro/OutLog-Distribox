# OutLog — Distribox

Sistema de gestão de estoque por casulo do CD (Supabase), com o módulo de Devoluções integrado (Neon).

## Estrutura

```
app.py                     # app principal: config de página, sessão, motor de
                            # estrutura/capacidade do CD, sidebar e todas as
                            # telas de Estocagem/SGO/Expedição
core/
    database.py             # conexão com o Supabase (Postgres)
    usuarios.py              # hash de senha + CRUD de usuários no Supabase
    relatorios_pdf.py        # extração de dados de PDF (resumo de estoque, romaneio)
modules/devolucoes/         # módulo de Devoluções (banco Neon próprio)
    parser.py, database.py, services.py, tratamento.py, anapolis.py, models.py
    pages/                   # uma tela Streamlit por arquivo
```

## Sobre a divisão do app.py

Você pediu para dividir `app.py` (antes 4035 linhas) em arquivos menores. Fiz isso em duas partes, por um motivo importante:

**O que já foi movido para `core/`:** conexão com o Supabase, autenticação/CRUD de usuários e extração de PDF. São funções auto-contidas, sem estado compartilhado — mover elas não muda nenhum comportamento.

**O que ainda está em `app.py` (por enquanto, de propósito):** o motor de estrutura/capacidade do CD (`ESTRUTURA_CD`, `RUA_GENERO`, `CAPACIDADE_*`, `CAPACIDADE_FIXA_POR_RUA`) e as ~10 telas de Estocagem/SGO/Expedição que dependem dele. O motivo: quando o Gerenciador salva uma configuração nova, `_aplicar_configuracoes_do_banco` faz `ESTRUTURA_CD = estrutura_nova` — ou seja, **substitui** a variável global, não atualiza o conteúdo dela. Em Python, se essas variáveis fossem movidas para um módulo separado e importadas com `from core.config import ESTRUTURA_CD` em cada tela, cada tela ficaria presa para sempre com a versão antiga do dicionário — a substituição só valeria dentro do módulo onde ela acontece. Isso criaria um bug silencioso e sério (estrutura desatualizada aparecendo pro usuário depois de salvar uma configuração nova), praticamente impossível de perceber sem testar contra o Supabase real.

Dividir esse núcleo com segurança dá pra fazer, mas exige primeiro trocar esse padrão de "substituir a variável" por algo que sobrevive a ficar em outro módulo (por exemplo, mutar o dicionário no lugar com `.clear()` + `.update()`, ou guardar tudo dentro de um objeto/classe e importar o objeto, não os campos soltos). Prefiro fazer essa troca como um passo isolado e testável, em vez de misturar com a divisão de arquivos — me avise se quiser que eu faça isso a seguir.

## Módulo de Devoluções

Adicionado como novo item do setor **🚚 Expedição** na sidebar, com 8 telas (Dashboard, Recebimento, Conferência, Pendências, Aguardando decisão, Defeitos Anápolis, Histórico, Indicadores). Usa um banco **Neon PostgreSQL separado do Supabase principal** — configure o secret `DATABASE_URL` (Settings → Secrets do Streamlit) apontando para esse Neon. Sem esse secret, as telas de Devoluções mostram um aviso e não afetam o resto do app.

Fluxo oficial: Romaneio da Loja + Romaneio Entrada CD + Romaneio Entrada Anápolis → Conferência → Registro → Tratamento → Histórico → Indicadores. Regra da conferência: Loja = Entrada CD + Entrada Anápolis. Mais detalhes em `modules/devolucoes/`.
