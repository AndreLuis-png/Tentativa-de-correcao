from flask import Blueprint, jsonify, request

# Criando o Blueprint da API
api_bp = Blueprint('api', __name__)

@api_bp.route('/api/produtos', methods=['GET'])
def listar_produtos():
    # Exemplo de dados estruturados para o Expo Go
    produtos = [
        {"id": 1, "nome": "Chave de Fenda", "quantidade": 15, "preco": 12.50},
        {"id": 2, "nome": "Martelo", "quantidade": 8, "preco": 35.00}
    ]
    return jsonify(produtos), 200