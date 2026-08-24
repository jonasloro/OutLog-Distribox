"""Extração de dados de PDFs (resumo de estoque por grupo e romaneio de
separação da Expedição em modo teste).

Extraído de app.py sem alterar lógica — só movido de lugar.
"""
import re

import pypdf


def extrair_totais_por_grupo_pdf(arquivo_pdf):
    """
    Lê um PDF no formato 'Resumo de Estoque do Grupo' (agrupado por GRUPO,
    detalhado por MARCA) e retorna uma lista de (nome_grupo, quantidade) com
    o SUBTOTAL de peças de cada grupo — ignora os valores de custo/venda e
    o detalhe por marca, que não são necessários pro planejamento de casulos.
    """
    leitor = pypdf.PdfReader(arquivo_pdf)
    texto_completo = ""
    for pagina in leitor.pages:
        texto_completo += pagina.extract_text(extraction_mode="layout") + "\n"

    padrao_dinheiro = re.compile(r'^\d{1,3}(\.\d{3})*,\d{2}$')
    padrao_metadado = re.compile(r'(RESUMO DE ESTOQUE|Agrupado por|Empresas:|DESCRIÇÃO|Pag\.:|Detalhado por|Emitir P\.|^\d{2}\s*-\s*CD)', re.I)

    def achar_qtd(lista_tokens):
        for t in lista_tokens:
            if padrao_dinheiro.match(t):
                continue
            if re.match(r'^\d+(\.\d{3})*$', t):
                return int(t.replace(".", ""))
        return None

    grupos = []
    grupo_atual = None

    for linha_bruta in texto_completo.split("\n"):
        linha = linha_bruta.strip()
        if not linha:
            continue
        if padrao_metadado.search(linha):
            continue

        tokens = linha.split()
        if not tokens:
            continue
        primeiro_upper = tokens[0].upper()
        n_valores_dinheiro = sum(1 for t in tokens if padrao_dinheiro.match(t))

        if primeiro_upper == "VAZIO":
            qtd = achar_qtd(tokens[1:])
            if qtd is not None:
                grupos.append(("Vazio (sem grupo)", qtd))
            continue

        if primeiro_upper == "SUBTOTAL":
            qtd = achar_qtd(tokens[1:])
            if qtd is not None and grupo_atual:
                grupos.append((grupo_atual, qtd))
            continue

        if primeiro_upper == "TOTAL":
            continue

        if n_valores_dinheiro >= 2:
            continue  # linha de marca (dado), não é cabeçalho de grupo

        grupo_atual = linha

    return grupos


SUFIXOS_VARIANTE_MARCA = {"L", "N", "PROMO", "KIDS", "BLACK", "NAC", "FITNESS", "COLEÇÃO"}


def extrair_marcas_por_grupo_pdf(arquivo_pdf):
    """
    Lê o mesmo PDF 'Resumo de Estoque do Grupo' (agrupado por GRUPO,
    detalhado por MARCA) e retorna {grupo: [marcas]} — o detalhe por marca
    que extrair_totais_por_grupo_pdf ignora de propósito. Usado só pra
    alimentar o reconhecimento automático de Marca (core/marcas.py), não
    pro planejamento de casulos.

    Sufixos de variante (cor/coleção/promo) são removidos do fim do nome
    pra consolidar "MAX GLAMM", "MAX GLAMM PROMO" e "MAX GLAMM FITNESS"
    numa marca só: "MAX GLAMM".
    """
    leitor = pypdf.PdfReader(arquivo_pdf)
    texto_completo = ""
    for pagina in leitor.pages:
        texto_completo += pagina.extract_text(extraction_mode="layout") + "\n"

    padrao_dinheiro = re.compile(r'^\d{1,3}(\.\d{3})*,\d{2}$')
    padrao_metadado = re.compile(r'(RESUMO DE ESTOQUE|Agrupado por|Empresas:|DESCRIÇÃO|Pag\.:|Detalhado por|Emitir P\.|^\d{2}\s*-\s*CD)', re.I)
    padrao_qtd = re.compile(r'^\d+(\.\d{3})*$')

    grupo_atual = None
    marcas_por_grupo = {}

    for linha_bruta in texto_completo.split("\n"):
        linha = linha_bruta.strip()
        if not linha:
            continue
        if padrao_metadado.search(linha):
            continue

        tokens = linha.split()
        if not tokens:
            continue
        primeiro_upper = tokens[0].upper()
        n_valores_dinheiro = sum(1 for t in tokens if padrao_dinheiro.match(t))

        if primeiro_upper in ("SUBTOTAL", "TOTAL", "VAZIO"):
            continue

        if n_valores_dinheiro >= 2:
            # linha de marca: [nome..., qtd, dinheiro, dinheiro]
            tokens_sem_dinheiro = [t for t in tokens if not padrao_dinheiro.match(t)]
            if len(tokens_sem_dinheiro) < 2:
                continue
            *nome_tokens, qtd_tok = tokens_sem_dinheiro
            if not padrao_qtd.match(qtd_tok):
                continue
            while nome_tokens and nome_tokens[-1].upper() in SUFIXOS_VARIANTE_MARCA:
                nome_tokens.pop()
            if not nome_tokens or not grupo_atual:
                continue
            marca = " ".join(nome_tokens).upper()
            if marca == "OUTROS":
                continue
            marcas_por_grupo.setdefault(grupo_atual, set()).add(marca)
            continue

        grupo_atual = linha

    return {grupo: sorted(marcas) for grupo, marcas in marcas_por_grupo.items()}


def extrair_baixas_romaneio_pdf(arquivo_pdf):
    """
    Parser PROVISÓRIO para o romaneio de separação, usado só na tela de
    Expedição (modo teste). Ainda não temos um romaneio real de exemplo, então
    isso procura, em cada linha do PDF, um endereço de casulo no mesmo padrão
    usado no Localizador Global ('NNN-L-NNN', ex: 003-B-009) seguido de uma
    quantidade (o primeiro número inteiro depois do endereço na mesma linha).
    Quando tivermos um romaneio real, este parser deve ser ajustado pro layout exato.
    """
    leitor = pypdf.PdfReader(arquivo_pdf)
    texto_completo = ""
    for pagina in leitor.pages:
        texto_completo += (pagina.extract_text(extraction_mode="layout") or "") + "\n"

    padrao_endereco = re.compile(r'\b(\d{2,3})\s*-\s*([A-Za-z])\s*-\s*(\d{2,3})\b')

    linhas_extraidas = []
    for linha_bruta in texto_completo.split("\n"):
        linha = linha_bruta.strip()
        if not linha:
            continue
        m_end = padrao_endereco.search(linha)
        if not m_end:
            continue
        resto_linha = linha[m_end.end():]
        m_qtd = re.search(r'\d+', resto_linha)
        if not m_qtd:
            continue
        num_rua_str, nivel_str, col_str = m_end.groups()
        linhas_extraidas.append({
            "endereco": f"{int(num_rua_str):03d}-{nivel_str.upper()}-{int(col_str):03d}",
            "rua_num": int(num_rua_str),
            "nivel": nivel_str.upper(),
            "coluna": int(col_str),
            "quantidade": int(m_qtd.group())
        })

    return linhas_extraidas
