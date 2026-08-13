from flask import Blueprint, jsonify, request
import MySQLdb.cursors
import unicodedata

api_bp = Blueprint('api_bp', __name__, url_prefix='/api')

# ==========================================
# FUNÇÕES AUXILIARES DA API
# ==========================================

def get_mysql_connection():
    """Importação interna para obter a conexão de forma segura e sem ciclo circular."""
    from app import mysql
    return mysql.connection

def get_mysql_cursor():
    """Retorna um cursor configurado para dicionários de forma segura."""
    return get_mysql_connection().cursor(MySQLdb.cursors.DictCursor)

def limpar_texto(texto):
    if not texto:
        return ""
    nfkd_form = unicodedata.normalize('NFKD', texto)
    texto_sem_acento = "".join([c for c in nfkd_form if not unicodedata.combining(c)])
    return texto_sem_acento.strip().lower().capitalize()

def gerar_proximo_id(area):
    prefixos = {'Geral': '0', 'Mecânica': '1', 'Elétrica': '2'}
    prefixo = prefixos.get(area, '0')
    
    cursor = get_mysql_cursor()
    cursor.execute("SELECT id_produto FROM estoque WHERE id_produto LIKE %s", (prefixo + '%',))
    rows = cursor.fetchall()
    cursor.close()
    
    ids_existentes = []
    for row in rows:
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
# ROTAS ENDPOINTS DA API (RESTful)
# ==========================================

@api_bp.route('/produtos', methods=['GET'])
def listar_produtos():
    """
    GET /api/produtos
    Filtros opcionais via Query Params: ?area=Geral&pesquisa=alic
    """
    cursor = get_mysql_cursor()
    try:
        area = request.args.get('area')
        pesquisa = request.args.get('pesquisa', '').strip()

        query = "SELECT id_produto, nome, area, quantidade, preco, descricao, link_midia FROM estoque WHERE 1=1"
        params = []

        if area and area != 'Todos':
            query += " AND area = %s"
            params.append(area)

        if pesquisa:
            query += " AND (nome LIKE %s OR id_produto LIKE %s)"
            params.append(f'%{pesquisa}%')
            params.append(f'%{pesquisa}%')

        query += " ORDER BY id_produto ASC"
        cursor.execute(query, tuple(params))
        produtos = cursor.fetchall()

        return jsonify({'status': 'success', 'dados': produtos}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'mensagem': str(e)}), 500
    finally:
        cursor.close()


@api_bp.route('/produtos/<id_produto>', methods=['GET'])
def obter_produto(id_produto):
    """
    GET /api/produtos/00001
    Retorna os detalhes de um único produto pelo ID.
    """
    cursor = get_mysql_cursor()
    try:
        cursor.execute("SELECT * FROM estoque WHERE id_produto = %s", (id_produto,))
        produto = cursor.fetchone()

        if not produto:
            return jsonify({'status': 'error', 'mensagem': 'Produto não encontrado'}), 404

        return jsonify({'status': 'success', 'dados': produto}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'mensagem': str(e)}), 500
    finally:
        cursor.close()


@api_bp.route('/produtos', methods=['POST'])
def criar_produto():
    """
    POST /api/produtos
    Body (JSON):
    {
        "nome": "Chave Fenda",
        "area": "Geral",
        "quantidade": 15,
        "preco": 12.50,
        "descricao": "Ferramenta manual",
        "link_midia": "https://link.com/foto.jpg",
        "usuario": "admin"
    }
    """
    dados = request.get_json() or {}
    
    nome = limpar_texto(dados.get('nome'))
    area = dados.get('area', 'Geral')
    
    try:
        quantidade = int(dados.get('quantidade', 1))
    except (ValueError, TypeError):
        quantidade = 1

    try:
        preco = float(dados.get('preco', 0.0))
    except (ValueError, TypeError):
        preco = 0.0

    descricao = limpar_texto(dados.get('descricao', ''))
    link_midia = dados.get('link_midia')
    usuario_log = dados.get('usuario', 'API_User')

    if not nome:
        return jsonify({'status': 'error', 'mensagem': 'O campo nome é obrigatório.'}), 400

    cursor = get_mysql_cursor()
    conn = get_mysql_connection()

    try:
        # Verifica se já existe item igual
        cursor.execute("SELECT * FROM estoque WHERE nome = %s AND area = %s", (nome, area))
        produto_existente = cursor.fetchone()

        if produto_existente:
            nova_qtd = produto_existente['quantidade'] + quantidade
            id_final = produto_existente['id_produto']
            cursor.execute("UPDATE estoque SET quantidade = %s, preco = %s WHERE id_produto = %s", 
                           (nova_qtd, preco, id_final))
            acao_log = "Incremento via API"
        else:
            id_final = gerar_proximo_id(area)
            cursor.execute("""
                INSERT INTO estoque (id_produto, nome, area, quantidade, preco, descricao, link_midia)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (id_final, nome, area, quantidade, preco, descricao, link_midia))
            acao_log = "Inserção via API"

        # Registrar log no banco de dados
        cursor.execute("""
            INSERT INTO historico_logs (usuario, acao, detalhe)
            VALUES (%s, %s, %s)
        """, (usuario_log, acao_log, f"Produto: {nome} (ID: {id_final}), Qtd: {quantidade}"))

        conn.commit()
        return jsonify({
            'status': 'success',
            'mensagem': 'Operação realizada com sucesso!',
            'id_produto': id_final
        }), 201
    except Exception as e:
        conn.rollback()
        return jsonify({'status': 'error', 'mensagem': str(e)}), 500
    finally:
        cursor.close()


@api_bp.route('/produtos/<id_produto>/retirada', methods=['POST'])
def dar_baixa_produto(id_produto):
    """
    POST /api/produtos/00001/retirada
    Body (JSON):
    {
        "quantidade": 2,
        "usuario": "andre"
    }
    """
    dados = request.get_json() or {}
    
    try:
        quantidade_retirar = int(dados.get('quantidade', 1))
    except (ValueError, TypeError):
        quantidade_retirar = 1
        
    usuario_log = dados.get('usuario', 'API_User')

    cursor = get_mysql_cursor()
    conn = get_mysql_connection()

    try:
        cursor.execute("SELECT * FROM estoque WHERE id_produto = %s", (id_produto,))
        produto = cursor.fetchone()

        if not produto:
            return jsonify({'status': 'error', 'mensagem': 'Produto não encontrado.'}), 404

        if produto['quantidade'] < quantidade_retirar:
            return jsonify({'status': 'error', 'mensagem': 'Quantidade insuficiente em estoque.'}), 400

        nova_qtd = produto['quantidade'] - quantidade_retirar
        cursor.execute("UPDATE estoque SET quantidade = %s WHERE id_produto = %s", (nova_qtd, id_produto))

        cursor.execute("""
            INSERT INTO historico_logs (usuario, acao, detalhe)
            VALUES (%s, 'Retirada via API', %s)
        """, (usuario_log, f"Retirado {quantidade_retirar} un de {produto['nome']} (ID: {id_produto})"))

        conn.commit()
        return jsonify({
            'status': 'success', 
            'mensagem': 'Baixa efetuada com sucesso!',
            'quantidade_restante': nova_qtd
        }), 200
    except Exception as e:
        conn.rollback()
        return jsonify({'status': 'error', 'mensagem': str(e)}), 500
    finally:
        cursor.close()