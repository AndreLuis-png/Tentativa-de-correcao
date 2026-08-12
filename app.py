#pip install flask flask-mysqldb mysqlclient bcrypt  --Instalar antes de usar o código

import os
import re
import unicodedata
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_mysqldb import MySQL
import bcrypt
import MySQLdb.cursors
from flask_cors import CORS
from rotasAPI.produtos_api import api_bp

app = Flask(__name__, template_folder='rotasURL/templates', static_folder='rotasURL/static')
CORS(app)  # Permite que o Expo Go acesse seu backend
app.register_blueprint(api_bp)  # Registra as rotas da API no servidor
app.secret_key = os.urandom(24)

# Configurações de Conexão com o Banco de Dados
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''  
app.config['MYSQL_DB'] = 'almoxarifado_db'

mysql = MySQL(app)

# ==========================================
# FUNÇÕES AUXILIARES E DE SEGURANÇA
# ==========================================

def limpar_texto(texto):
    """
    Remove acentuações, caracteres especiais de combinação e espaços em branco desnecessários.
    Converte o texto todo para minúsculo e, por fim, capitaliza apenas a primeira letra.
    Ideal para padronizar nomes de produtos e evitar duplicatas por erro de digitação.
    """
    if not texto:
        return ""
    nfkd_form = unicodedata.normalize('NFKD', texto)
    texto_sem_acento = "".join([c for c in nfkd_form if not unicodedata.combining(c)])
    texto_limpo = texto_sem_acento.strip().lower()
    return texto_limpo.capitalize()

def checar_bloqueio():
    """
    Valida se o usuário logado teve a conta suspensa em tempo real.
    Consulta o banco de dados e, se o status do usuário não for 'ativo',
    limpa a sessão (desloga) e avisa que a conta foi bloqueada.
    """
    if 'logged_in' in session and session.get('usuario'):
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("SELECT status FROM usuarios WHERE login = %s", (session['usuario'],))
        usr = cursor.fetchone()
        if usr and usr.get('status') != 'ativo':
            session.clear()
            flash("Sua conta encontra-se suspensa/bloqueada pelo administrador.")
            return False
    return True

def verificar_chave_secundaria(chave_digitada):
    """
    Valida de forma segura o hash Bcrypt da chave mecânica secundária.
    Pega a chave digitada pelo usuário, busca a hash correspondente no banco (ID = 1 na config_admin)
    e compara utilizando a função de checagem do Bcrypt para evitar vazamento de senhas em texto puro.
    """
    if not chave_digitada:
        return False
        
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT chave_secundaria FROM config_admin WHERE id = 1")
    reg = cursor.fetchone()
    
    if not reg or not reg.get('chave_secundaria'):
        return False
        
    try:
        hash_banco = reg['chave_secundaria'].encode('utf-8')
        return bcrypt.checkpw(chave_digitada.encode('utf-8'), hash_banco)
    except (ValueError, TypeError):
        # Trata erros caso a chave no banco esteja em formato inválido
        return False

def gerar_proximo_id(area):
    """
    Gera um novo ID de produto (formato de 5 dígitos) baseado na área/categoria do item.
    Atribui um prefixo ('0' Geral, '1' Mecânica, '2' Elétrica) e busca os IDs já existentes
    para encontrar o próximo número livre na sequência, evitando colisões de ID.
    """
    prefixos = {'Geral': '0', 'Mecânica': '1', 'Elétrica': '2'}
    prefixo = prefixos.get(area, '0')
    
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT id_produto FROM estoque WHERE id_produto LIKE %s ORDER BY id_produto ASC", (prefixo + '%',))
    
    ids_existentes = []
    for row in cursor.fetchall():
        try:
            ids_existentes.append(int(row['id_produto']))
        except ValueError:
            continue
    
    inicio_sequencia = int(prefixo + "0001")
    proximo_numero = inicio_sequencia
    while proximo_numero in ids_existentes:
        proximo_numero += 1
        
    return f"{proximo_numero:05d}"

