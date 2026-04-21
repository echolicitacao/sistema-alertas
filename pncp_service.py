"""
Serviço de busca de licitações e contratos no PNCP
API pública, sem necessidade de chave ou cadastro
"""

import requests
from datetime import datetime, timedelta

PNCP_BASE = "https://pncp.gov.br/api/pncp/v1"
TIMEOUT = 15

def buscar_licitacoes(palavras: list, estados: list, valor_min: float, ja_enviados: set) -> list:
    """
    Busca licitações abertas no PNCP filtrando por palavras-chave,
    estados e valor mínimo. Exclui IDs já enviados (deduplicação).
    Retorna lista de dicts.
    """
    hoje = datetime.now()
    data_ini = (hoje - timedelta(days=7)).strftime("%Y%m%d")
    data_fim = hoje.strftime("%Y%m%d")

    resultados = []
    pagina = 1

    while True:
        try:
            resp = requests.get(
                f"{PNCP_BASE}/contratacoes/publicacoes",
                params={
                    "dataInicial": data_ini,
                    "dataFinal":   data_fim,
                    "pagina":      pagina,
                    "tamanhoPagina": 50,
                },
                timeout=TIMEOUT
            )
            if resp.status_code != 200:
                break

            data = resp.json()
            itens = data.get("data", [])
            if not itens:
                break

            for item in itens:
                # Filtro de valor mínimo
                valor = float(item.get("valorTotalEstimado") or 0)
                if valor < valor_min:
                    continue

                # Filtro de estado (UF do órgão)
                uf_item = (item.get("orgaoEntidade", {}) or {}).get("ufSigla", "")
                if estados and uf_item not in estados:
                    continue

                # Filtro de palavras-chave no objeto
                objeto = (item.get("objetoCompra") or "").lower()
                if palavras:
                    if not any(p.lower() in objeto for p in palavras):
                        continue

                # Deduplicação
                edital_id = str(item.get("numeroControlePNCP") or item.get("id") or "")
                if edital_id in ja_enviados:
                    continue

                orgao = item.get("orgaoEntidade", {}) or {}
                resultados.append({
                    "id":         edital_id,
                    "orgao":      orgao.get("razaoSocial", "Orgão não informado"),
                    "uf":         uf_item,
                    "objeto":     item.get("objetoCompra", "Objeto não informado"),
                    "modalidade": item.get("modalidadeNome", ""),
                    "numero":     item.get("numeroCompra", ""),
                    "valor":      f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
                    "abertura":   _formatar_data(item.get("dataAberturaProposta") or item.get("dataPublicacaoPncp")),
                    "link":       f"https://pncp.gov.br/app/editais/{orgao.get('cnpj','')}/2026/{item.get('sequencialCompra','')}",
                })

            # Verificar se há mais páginas
            total_paginas = data.get("totalPaginas", 1)
            if pagina >= total_paginas:
                break
            pagina += 1

        except requests.exceptions.RequestException as e:
            print(f"  [PNCP] Erro na busca de licitações (pág {pagina}): {e}")
            break

    return resultados


def buscar_contratos_assinados(palavras: list, estados: list, valor_min: float) -> list:
    """
    Busca contratos assinados na última semana no PNCP.
    Filtra por palavras-chave, estado e valor mínimo.
    """
    hoje = datetime.now()
    data_ini = (hoje - timedelta(days=7)).strftime("%Y%m%d")
    data_fim = hoje.strftime("%Y%m%d")

    resultados = []
    pagina = 1

    while True:
        try:
            resp = requests.get(
                f"{PNCP_BASE}/contratos",
                params={
                    "dataInicial": data_ini,
                    "dataFinal":   data_fim,
                    "pagina":      pagina,
                    "tamanhoPagina": 50,
                },
                timeout=TIMEOUT
            )
            if resp.status_code != 200:
                break

            data = resp.json()
            itens = data.get("data", [])
            if not itens:
                break

            for item in itens:
                valor = float(item.get("valorInicial") or 0)
                if valor < valor_min:
                    continue

                uf_item = (item.get("orgaoEntidade", {}) or {}).get("ufSigla", "")
                if estados and uf_item not in estados:
                    continue

                objeto = (item.get("objetoContrato") or "").lower()
                if palavras:
                    if not any(p.lower() in objeto for p in palavras):
                        continue

                fornecedor = item.get("nomeRazaoSocialFornecedor", "Não informado")
                cnpj = item.get("numeroCnpjFornecedor", "Não informado")
                orgao = item.get("orgaoEntidade", {}) or {}

                resultados.append({
                    "empresa":    fornecedor,
                    "cnpj":       cnpj,
                    "orgao":      orgao.get("razaoSocial", "Orgão não informado"),
                    "uf":         uf_item,
                    "objeto":     item.get("objetoContrato", "Objeto não informado"),
                    "valor":      f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
                    "data":       _formatar_data(item.get("dataAssinatura")),
                })

            total_paginas = data.get("totalPaginas", 1)
            if pagina >= total_paginas:
                break
            pagina += 1

        except requests.exceptions.RequestException as e:
            print(f"  [PNCP] Erro na busca de contratos (pág {pagina}): {e}")
            break

    return resultados


def _formatar_data(data_str: str) -> str:
    if not data_str:
        return "A confirmar"
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(data_str[:len(fmt.replace("%Y","2026").replace("%m","01").replace("%d","01").replace("%H","00").replace("%M","00").replace("%S","00"))], fmt).strftime("%d/%m/%Y")
        except:
            pass
    return data_str[:10] if len(data_str) >= 10 else data_str
