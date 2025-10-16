from flask import Flask, render_template_string, request, redirect, url_for, session, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import date, datetime, timedelta
import sqlite3
import os
import shutil

app = Flask(__name__)
app.secret_key = 'sua-chave-secreta-aqui-mude-em-producao'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Configuração do Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, id, username):
        self.id = id
        self.username = username

@login_manager.user_loader
def load_user(user_id):
    conn = sqlite3.connect('pasteis.db')
    c = conn.cursor()
    c.execute('SELECT id, username FROM users WHERE id = ?', (user_id,))
    user = c.fetchone()
    conn.close()
    if user:
        return User(user[0], user[1])
    return None

def init_db():
    conn = sqlite3.connect('pasteis.db')
    c = conn.cursor()
    
    # Tabela de usuários
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT UNIQUE NOT NULL,
                  password_hash TEXT NOT NULL)''')
    
    # Tabela de pastéis
    c.execute('''CREATE TABLE IF NOT EXISTS pasteis
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  data TEXT NOT NULL,
                  quantidade INTEGER NOT NULL,
                  user_id INTEGER,
                  FOREIGN KEY (user_id) REFERENCES users (id))''')
    
    conn.commit()
    conn.close()

def get_quantidade(data):
    if not current_user.is_authenticated:
        return 0
    conn = sqlite3.connect('pasteis.db')
    c = conn.cursor()
    c.execute('SELECT quantidade FROM pasteis WHERE data = ? AND user_id = ?', (data, current_user.id))
    result = c.fetchone()
    conn.close()
    return result[0] if result else 0

def set_quantidade(data, quantidade):
    if not current_user.is_authenticated:
        return
    conn = sqlite3.connect('pasteis.db')
    c = conn.cursor()
    c.execute('SELECT id FROM pasteis WHERE data = ? AND user_id = ?', (data, current_user.id))
    existing = c.fetchone()
    
    if existing:
        c.execute('UPDATE pasteis SET quantidade = ? WHERE data = ? AND user_id = ?', 
                 (quantidade, data, current_user.id))
    else:
        c.execute('INSERT INTO pasteis (data, quantidade, user_id) VALUES (?, ?, ?)', 
                 (data, quantidade, current_user.id))
    
    conn.commit()
    conn.close()

def check_first_run():
    conn = sqlite3.connect('pasteis.db')
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM users')
    count = c.fetchone()[0]
    conn.close()
    return count == 0

def backup_current_db():
    """Cria backup do banco atual se existir"""
    if os.path.exists('pasteis.db'):
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_name = f'pasteis_backup_{timestamp}.db'
        shutil.copy2('pasteis.db', backup_name)
        return backup_name
    return None

def is_valid_db_file(filepath):
    """Verifica se o arquivo é um banco SQLite válido com as tabelas necessárias"""
    try:
        conn = sqlite3.connect(filepath)
        c = conn.cursor()
        
        # Verifica se as tabelas existem
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('users', 'pasteis')")
        tables = c.fetchall()
        conn.close()
        
        return len(tables) == 2
    except:
        return False

upload_template = '''
<!doctype html>
<html lang="pt-br">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Upload de Banco - Contador de Pastéis</title>
    <style>
        body { 
            font-family: sans-serif; 
            max-width: 500px; 
            margin: 2em auto; 
            background: #fafafa; 
            padding: 0 1em;
        }
        .center { text-align: center; }
        .form-row { margin-bottom: 1.5em; }
        label { 
            display: block; 
            margin-bottom: 0.5em; 
            font-weight: bold;
        }
        input[type=file] { 
            width: 100%;
            padding: 0.75em; 
            border: 2px dashed #ccc; 
            border-radius: 4px; 
            font-size: 16px;
            box-sizing: border-box;
            background: #f9f9f9;
        }
        button { 
            width: 100%;
            padding: 0.75em; 
            background: #007cba; 
            color: white; 
            border: none; 
            border-radius: 4px; 
            font-size: 16px;
            cursor: pointer;
            margin: 0.3em 0;
        }
        button:hover { background: #005a8b; }
        .skip-btn { background: #6c757d; }
        .skip-btn:hover { background: #545b62; }
        .alert { 
            padding: 1em; 
            margin: 1em 0; 
            border-radius: 4px; 
        }
        .alert-success { 
            background: #d4edda; 
            border: 1px solid #c3e6cb; 
            color: #155724; 
        }
        .alert-error { 
            background: #f8d7da; 
            border: 1px solid #f5c6cb; 
            color: #721c24; 
        }
        .alert-info { 
            background: #d1ecf1; 
            border: 1px solid #bee5eb; 
            color: #0c5460; 
        }
        .info-box {
            background: #e9ecef;
            padding: 1em;
            border-radius: 4px;
            margin-bottom: 1.5em;
            font-size: 14px;
        }
        .file-info {
            font-size: 12px;
            color: #666;
            margin-top: 0.5em;
        }
    </style>
</head>
<body>
    <h2 class="center">Configuração do Banco de Dados</h2>
    
    <div class="info-box">
        <strong>Opções disponíveis:</strong><br>
        • <strong>Upload:</strong> Envie um arquivo pasteis.db existente<br>
        • <strong>Usar existente:</strong> Continue com o banco atual (se houver)<br>
        • <strong>Criar novo:</strong> Inicie com banco vazio
    </div>
    
    {% if mensagem %}
    <div class="alert alert-{{ tipo_msg }}">{{ mensagem }}</div>
    {% endif %}
    
    {% if tem_banco_atual %}
    <div class="alert alert-info">
        <strong>Banco atual encontrado!</strong><br>
        Você pode continuar usando o banco existente ou fazer upload de outro.
    </div>
    {% endif %}
    
    <form method="post" enctype="multipart/form-data">
        <div class="form-row">
            <label for="database_file">Fazer Upload de Banco de Dados:</label>
            <input type="file" id="database_file" name="database_file" accept=".db">
            <div class="file-info">Apenas arquivos .db são aceitos (máximo 16MB)</div>
        </div>
        <button type="submit" name="acao" value="upload">📤 Fazer Upload</button>
        
        {% if tem_banco_atual %}
        <button type="submit" name="acao" value="usar_atual" class="skip-btn">📁 Usar Banco Atual</button>
        {% endif %}
        
        <button type="submit" name="acao" value="criar_novo" class="skip-btn">🆕 Criar Banco Novo</button>
    </form>
</body>
</html>
'''

login_template = '''
<!doctype html>
<html lang="pt-br">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login - Contador de Pastéis</title>
    <style>
        body { 
            font-family: sans-serif; 
            max-width: 400px; 
            margin: 2em auto; 
            background: #fafafa; 
            padding: 0 1em;
        }
        .center { text-align: center; }
        .form-row { margin-bottom: 1em; }
        label { 
            display: block; 
            margin-bottom: 0.5em; 
            font-weight: bold;
        }
        input[type=text], input[type=password] { 
            width: 100%;
            padding: 0.75em; 
            border: 1px solid #ccc; 
            border-radius: 4px; 
            font-size: 16px;
            box-sizing: border-box;
        }
        button { 
            width: 100%;
            padding: 0.75em; 
            background: #007cba; 
            color: white; 
            border: none; 
            border-radius: 4px; 
            font-size: 16px;
            cursor: pointer;
            margin-top: 1em;
        }
        button:hover { background: #005a8b; }
        .alert { 
            padding: 1em; 
            margin: 1em 0; 
            background: #ffebee; 
            border: 1px solid #ffcdd2; 
            border-radius: 4px; 
            color: #c62828; 
        }
        .logout { 
            text-align: right; 
            margin-bottom: 1em; 
        }
        .logout a { 
            color: #007cba; 
            text-decoration: none; 
            font-size: 14px;
        }
        .db-link {
            text-align: center;
            margin-top: 1em;
        }
        .db-link a {
            color: #007cba;
            text-decoration: none;
            font-size: 14px;
        }
    </style>
</head>
<body>
    <h2 class="center">{{ titulo }}</h2>
    
    {% if mensagem %}
    <div class="alert">{{ mensagem }}</div>
    {% endif %}
    
    <form method="post">
        <div class="form-row">
            <label for="username">Usuário:</label>
            <input type="text" id="username" name="username" required>
        </div>
        <div class="form-row">
            <label for="password">Senha:</label>
            <input type="password" id="password" name="password" required>
        </div>
        {% if primeira_vez %}
        <div class="form-row">
            <label for="confirm_password">Confirmar Senha:</label>
            <input type="password" id="confirm_password" name="confirm_password" required>
        </div>
        {% endif %}
        <button type="submit">{{ botao_texto }}</button>
    </form>
    
    <div class="db-link">
        <a href="/upload_db">Gerenciar Banco de Dados</a>
    </div>
</body>
</html>
'''

template = '''
<!doctype html>
<html lang="pt-br">
<head>
    <meta charset="utf-8">
    <title>Contador de Pastéis</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body { 
            font-family: sans-serif; 
            max-width: 400px; 
            margin: 1em auto; 
            background: #fafafa; 
            padding: 0 1em;
        }
        .center { text-align: center; }
        
        form { margin-bottom: 1em; }
        
        label { 
            display: inline-block; 
            margin-bottom: 0.5em; 
            font-weight: bold;
        }
        
        input[type=date], input[type=number] { 
            padding: 0.5em; 
            border: 1px solid #ccc; 
            border-radius: 4px; 
            font-size: 16px;
            margin-bottom: 0.5em;
        }
        
        input[type=number] { width: 80px; }
        
        button { 
            padding: 0.5em 1em; 
            background: #007cba; 
            color: white; 
            border: none; 
            border-radius: 4px; 
            font-size: 16px;
            cursor: pointer;
            margin: 0.2em;
        }
        
        button:hover { background: #005a8b; }
        
        .media { 
            margin-top: 2em; 
            padding: 1em; 
            background: #eee; 
            border-radius: 8px; 
        }
        
        .form-row { 
            margin-bottom: 1em; 
        }
        
        .form-row.inline { 
            display: flex; 
            align-items: center; 
            gap: 0.5em; 
        }
        
        .form-row.inline label { 
            margin-bottom: 0; 
            min-width: 80px;
        }
        
        @media (max-width: 480px) {
            body { 
                margin: 0.5em auto; 
                padding: 0 0.5em; 
            }
            
            .form-row.inline { 
                flex-direction: column; 
                align-items: stretch; 
            }
            
            .form-row.inline label { 
                min-width: auto; 
                margin-bottom: 0.3em;
            }
            
            input[type=date], input[type=number] { 
                width: 100%; 
                box-sizing: border-box;
            }
            
            input[type=number] { 
                max-width: 120px; 
                margin: 0 auto;
                display: block;
            }
            
            button { 
                width: 100%; 
                margin: 0.3em 0; 
            }
            
            .button-group { 
                display: flex; 
                gap: 0.5em; 
            }
            
            .button-group button { 
                flex: 1; 
                width: auto;
            }
        }
    </style>
    <script>
        function atualizarQuantidade() {
            const dataInput = document.getElementById('data');
            const quantidadeInput = document.getElementById('quantidade');
            
            dataInput.addEventListener('change', function() {
                fetch('/get_quantidade?data=' + this.value)
                    .then(response => response.json())
                    .then(data => {
                        quantidadeInput.value = data.quantidade;
                        document.getElementById('quantidade-display').textContent = data.quantidade;
                    });
            });
        }
        
        window.onload = atualizarQuantidade;
    </script>
</head>
<body>
    <div class="logout">
        <a href="/logout">Sair ({{ current_user.username }})</a>
    </div>
    <h2 class="center">Contador de Pastéis</h2>
    <form method="post" action="/add">
        <div class="form-row">
            <label for="data">Dia:</label>
            <input type="date" id="data" name="data" value="{{ data }}">
        </div>
        <div class="form-row inline">
            <label for="quantidade">Quantidade:</label>
            <input type="number" id="quantidade" name="quantidade" min="0" value="{{ quantidade }}">
        </div>
        <div class="button-group">
            <button type="submit" name="acao" value="add">+ Adicionar</button>
            <button type="submit" name="acao" value="set">Salvar</button>
        </div>
    </form>
    <div class="center">
        <p>Pastéis neste dia: <b><span id="quantidade-display">{{ quantidade }}</span></b></p>
    </div>
    <hr>
    <form method="get" action="/media">
        <div class="form-row inline">
            <label for="inicio">De:</label>
            <input type="date" id="inicio" name="inicio" value="{{ inicio }}">
        </div>
        <div class="form-row inline">
            <label for="fim">Até:</label>
            <input type="date" id="fim" name="fim" value="{{ fim }}">
        </div>
        <button type="submit">Calcular média</button>
    </form>
    {% if media is not none %}
    <div class="media center">
        <b>Média no período:</b> {{ media }} pastéis/dia
    </div>
    {% endif %}
</body>
</html>
'''

def get_quantidade(d):
    return pasteis_por_dia.get(d, 0)

def get_quantidade(data):
    if not current_user.is_authenticated:
        return 0
    conn = sqlite3.connect('pasteis.db')
    c = conn.cursor()
    c.execute('SELECT quantidade FROM pasteis WHERE data = ? AND user_id = ?', (data, current_user.id))
    result = c.fetchone()
    conn.close()
    return result[0] if result else 0

@app.route('/upload_db', methods=['GET', 'POST'])
def upload_db():
    tem_banco_atual = os.path.exists('pasteis.db')
    
    if request.method == 'POST':
        acao = request.form.get('acao')
        
        if acao == 'upload':
            if 'database_file' not in request.files:
                return render_template_string(upload_template, 
                                            mensagem="Nenhum arquivo selecionado",
                                            tipo_msg="error",
                                            tem_banco_atual=tem_banco_atual)
            
            file = request.files['database_file']
            if file.filename == '':
                return render_template_string(upload_template, 
                                            mensagem="Nenhum arquivo selecionado",
                                            tipo_msg="error",
                                            tem_banco_atual=tem_banco_atual)
            
            if file and file.filename.lower().endswith('.db'):
                # Salva temporariamente para validar
                temp_filename = 'temp_upload.db'
                file.save(temp_filename)
                
                # Valida o arquivo
                if is_valid_db_file(temp_filename):
                    # Faz backup do banco atual se existir
                    backup_name = backup_current_db()
                    
                    # Substitui o banco atual
                    if os.path.exists('pasteis.db'):
                        os.remove('pasteis.db')
                    shutil.move(temp_filename, 'pasteis.db')
                    
                    mensagem = "Banco de dados carregado com sucesso!"
                    if backup_name:
                        mensagem += f" Backup criado: {backup_name}"
                    
                    # Redireciona para verificar se precisa de setup ou login
                    if check_first_run():
                        return redirect(url_for('setup'))
                    else:
                        flash("Banco de dados carregado com sucesso!")
                        return redirect(url_for('login'))
                else:
                    os.remove(temp_filename)
                    return render_template_string(upload_template, 
                                                mensagem="Arquivo inválido. Deve ser um banco pasteis.db válido",
                                                tipo_msg="error",
                                                tem_banco_atual=tem_banco_atual)
            else:
                return render_template_string(upload_template, 
                                            mensagem="Formato inválido. Apenas arquivos .db são aceitos",
                                            tipo_msg="error",
                                            tem_banco_atual=tem_banco_atual)
        
        elif acao == 'usar_atual':
            if tem_banco_atual:
                if check_first_run():
                    return redirect(url_for('setup'))
                else:
                    flash("Continuando com o banco atual")
                    return redirect(url_for('login'))
            else:
                return render_template_string(upload_template, 
                                            mensagem="Nenhum banco atual encontrado",
                                            tipo_msg="error",
                                            tem_banco_atual=tem_banco_atual)
        
        elif acao == 'criar_novo':
            # Faz backup do banco atual se existir
            backup_name = backup_current_db()
            
            # Remove banco atual e cria novo
            if os.path.exists('pasteis.db'):
                os.remove('pasteis.db')
            init_db()
            
            mensagem = "Novo banco criado!"
            if backup_name:
                mensagem += f" Backup do anterior: {backup_name}"
            
            return redirect(url_for('setup'))
    
    return render_template_string(upload_template, 
                                mensagem=None,
                                tipo_msg=None,
                                tem_banco_atual=tem_banco_atual)

@app.route('/login', methods=['GET', 'POST'])
def login():
    # Verifica se é a primeira execução ou se não existe banco
    if not os.path.exists('pasteis.db'):
        return redirect(url_for('upload_db'))
    
    # Se existe banco mas é primeira execução (sem usuários), vai para setup
    if check_first_run():
        return redirect(url_for('setup'))
    
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = sqlite3.connect('pasteis.db')
        c = conn.cursor()
        c.execute('SELECT id, username, password_hash FROM users WHERE username = ?', (username,))
        user = c.fetchone()
        conn.close()
        
        if user and check_password_hash(user[2], password):
            user_obj = User(user[0], user[1])
            login_user(user_obj)
            return redirect(url_for('index'))
        else:
            return render_template_string(login_template, 
                                        titulo="Login", 
                                        botao_texto="Entrar",
                                        primeira_vez=False,
                                        mensagem="Usuário ou senha incorretos")
    
    return render_template_string(login_template, 
                                titulo="Login", 
                                botao_texto="Entrar",
                                primeira_vez=False,
                                mensagem=None)

@app.route('/db_manager')
def db_manager():
    """Rota para gerenciar banco de dados quando já existe um"""
    return redirect(url_for('upload_db'))

@app.route('/setup', methods=['GET', 'POST'])
def setup():
    # Se não existe banco, redireciona para upload
    if not os.path.exists('pasteis.db'):
        return redirect(url_for('upload_db'))
    
    # Se já existe usuário, redireciona para login
    if not check_first_run():
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        if password != confirm_password:
            return render_template_string(login_template, 
                                        titulo="Configuração Inicial", 
                                        botao_texto="Criar Usuário",
                                        primeira_vez=True,
                                        mensagem="As senhas não coincidem")
        
        if len(password) < 4:
            return render_template_string(login_template, 
                                        titulo="Configuração Inicial", 
                                        botao_texto="Criar Usuário",
                                        primeira_vez=True,
                                        mensagem="A senha deve ter pelo menos 4 caracteres")
        
        # Cria o primeiro usuário
        conn = sqlite3.connect('pasteis.db')
        c = conn.cursor()
        password_hash = generate_password_hash(password)
        c.execute('INSERT INTO users (username, password_hash) VALUES (?, ?)', 
                 (username, password_hash))
        conn.commit()
        conn.close()
        
        return redirect(url_for('login'))
    
    return render_template_string(login_template, 
                                titulo="Configuração Inicial", 
                                botao_texto="Criar Usuário",
                                primeira_vez=True,
                                mensagem=None)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/', methods=['GET'])
@login_required
def index():
    hoje = date.today().isoformat()
    data = request.args.get('data', hoje)
    quantidade = get_quantidade(data)
    return render_template_string(template, data=data, quantidade=quantidade, inicio=hoje, fim=hoje, media=None)

@app.route('/add', methods=['POST'])
@login_required
def add():
    data = request.form.get('data', date.today().isoformat())
    acao = request.form.get('acao')
    try:
        quantidade = int(request.form.get('quantidade', 0))
    except ValueError:
        quantidade = 0
    if acao == 'add':
        quantidade = get_quantidade(data) + 1
    set_quantidade(data, quantidade)
    return redirect(url_for('index', data=data))

@app.route('/media', methods=['GET'])
@login_required
def media():
    inicio = request.args.get('inicio', date.today().isoformat())
    fim = request.args.get('fim', date.today().isoformat())
    try:
        d1 = datetime.strptime(inicio, '%Y-%m-%d').date()
        d2 = datetime.strptime(fim, '%Y-%m-%d').date()
    except Exception:
        d1 = d2 = date.today()
    if d1 > d2:
        d1, d2 = d2, d1
    dias = (d2 - d1).days + 1
    
    # Busca dados do banco
    conn = sqlite3.connect('pasteis.db')
    c = conn.cursor()
    c.execute('''SELECT data, quantidade FROM pasteis 
                 WHERE data BETWEEN ? AND ? AND user_id = ?''', 
              (d1.isoformat(), d2.isoformat(), current_user.id))
    dados = {row[0]: row[1] for row in c.fetchall()}
    conn.close()
    
    total = sum(dados.get((d1 + timedelta(days=i)).isoformat(), 0) for i in range(dias))
    media = round(total / dias, 2) if dias > 0 else 0
    return render_template_string(template, data=d2.isoformat(), quantidade=get_quantidade(d2.isoformat()), inicio=inicio, fim=fim, media=media)

@app.route('/get_quantidade', methods=['GET'])
@login_required
def get_quantidade_ajax():
    data = request.args.get('data', date.today().isoformat())
    quantidade = get_quantidade(data)
    return {'quantidade': quantidade}

if __name__ == '__main__':
    # Verifica se existe banco, se não redireciona para upload
    if os.path.exists('pasteis.db'):
        init_db()  # Garante que as tabelas existem
    
    # Porta configurável via variável de ambiente (equivalente ao Node.js)
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=True)