# ==========================================
# ROTAS PRINCIPAIS
# ==========================================

@app.route('/', methods=['GET', 'POST'])
def login():
    """
    Rota inicial de Autenticação.
    Recebe login e senha do formulário, busca o usuário no banco de dados e verifica a 
    autenticidade da senha usando Bcrypt. Se passar, cria variáveis de sessão (logged_in, usuario, is_admin)
    e redireciona para o lobby; caso contrário, avisa do erro.
    """
    if request.method == 'POST':
        usuario = request.form['usuario']
        senha = request.form['senha']
        
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("SELECT * FROM usuarios WHERE login = %s", (usuario,))
        account = cursor.fetchone()
        
        if account:
            senha_banco = account.get('senha')
            if senha_banco and bcrypt.checkpw(senha.encode('utf-8'), senha_banco.encode('utf-8')):
                if account.get('status') != 'ativo':
                    flash(f"Este utilizador encontra-se suspenso/bloqueado. Status: {account.get('status')}.")
                    return redirect(url_for('login'))
                    
                session['logged_in'] = True
                session['usuario'] = account['login']
                session['is_admin'] = (account['role'] == 'admin')
                return redirect(url_for('lobby'))
            else:
                flash("Utilizador ou Palavra-passe incorretos!")
        else:
            flash("Utilizador ou Palavra-passe incorretos!")
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    """
    Rota para deslogar do sistema.
    Limpa completamente os dados salvos no cookie de sessão e manda o usuário de volta pro login.
    """
    session.clear()
    return redirect(url_for('login'))

@app.route('/lobby', methods=['GET'])
@app.route('/lobby/<area_filtro>', methods=['GET'])
def lobby(area_filtro='Todos'):
    """
    Página principal do almoxarifado (Dashboard).
    Lista todos os produtos do estoque. Permite filtrar os itens por área, 
    pesquisar por texto (nome, ID ou preço) e ordenar o resultado de forma crescente/decrescente pelo preço.
    """
    if 'logged_in' not in session or not checar_bloqueio():
        return redirect(url_for('login'))
        
    termo_pesquisa = request.args.get('pesquisa', '').strip()
    ordem_preco = request.args.get('ordem', '').strip()
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    query = """
        SELECT id_produto, nome, area, quantidade, preco, descricao, 
        CASE WHEN link_midia IS NOT NULL AND link_midia != '' THEN 1 ELSE 0 END as possui_imagem 
        FROM estoque WHERE 1=1
    """
    params = []
    
    if area_filtro != 'Todos':
        query += " AND area = %s"
        params.append(area_filtro)
        
    if termo_pesquisa:
        query += " AND (nome LIKE %s OR id_produto LIKE %s OR CAST(preco AS CHAR) LIKE %s)"
        params.append('%' + termo_pesquisa + '%')
        params.append('%' + termo_pesquisa + '%')
        params.append('%' + termo_pesquisa + '%')
        
    if ordem_preco == 'crescente':
        query += " ORDER BY preco ASC"
    elif ordem_preco == 'decrescente':
        query += " ORDER BY preco DESC"
    else:
        query += " ORDER BY id_produto ASC"
        
    cursor.execute(query, tuple(params))
    itens_estoque = cursor.fetchall()
    
    cursor.execute("SELECT id_produto, nome, preco FROM estoque")
    sugestoes = cursor.fetchall()
    
    return render_template('lobby.html', estoque=itens_estoque, area_atual=area_filtro, sugestoes=sugestoes, termo_pesquisa=termo_pesquisa, ordem_atual=ordem_preco)

