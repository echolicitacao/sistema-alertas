"""
Serviço de envio de e-mail via Resend.com
Gratuito até 3.000 e-mails/mês
"""

import os
import requests
from jinja2 import Environment, FileSystemLoader, select_autoescape
from datetime import datetime

RESEND_API_KEY  = os.environ.get("RESEND_API_KEY", "")
EMAIL_REMETENTE = os.environ.get("EMAIL_REMETENTE", "alertas@seudominio.com")
RESEND_API_URL  = "https://api.resend.com/emails"

def enviar_relatorio(destinatario: str, nome: str, licitacoes: list, contratos: list, semana: str):
    """
    Monta o HTML do relatório e envia por e-mail via Resend.
    """
    if not RESEND_API_KEY:
        print(f"  [EMAIL] RESEND_API_KEY não configurada. Simulando envio para {destinatario}")
        print(f"  [EMAIL] Licitações: {len(licitacoes)} | Contratos: {len(contratos)}")
        return

    # Montar HTML do relatório
    html = _montar_html(nome, licitacoes, contratos, semana)

    assunto = f"Suas oportunidades da semana — {semana}"

    payload = {
        "from":    EMAIL_REMETENTE,
        "to":      [destinatario],
        "subject": assunto,
        "html":    html,
    }

    resp = requests.post(
        RESEND_API_URL,
        headers={
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type":  "application/json",
        },
        json=payload,
        timeout=15,
    )

    if resp.status_code not in (200, 201):
        raise Exception(f"Resend retornou {resp.status_code}: {resp.text}")

    print(f"  [EMAIL] Enviado para {destinatario} — ID: {resp.json().get('id','?')}")


def _montar_html(nome: str, licitacoes: list, contratos: list, semana: str) -> str:
    return f"""
<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Relatório Semanal</title>
<style>
  body {{ font-family: Arial, sans-serif; background: #F7F9FC; margin: 0; padding: 0; color: #2D3748; }}
  .container {{ max-width: 700px; margin: 32px auto; background: #fff; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }}
  .header {{ background: #112244; padding: 28px 32px; }}
  .header h1 {{ color: #fff; font-size: 18px; margin: 0 0 4px; }}
  .header p {{ color: #B8CCF0; font-size: 12px; margin: 0; }}
  .meta {{ background: #EBF0F8; padding: 16px 32px; display: flex; gap: 32px; }}
  .meta span {{ font-size: 12px; color: #4A5568; }}
  .meta strong {{ color: #112244; }}
  .section-header {{ background: #1B3A6B; color: #fff; padding: 12px 32px; font-size: 13px; font-weight: bold; margin-top: 0; }}
  .section-header.green {{ background: #1A5C36; }}
  .content {{ padding: 0 32px 16px; }}
  .card {{ border: 1px solid #E2E8F0; border-left: 4px solid #2251A3; border-radius: 4px; padding: 14px 16px; margin: 12px 0; }}
  .card.green {{ border-left-color: #1A5C36; }}
  .card-orgao {{ font-weight: bold; font-size: 13px; color: #112244; margin-bottom: 4px; }}
  .card-objeto {{ font-size: 12px; color: #4A5568; margin-bottom: 8px; line-height: 1.5; }}
  .card-meta {{ display: flex; flex-wrap: wrap; gap: 12px; font-size: 11px; color: #718096; }}
  .card-meta strong {{ color: #1A5C36; font-size: 13px; }}
  .card-empresa {{ font-weight: bold; font-size: 13px; color: #112244; margin-bottom: 4px; }}
  .card-cnpj {{ font-size: 11px; color: #718096; margin-bottom: 4px; }}
  .empty {{ padding: 20px 32px; color: #A0AEC0; font-size: 12px; font-style: italic; }}
  .footer {{ background: #F7F9FC; padding: 16px 32px; font-size: 10px; color: #A0AEC0; border-top: 1px solid #E2E8F0; text-align: center; }}
  .badge {{ display: inline-block; background: #EBF0F8; color: #1B3A6B; border-radius: 10px; padding: 2px 8px; font-size: 10px; font-weight: bold; }}
</style>
</head>
<body>
<div class="container">

  <!-- CABEÇALHO -->
  <div class="header">
    <h1>Relatório Semanal de Licitações</h1>
    <p>Semana de {semana} &nbsp;·&nbsp; Preparado para <strong style="color:#fff">{nome}</strong></p>
  </div>

  <!-- META -->
  <div class="meta">
    <span><strong>{len(licitacoes)}</strong> oportunidades abertas</span>
    <span><strong>{len(contratos)}</strong> contratos assinados esta semana</span>
    <span>Filtro: <strong>acima de R$ 1.000.000</strong></span>
  </div>

  <!-- SECAO 1: OPORTUNIDADES -->
  <div class="section-header">SECAO 1 — OPORTUNIDADES ABERTAS ESTA SEMANA</div>
  <div class="content">
    {"".join([f'''
    <div class="card">
      <div class="card-orgao">{l["orgao"]} &nbsp;<span class="badge">{l["uf"]}</span></div>
      <div class="card-objeto">{l["objeto"]}</div>
      <div class="card-meta">
        <span>{l["modalidade"]}</span>
        <span>Abertura: <strong>{l["abertura"]}</strong></span>
        <span>Valor est.: <strong style="color:#1A5C36">{l["valor"]}</strong></span>
        <span><a href="{l["link"]}" style="color:#2251A3">Ver edital no PNCP</a></span>
      </div>
    </div>''' for l in licitacoes]) if licitacoes else '<div class="empty">Nenhuma oportunidade encontrada nesta semana com os filtros configurados.</div>'}
  </div>

  <!-- SECAO 2: CONTRATOS ASSINADOS -->
  <div class="section-header green">SECAO 2 — CONTRATOS ASSINADOS NA SEMANA (CONCORRENTES)</div>
  <div class="content">
    {"".join([f'''
    <div class="card green">
      <div class="card-empresa">{c["empresa"]}</div>
      <div class="card-cnpj">CNPJ: {c["cnpj"]} &nbsp;·&nbsp; Assinado: {c["data"]} &nbsp;<span class="badge">{c["uf"]}</span></div>
      <div class="card-objeto"><strong>Orgao:</strong> {c["orgao"]}</div>
      <div class="card-objeto"><strong>Objeto:</strong> {c["objeto"]}</div>
      <div class="card-meta"><strong style="color:#1A5C36">{c["valor"]}</strong></div>
    </div>''' for c in contratos]) if contratos else '<div class="empty">Nenhum contrato assinado encontrado nesta semana com os filtros configurados.</div>'}
  </div>

  <div class="footer">
    Fontes: Portal Nacional de Contratações Públicas (PNCP) · pncp.gov.br<br>
    Você recebe este relatório pois está cadastrado no sistema de alertas.<br>
    Para cancelar ou alterar configurações, entre em contato com o suporte.
  </div>

</div>
</body>
</html>
"""
