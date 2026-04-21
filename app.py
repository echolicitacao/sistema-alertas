"""
SISTEMA DE MONITORAMENTO E ALERTAS
Painel administrativo + envio semanal de relatórios por e-mail
"""

from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
import sqlite3, hashlib, os, json
from datetime import datetime, timedelta
from email_service import enviar_relatorio
from pncp_service import buscar_licitacoes, buscar_contratos_assinados

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "troque-esta-chave-secreta-123")

DB_PATH = os.environ.get("DB_PATH", "sistema.db")
ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASS = os.environ.get("ADMIN_PASS", "admin123")

# ──────────────────────────────────────────────────────────────────
# BANCO DE DADOS
# ──────────────────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            nome        TEXT NOT NULL,
            email       TEXT NOT NULL UNIQUE,
            palavras    TEXT NOT NULL DEFAULT '',
            estados     TEXT NOT NULL DEFAULT '',
            valor_min   REAL NOT NULL DEFAULT 1000000,
            plano       TEXT NOT NULL DEFAULT 'basico',
            ativo       INTEGER NOT NULL DEFAULT 1,
            criado_em   TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS envios (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id      INTEGER NOT NULL,
            enviado_em      TEXT NOT NULL DEFAULT (datetime('now')),
            qtd_licitacoes  INTEGER NOT NULL DEFAULT 0,
            qtd_contratos   INTEGER NOT NULL DEFAULT 0,
            status          TEXT NOT NULL DEFAULT 'sucesso',
            erro            TEXT,
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
        );

        CREATE TABLE IF NOT EXISTS editais_enviados (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id  INTEGER NOT NULL,
            edital_id   TEXT NOT NULL,
            enviado_em  TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(usuario_id, edital_id)
        );
    """)
    conn.commit()
    conn.close()

# ──────────────────────────────────────────────────────────────────
# AUTENTICAÇÃO
# ──────────────────────────────────────────────────────────────────

def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logado"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = request.form.get("usuario", "")
        pwd  = request.form.get("senha", "")
        if user == ADMIN_USER and pwd == ADMIN_PASS:
            session["logado"] = True
            return redirect(url_for("index"))
        flash("Usuário ou senha incorretos.", "erro")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ──────────────────────────────────────────────────────────────────
# PAINEL PRINCIPAL
# ──────────────────────────────────────────────────────────────────

@app.route("/")
@login_required
def index():
    conn = get_db()
    usuarios = conn.execute(
        "SELECT * FROM usuarios ORDER BY criado_em DESC"
    ).fetchall()
    ultimo_envio = conn.execute(
        "SELECT enviado_em FROM envios ORDER BY enviado_em DESC LIMIT 1"
    ).fetchone()
    total_envios = conn.execute("SELECT COUNT(*) FROM envios").fetchone()[0]
    ativos = conn.execute("SELECT COUNT(*) FROM usuarios WHERE ativo=1").fetchone()[0]
    conn.close()
    return render_template("index.html",
        usuarios=usuarios,
        ultimo_envio=ultimo_envio,
        total_envios=total_envios,
        ativos=ativos
    )

# ──────────────────────────────────────────────────────────────────
# CRUD USUÁRIOS
# ──────────────────────────────────────────────────────────────────

ESTADOS_BR = ["AC","AL","AP","AM","BA","CE","DF","ES","GO","MA","MT","MS",
              "MG","PA","PB","PR","PE","PI","RJ","RN","RS","RO","RR","SC",
              "SP","SE","TO"]

@app.route("/usuario/novo", methods=["GET", "POST"])
@login_required
def novo_usuario():
    if request.method == "POST":
        nome      = request.form.get("nome", "").strip()
        email     = request.form.get("email", "").strip().lower()
        palavras  = request.form.get("palavras", "").strip()
        estados   = ",".join(request.form.getlist("estados"))
        valor_min = float(request.form.get("valor_min", 1000000))
        plano     = request.form.get("plano", "basico")

        if not nome or not email:
            flash("Nome e e-mail são obrigatórios.", "erro")
            return render_template("form_usuario.html", estados=ESTADOS_BR, usuario=None)

        try:
            conn = get_db()
            conn.execute(
                "INSERT INTO usuarios (nome,email,palavras,estados,valor_min,plano) VALUES (?,?,?,?,?,?)",
                (nome, email, palavras, estados, valor_min, plano)
            )
            conn.commit()
            conn.close()
            flash(f"Usuário {nome} cadastrado com sucesso!", "sucesso")
            return redirect(url_for("index"))
        except sqlite3.IntegrityError:
            flash("Este e-mail já está cadastrado.", "erro")

    return render_template("form_usuario.html", estados=ESTADOS_BR, usuario=None)

@app.route("/usuario/<int:uid>/editar", methods=["GET", "POST"])
@login_required
def editar_usuario(uid):
    conn = get_db()
    usuario = conn.execute("SELECT * FROM usuarios WHERE id=?", (uid,)).fetchone()
    if not usuario:
        conn.close()
        flash("Usuário não encontrado.", "erro")
        return redirect(url_for("index"))

    if request.method == "POST":
        nome      = request.form.get("nome", "").strip()
        email     = request.form.get("email", "").strip().lower()
        palavras  = request.form.get("palavras", "").strip()
        estados   = ",".join(request.form.getlist("estados"))
        valor_min = float(request.form.get("valor_min", 1000000))
        plano     = request.form.get("plano", "basico")

        conn.execute(
            "UPDATE usuarios SET nome=?,email=?,palavras=?,estados=?,valor_min=?,plano=? WHERE id=?",
            (nome, email, palavras, estados, valor_min, plano, uid)
        )
        conn.commit()
        conn.close()
        flash(f"Usuário {nome} atualizado!", "sucesso")
        return redirect(url_for("index"))

    conn.close()
    return render_template("form_usuario.html", estados=ESTADOS_BR, usuario=usuario)

@app.route("/usuario/<int:uid>/toggle", methods=["POST"])
@login_required
def toggle_usuario(uid):
    conn = get_db()
    usuario = conn.execute("SELECT * FROM usuarios WHERE id=?", (uid,)).fetchone()
    if usuario:
        novo_status = 0 if usuario["ativo"] else 1
        conn.execute("UPDATE usuarios SET ativo=? WHERE id=?", (novo_status, uid))
        conn.commit()
        status_texto = "ativado" if novo_status else "desativado"
        flash(f"Usuário {status_texto}.", "sucesso")
    conn.close()
    return redirect(url_for("index"))

@app.route("/usuario/<int:uid>/historico")
@login_required
def historico_usuario(uid):
    conn = get_db()
    usuario = conn.execute("SELECT * FROM usuarios WHERE id=?", (uid,)).fetchone()
    envios  = conn.execute(
        "SELECT * FROM envios WHERE usuario_id=? ORDER BY enviado_em DESC LIMIT 90",
        (uid,)
    ).fetchall()
    conn.close()
    return render_template("historico.html", usuario=usuario, envios=envios)

# ──────────────────────────────────────────────────────────────────
# DISPARO MANUAL
# ──────────────────────────────────────────────────────────────────

@app.route("/usuario/<int:uid>/disparar", methods=["POST"])
@login_required
def disparar_manual(uid):
    conn = get_db()
    usuario = conn.execute("SELECT * FROM usuarios WHERE id=?", (uid,)).fetchone()
    conn.close()
    if not usuario:
        flash("Usuário não encontrado.", "erro")
        return redirect(url_for("index"))
    try:
        resultado = processar_usuario(dict(usuario))
        flash(f"Relatório enviado para {usuario['email']} — {resultado['licitacoes']} oportunidades, {resultado['contratos']} contratos.", "sucesso")
    except Exception as e:
        flash(f"Erro ao enviar: {str(e)}", "erro")
    return redirect(url_for("index"))

@app.route("/disparar-todos", methods=["POST"])
@login_required
def disparar_todos():
    executar_envio_semanal()
    flash("Envio semanal executado para todos os usuários ativos.", "sucesso")
    return redirect(url_for("index"))

# ──────────────────────────────────────────────────────────────────
# LÓGICA DE PROCESSAMENTO
# ──────────────────────────────────────────────────────────────────

def processar_usuario(usuario):
    uid       = usuario["id"]
    palavras  = [p.strip() for p in usuario["palavras"].split(",") if p.strip()]
    estados   = [e.strip() for e in usuario["estados"].split(",") if e.strip()]
    valor_min = float(usuario["valor_min"])

    # Buscar IDs já enviados para este usuário (deduplicação)
    conn = get_db()
    ja_enviados = set(
        row[0] for row in conn.execute(
            "SELECT edital_id FROM editais_enviados WHERE usuario_id=?", (uid,)
        ).fetchall()
    )

    # Buscar licitações abertas
    licitacoes = buscar_licitacoes(palavras, estados, valor_min, ja_enviados)

    # Buscar contratos assinados na última semana
    contratos = buscar_contratos_assinados(palavras, estados, valor_min)

    # Enviar e-mail
    enviar_relatorio(
        destinatario=usuario["email"],
        nome=usuario["nome"],
        licitacoes=licitacoes,
        contratos=contratos,
        semana=datetime.now().strftime("%d/%m/%Y")
    )

    # Registrar IDs enviados (deduplicação futura)
    for lic in licitacoes:
        try:
            conn.execute(
                "INSERT OR IGNORE INTO editais_enviados (usuario_id, edital_id) VALUES (?,?)",
                (uid, lic.get("id", ""))
            )
        except:
            pass

    # Registrar envio no histórico
    conn.execute(
        "INSERT INTO envios (usuario_id, qtd_licitacoes, qtd_contratos, status) VALUES (?,?,?,?)",
        (uid, len(licitacoes), len(contratos), "sucesso")
    )
    conn.commit()
    conn.close()

    return {"licitacoes": len(licitacoes), "contratos": len(contratos)}

def executar_envio_semanal():
    print(f"[{datetime.now()}] Iniciando envio semanal...")
    conn = get_db()
    usuarios = conn.execute("SELECT * FROM usuarios WHERE ativo=1").fetchall()
    conn.close()

    for u in usuarios:
        try:
            resultado = processar_usuario(dict(u))
            print(f"  OK: {u['email']} — {resultado['licitacoes']} licitações, {resultado['contratos']} contratos")
        except Exception as e:
            print(f"  ERRO: {u['email']} — {str(e)}")
            conn = get_db()
            conn.execute(
                "INSERT INTO envios (usuario_id, status, erro) VALUES (?,?,?)",
                (u["id"], "erro", str(e))
            )
            conn.commit()
            conn.close()

    print(f"[{datetime.now()}] Envio semanal concluído.")

# ──────────────────────────────────────────────────────────────────
# INICIALIZAÇÃO
# ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    init_db()

    # Agendamento: toda segunda-feira às 7h
    
    scheduler.add_job(executar_envio_semanal, "cron", day_of_week="mon", hour=7, minute=0)
    
    print("Sistema iniciado. Painel em: http://localhost:5000")
    print("Login: admin / admin123")

    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