@app.route('/api/obter_link_imagem/<id_produto>')
def obter_link_imagem(id_produto):
    """
    Endpoint de API (Backend).
    Retorna no formato JSON a URL de mídia/imagem vinculada a um produto específico.
    Geralmente chamado via JavaScript ou requisições assíncronas (AJAX).
    """
    if 'logged_in' not in session or not checar_bloqueio():
        return jsonify({'error': 'Não autorizado'}), 401
    
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT link_midia FROM estoque WHERE id_produto = %s", (id_produto,))
    produto = cursor.fetchone()
    return jsonify({'link_url': produto['link_midia'] if produto else None})

@app.route('/insercao', methods=['GET', 'POST'])
def insercao():
    """
    Rota para Entrada/Cadastro de Materiais.
    Se o produto já existir no banco (mesmo nome e área), ele apenas adiciona a nova quantidade 
    ao estoque atual e atualiza o preço. Se não existir, gera um ID e cria um registro novo.
    Salva uma entrada detalhada na tabela `historico_logs` auditar a ação.
    """
    if 'logged_in' not in session or not checar_bloqueio():
        return redirect(url_for('login'))
        
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    if request.method == 'POST':
        nome = limpar_texto(request.form['nome'])
        area = request.form['area']
        
        try:
            quantidade = int(request.form['quantidade'])
        except (ValueError, KeyError):
            quantidade = 1
            
        try:
            preco = float(str(request.form['preco']).replace(',', '.'))
        except (ValueError, KeyError):
            preco = 0.0
            
        descricao = limpar_texto(request.form.get('descricao', ''))
        link_imagem = request.form.get('link_imagem', None)
        
        cursor.execute("SELECT * FROM estoque WHERE nome = %s AND area = %s", (nome, area))
        produto_existente = cursor.fetchone()
        
        if produto_existente:
            nova_qtd = produto_existente['quantidade'] + quantidade
            cursor.execute("UPDATE estoque SET quantidade = %s, preco = %s WHERE id_produto = %s", (nova_qtd, preco, produto_existente['id_produto']))
            id_final = produto_existente['id_produto']
        else:
            id_final = gerar_proximo_id(area)
            cursor.execute("""
                INSERT INTO estoque (id_produto, nome, area, quantidade, preco, descricao, link_midia)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (id_final, nome, area, quantidade, preco, descricao, link_imagem if link_imagem else None))
            
        cursor.execute("""
            INSERT INTO historico_logs (usuario, acao, detalhe)
            VALUES (%s, 'Inserção', %s)
        """, (session['usuario'], f"Adicionado {quantidade} un do item {nome} (ID: {id_final}) a R${preco:.2f} cada"))
        
        mysql.connection.commit()
        flash(f"Entrada do item '{nome}' registrada com sucesso!", "success")
        return redirect(url_for('lobby'))
        
    cursor.execute("SELECT id_produto, nome, preco FROM estoque")
    sugestoes = cursor.fetchall()
    return render_template('insercao.html', sugestoes=sugestoes)

@app.route('/retirada', methods=['GET', 'POST'])
def retirada():
    """
    Rota para Baixa/Retirada de Materiais.
    Pega a quantidade que o usuário quer retirar, verifica se há estoque suficiente
    no banco de dados e deduz essa quantidade. Também salva a ação na tabela de logs para auditoria.
    """
    if 'logged_in' not in session or not checar_bloqueio():
        return redirect(url_for('login'))
        
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    if request.method == 'POST':
        nome_selecionado = request.form['nome']
        
        try:
            quantidade_retirar = int(request.form['quantidade'])
        except (ValueError, KeyError):
            quantidade_retirar = 1
        
        cursor.execute("SELECT * FROM estoque WHERE nome = %s AND quantidade >= %s", (nome_selecionado, quantidade_retirar))
        produto = cursor.fetchone()
        
        if produto:
            nova_qtd = produto['quantidade'] - quantidade_retirar
            cursor.execute("UPDATE estoque SET quantidade = %s WHERE id_produto = %s", (nova_qtd, produto['id_produto']))
            
            cursor.execute("""
                INSERT INTO historico_logs (usuario, acao, detalhe)
                VALUES (%s, 'Retirada', %s)
            """, (session['usuario'], f"Retirado {quantidade_retirar} un do item {produto['nome']} (ID: {produto['id_produto']})"))
            
            mysql.connection.commit()
            flash("Baixa efetuada com sucesso!", "success")
            return redirect(url_for('lobby'))
        else:
            flash("Erro: Produto não encontrado ou quantidade insuficiente em estoque!", "error")
            
    cursor.execute("SELECT id_produto, nome, preco FROM estoque WHERE quantidade > 0")
    sugestoes = cursor.fetchall()
    return render_template('retirada.html', sugestoes=sugestoes)

@app.route('/editar/<id_produto>', methods=['GET', 'POST'])
def editar(id_produto):
    """
    Rota para Edição ou Exclusão de Produtos.
    Processa dois botões (ações) diferentes: 
    1. 'excluir' -> Apaga completamente o item do banco de dados.
    2. 'salvar' -> Atualiza as colunas do banco com as novas informações fornecidas.
    Ambas as ações criam um registro no histórico de logs.
    """
    if 'logged_in' not in session or not checar_bloqueio():
        return redirect(url_for('login'))
        
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    if request.method == 'POST':
        botao_acao = request.form.get('botao_acao')
        
        if botao_acao == 'excluir':
            cursor.execute("SELECT nome FROM estoque WHERE id_produto = %s", (id_produto,))
            prod = cursor.fetchone()
            if prod:
                cursor.execute("DELETE FROM estoque WHERE id_produto = %s", (id_produto,))
                cursor.execute("""
                    INSERT INTO historico_logs (usuario, acao, detalhe)
                    VALUES (%s, 'Exclusão', %s)
                """, (session['usuario'], f"Apagado o produto {prod['nome']} (ID: {id_produto}) permanentemente."))
                mysql.connection.commit()
                flash("Produto removido definitivamente do estoque.", "success")
            return redirect(url_for('lobby'))
            
        elif botao_acao == 'salvar':
            nome = limpar_texto(request.form['nome'])
            area = request.form['area']
            
            try:
                quantidade = int(request.form['quantidade'])
            except (ValueError, KeyError):
                quantidade = 0
                
            try:
                preco = float(str(request.form['preco']).replace(',', '.'))
            except (ValueError, KeyError):
                preco = 0.0
                
            descricao = limpar_texto(request.form.get('descricao', ''))
            link_imagem = request.form.get('link_imagem', None)
            
            cursor.execute("""
                UPDATE estoque 
                SET nome = %s, area = %s, quantidade = %s, preco = %s, descricao = %s, link_midia = %s
                WHERE id_produto = %s
            """, (nome, area, quantidade, preco, descricao, link_imagem if link_imagem else None, id_produto))
            
            cursor.execute("""
                INSERT INTO historico_logs (usuario, acao, detalhe)
                VALUES (%s, 'Alteração', %s)
            """, (session['usuario'], f"Editou propriedades do item {nome} (ID: {id_produto})"))
            
            mysql.connection.commit()
            flash("Informações do material atualizadas!", "success")
            return redirect(url_for('lobby'))

    cursor.execute("SELECT id_produto, nome, area, quantidade, preco, descricao, link_midia as link_imagem FROM estoque WHERE id_produto = %s", (id_produto,))
    produto = cursor.fetchone()
    
    cursor.execute("SELECT id_produto, nome, preco FROM estoque")
    sugestoes = cursor.fetchall()
    return render_template('editar.html', produto=produto, sugestoes=sugestoes)

# ==========================================
# PAINEL ADMINISTRATIVO
# ==========================================

@app.route('/admin_panel', methods=['GET', 'POST'])
def admin_panel():
    """
    Rota de Administração do Sistema (Exclusiva para role 'admin').
    Possui várias ferramentas centralizadas via parâmetro `action` no POST:
    - 'create_user': Cria uma nova conta com uma senha cifrada com bcrypt.
    - 'suspender' / 'reativar': Muda o status da conta de um usuário (impedindo-o de logar).
    - 'alterar_chave': Atualiza a chave de segurança administrativa criptografando-a.
    Na requisição GET padrão, também exibe listas de usuários e o histórico recente do sistema.
    """
    if 'logged_in' not in session or not session.get('is_admin') or not checar_bloqueio():
        flash("Acesso restrito apenas a administradores!")
        return redirect(url_for('lobby'))
        
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'create_user':
            novo_usuario = request.form['novo_usuario'].strip()
            nova_senha = request.form['nova_senha']
            role = request.form['role']
            
            cursor.execute("SELECT * FROM usuarios WHERE login = %s", (novo_usuario,))
            if cursor.fetchone():
                flash("Erro: Este usuário já existe!", "error")
            else:
                hashed_password = bcrypt.hashpw(nova_senha.encode('utf-8'), bcrypt.gensalt(12)).decode('utf-8')
                cursor.execute("INSERT INTO usuarios (login, senha, status, role) VALUES (%s, %s, 'ativo', %s)", (novo_usuario, hashed_password, role))
                cursor.execute("INSERT INTO historico_logs (usuario, acao, detalhe) VALUES (%s, 'Admin', %s)", (session['usuario'], f"Criou o usuário '{novo_usuario}' com a função '{role}'"))
                mysql.connection.commit()
                flash(f"Usuário '{novo_usuario}' cadastrado com sucesso!", "success")
                
        elif action in ['suspender', 'reativar']:
            alvo = request.form['usuario_alvo']
            novo_status = 'suspenso' if action == 'suspender' else 'ativo'
            
            if alvo == 'admin':
                flash("Erro: O usuário master 'admin' não pode ser suspenso!", "error")
            else:
                cursor.execute("UPDATE usuarios SET status = %s WHERE login = %s", (novo_status, alvo))
                cursor.execute("INSERT INTO historico_logs (usuario, acao, detalhe) VALUES (%s, 'Admin', %s)", (session['usuario'], f"Alterou o status do usuário '{alvo}' para '{novo_status}'"))
                mysql.connection.commit()
                flash(f"Status do usuário '{alvo}' alterado para {novo_status}!", "success")
                
        elif action == 'alterar_chave':
            nova_chave = request.form['nova_chave'].strip()
            if nova_chave:
                hashed_chave = bcrypt.hashpw(nova_chave.encode('utf-8'), bcrypt.gensalt(12)).decode('utf-8')
                cursor.execute("UPDATE config_admin SET chave_secundaria = %s WHERE id = 1", (hashed_chave,))
                cursor.execute("INSERT INTO historico_logs (usuario, acao, detalhe) VALUES (%s, 'Admin', 'Alterou a chave mecânica secundária')", (session['usuario'],))
                mysql.connection.commit()
                flash("Chave mecânica secundária atualizada e criptografada com sucesso!", "success")
            
        return redirect(url_for('admin_panel'))
        
    cursor.execute("SELECT login, status, role FROM usuarios WHERE login != %s", (session['usuario'],))
    lista_usuarios = cursor.fetchall()
    
    cursor.execute("SELECT chave_secundaria FROM config_admin WHERE id = 1")
    reg_chave = cursor.fetchone()
    # Verifica apenas se a chave existe sem enviar a hash para o template HTML
    chave_configurada = bool(reg_chave and reg_chave.get('chave_secundaria'))
    
    cursor.execute("SELECT usuario, acao, detalhe, data_registro FROM historico_logs ORDER BY data_registro DESC LIMIT 100")
    lista_logs = cursor.fetchall()
    
    return render_template('admin.html', usuarios=lista_usuarios, logs=lista_logs, chave_configurada=chave_configurada)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)