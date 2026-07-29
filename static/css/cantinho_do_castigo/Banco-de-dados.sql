CREATE DATABASE IF NOT EXISTS almoxarifado_db
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;

USE almoxarifado_db;

-- --------------------------------------------------------
-- Estrutura da Tabela: estoque
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS estoque (
    id_produto VARCHAR(5) NOT NULL,
    nome VARCHAR(100) NOT NULL,
    area VARCHAR(50) NOT NULL,
    quantidade INT NOT NULL DEFAULT 0,
    preco DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    descricao VARCHAR(255) NULL,
    link_midia VARCHAR(500) NULL,
    PRIMARY KEY (id_produto)
) ENGINE=InnoDB;

-- --------------------------------------------------------
-- Estrutura da Tabela: usuarios
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS usuarios (
    login VARCHAR(50) NOT NULL,
    senha VARCHAR(255) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'ativo',
    role VARCHAR(20) NOT NULL DEFAULT 'user',
    PRIMARY KEY (login)
) ENGINE=InnoDB;

-- --------------------------------------------------------
-- Estrutura da Tabela: config_admin
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS config_admin (
    id INT AUTO_INCREMENT,
    chave_secundaria VARCHAR(255) NOT NULL,
    PRIMARY KEY (id)
) ENGINE=InnoDB;

-- --------------------------------------------------------
-- Estrutura da Tabela: historico_logs
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS historico_logs (
    id INT AUTO_INCREMENT,
    usuario VARCHAR(50) NOT NULL,
    acao VARCHAR(50) NOT NULL,
    detalhe TEXT NOT NULL,
    data_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id)
) ENGINE=InnoDB;

-- --------------------------------------------------------
-- Inserções Iniciais: Configurações e Chaves
-- Hash Bcrypt gerado para a chave mecânica secundária padrão
-- --------------------------------------------------------

-- Antes era para fazer alterações como admin, mas não se usa mais
-- INSERT INTO config_admin (chave_secundaria) 
-- VALUES ('$2a$12$TyKbVE6G425lA7ko/IgwoOcR.Uc4RCbcvGj/ftZkopSNhhlelM8Zi'); #ROCAMBOLE

-- --------------------------------------------------------
-- Inserções Iniciais: Usuários Padrão (Senhas com Bcrypt)
-- --------------------------------------------------------
INSERT INTO usuarios (login, senha, status, role) VALUES 
('admin', '$2a$12$TyKbVE6G425lA7ko/IgwoOcR.Uc4RCbcvGj/ftZkopSNhhlelM8Zi', 'ativo', 'admin'), #admin
('andre', '$2a$12$iaj8/rlNnch3bV0WlT/BNO.nQrFOUgoJ7KvCgsLdaaO/hySJbDgSa', 'ativo', 'admin'), #123
('Juao Camara', '$2a$12$3IfgDTjfMRr7yQN1nrWC9.PaciUGyIv4tCZXQ3iZisGuSiurJu7.O', 'ativo', 'user'), #delicinhas
('Mateos', '$2a$12$BHll1yOD6XtedIS1RF4BkOa2tCspibhRKPGFgz.KD1kI3W1/ocFTm', 'ativo', 'user'), #delicinhas
('Lyan', '$2a$12$q8ZhuyPclUKt8AoF7vsSg.d2oYBiXMItNB9EMOuuj43kBbEHLeZ1S', 'ativo', 'user'); #delicinhas

-- --------------------------------------------------------
-- Inserções Iniciais: Estoque
-- --------------------------------------------------------
INSERT INTO estoque (id_produto, nome, area, quantidade, preco, descricao, link_midia) VALUES 
('00001', 'Alicate', 'Geral', 10, 20.00, 'Aperta umas coisa ai...', 'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcS66xbAeYwltYSUHqGq4qKWALJX3lkY1ojqbRLkKs82Yw&s=10'),
('10001', 'Pregos', 'Mecânica', 200, 12.00, 'Entra reto', 'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcSuleVPCTMLQEhf4lkkzlW9AEMXDfDEqw4RAwsZjdZ-jw&s=10'),
('10002', 'Parafusos', 'Mecânica', 200, 0.40, 'Entra rodando', 'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcSlm_v8Khvn-wORVgWlbuepAl0Urz62I7pJCK2UQ3-nnQ&s=10'),
('20001', 'Paineis fotovoltaicos', 'Elétrica', 2, 850.00, 'Deixa o wifi ligado', 'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcSMI9NnZ9OYWpmM1wtQ-M1_qA-3j2069zxWJkRJ1pBIew&s=10'),
('00002', 'Chave philips', 'Geral', 7, 10.00, 'Enfia na fenda de X', 'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcRMOMqwTSGR4S2soHpfyq7s5czjFTB6h6zBHHycqd2ZRg&s=10');

DROP DATABASE almoxarifado_db
