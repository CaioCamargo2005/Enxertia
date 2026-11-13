-- Enxert.DB -- pode ser executado varias vezes (INSERT OR IGNORE / IF NOT EXISTS).
-- Sem BEGIN/COMMIT: quem executa o script controla a transacao.

-- Fontes: referencia de cada registro de compatibilidade vindo da literatura.
-- Registros da equipe ficam com id_fonte NULL.
CREATE TABLE IF NOT EXISTS Fontes (
    id_fonte INTEGER PRIMARY KEY,
    referencia TEXT NOT NULL,
    url TEXT
);

CREATE TABLE IF NOT EXISTS Plantas (
    id_planta INTEGER PRIMARY KEY AUTOINCREMENT,
    nome_comum TEXT NOT NULL,
    nome_cientifico TEXT NOT NULL UNIQUE,
    ncbi_taxid INTEGER,
    familia TEXT NOT NULL,
    genero TEXT NOT NULL,
    papel_agronomico TEXT CHECK(papel_agronomico IN ('Enxerto', 'Porta-Enxerto', 'Ambos'))
);

CREATE TABLE IF NOT EXISTS Metodos_Enxertia (
    id_metodo INTEGER PRIMARY KEY AUTOINCREMENT,
    nome_metodo TEXT NOT NULL,
    descricao TEXT,
    tempo_cicatrizacao_dias INTEGER
);

CREATE TABLE IF NOT EXISTS Compatibilidade (
    id_compatibilidade INTEGER PRIMARY KEY AUTOINCREMENT,
    id_copa INTEGER NOT NULL,
    id_porta_enxerto INTEGER NOT NULL,
    status_compatibilidade TEXT CHECK(status_compatibilidade IN ('Compatível', 'Incompatibilidade Localizada', 'Incompatibilidade Translocada', 'Incompatível')),
    taxa_pegamento_pct REAL,
    id_metodo INTEGER,
    observacoes TEXT,
    id_fonte INTEGER,
    trecho TEXT,
    conferido INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY(id_copa) REFERENCES Plantas(id_planta),
    FOREIGN KEY(id_porta_enxerto) REFERENCES Plantas(id_planta),
    FOREIGN KEY(id_metodo) REFERENCES Metodos_Enxertia(id_metodo),
    FOREIGN KEY(id_fonte) REFERENCES Fontes(id_fonte)
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_compatibilidade_par
    ON Compatibilidade(id_copa, id_porta_enxerto, COALESCE(id_metodo, 0));

CREATE TABLE IF NOT EXISTS Biomarcadores (
    id_biomarcador INTEGER PRIMARY KEY AUTOINCREMENT,
    id_planta INTEGER NOT NULL,
    atividade_peroxidase TEXT,
    concentracao_fenois TEXT,
    presenca_prunasina BOOLEAN,
    acoplamento_plasmodesmal TEXT,
    FOREIGN KEY(id_planta) REFERENCES Plantas(id_planta)
);

CREATE TABLE IF NOT EXISTS Atributos_Resistencia (
    id_atributo INTEGER PRIMARY KEY AUTOINCREMENT,
    id_porta_enxerto INTEGER NOT NULL,
    resistencia_patogenos_solo TEXT,
    resistencia_doencas_parte_aerea TEXT,
    tolerancia_estresse_abiotico TEXT,
    efeito_porte_vigor TEXT,
    FOREIGN KEY(id_porta_enxerto) REFERENCES Plantas(id_planta)
);

-- ATENCAO: ncbi_taxid das linhas 4, 8 e 11 (hibridos) e das linhas 2, 3, 7 e 9
-- nao foi conferido contra o NCBI -- revisar antes de usar em apresentacao.
-- Inserções Plantas
INSERT OR IGNORE INTO "Plantas" VALUES(1,'Tomateiro Janaína','Solanum lycopersicum',4081,'Solanaceae','Solanum','Enxerto');
INSERT OR IGNORE INTO "Plantas" VALUES(2,'Jurubeba','Solanum paniculatum',4102,'Solanaceae','Solanum','Porta-Enxerto');
INSERT OR IGNORE INTO "Plantas" VALUES(3,'Joá','Solanum aculeatissimum',110275,'Solanaceae','Solanum','Porta-Enxerto');
INSERT OR IGNORE INTO "Plantas" VALUES(4,'Porta-Enxerto Castelpro','Solanum lycopersicum x S. habrochaites (Castelpro)',4081,'Solanaceae','Solanum','Porta-Enxerto');
INSERT OR IGNORE INTO "Plantas" VALUES(5,'Porta-Enxerto 15PEX00056','Solanum lycopersicum (15PEX00056)',4081,'Solanaceae','Solanum','Porta-Enxerto');
INSERT OR IGNORE INTO "Plantas" VALUES(6,'Laranjeira Pera D6','Citrus sinensis (Pera D6)',2711,'Rutaceae','Citrus','Enxerto');
INSERT OR IGNORE INTO "Plantas" VALUES(7,'Tangerineira Sunki Tropical','Citrus sunki',555021,'Rutaceae','Citrus','Porta-Enxerto');
INSERT OR IGNORE INTO "Plantas" VALUES(8,'Citrandarin San Diego','Citrus sunki x Poncirus trifoliata',2711,'Rutaceae','Citrus','Porta-Enxerto');
INSERT OR IGNORE INTO "Plantas" VALUES(9,'Limoeiro Cravo','Citrus limonia',170929,'Rutaceae','Citrus','Porta-Enxerto');
INSERT OR IGNORE INTO "Plantas" VALUES(10,'Pessegueiro Santa Rosa / Diamante','Prunus persica',3760,'Rosaceae','Prunus','Ambos');
INSERT OR IGNORE INTO "Plantas" VALUES(11,'Ameixeira Marianna','Prunus marianna',3760,'Rosaceae','Prunus','Porta-Enxerto');
INSERT OR IGNORE INTO "Plantas" VALUES(12,'Ameixeira Mirabolano','Prunus cerasifera',3765,'Rosaceae','Prunus','Porta-Enxerto');
INSERT OR IGNORE INTO "Plantas" VALUES(13,'Pessegueiro Okinawa','Prunus persica (Okinawa)',3760,'Rosaceae','Prunus','Porta-Enxerto');
INSERT OR IGNORE INTO "Plantas" VALUES(14,'Pessegueiro Capdeboscq','Prunus persica (Capdeboscq)',3760,'Rosaceae','Prunus','Porta-Enxerto');
INSERT OR IGNORE INTO "Plantas" VALUES(15,'Melancia','Citrullus lanatus',3654,'Cucurbitaceae','Citrullus','Enxerto');
INSERT OR IGNORE INTO "Plantas" VALUES(16,'Abóbora / Porongo','Cucurbita maxima',3661,'Cucurbitaceae','Cucurbita','Porta-Enxerto');

-- Inserções Métodos
INSERT OR IGNORE INTO "Metodos_Enxertia" VALUES(1,'Garfagem de Topo / Fenda-Cheia','União por fenda no porta-enxerto com garfo cortado em cunha no enxerto.',14);
INSERT OR IGNORE INTO "Metodos_Enxertia" VALUES(2,'Borbulhia T-Invertido','Inserção de uma gema vegetativa sob a casca cortada em forma de T invertido no porta-enxerto.',12);
INSERT OR IGNORE INTO "Metodos_Enxertia" VALUES(3,'Enxertia por Aproximação','União física dos caules mantendo ambas as plantas com raízes até a cicatrização.',15);
INSERT OR IGNORE INTO "Metodos_Enxertia" VALUES(4,'Perfuração Apical','Remoção do meristema do porta-enxerto e inserção do hipocótilo perfurado do enxerto.',10);

-- Inserções Compatibilidade
INSERT OR IGNORE INTO "Compatibilidade" (id_compatibilidade, id_copa, id_porta_enxerto, status_compatibilidade, taxa_pegamento_pct, id_metodo, observacoes) VALUES(1,1,5,'Compatível',100.0,1,'Excelente pegamento, aumento significativo na massa média dos frutos e produtividade total.');
INSERT OR IGNORE INTO "Compatibilidade" (id_compatibilidade, id_copa, id_porta_enxerto, status_compatibilidade, taxa_pegamento_pct, id_metodo, observacoes) VALUES(2,1,4,'Compatível',95.8,1,'Ótimo equilíbrio vegetativo/produtivo e alta compatibilidade cambial.');
INSERT OR IGNORE INTO "Compatibilidade" (id_compatibilidade, id_copa, id_porta_enxerto, status_compatibilidade, taxa_pegamento_pct, id_metodo, observacoes) VALUES(3,1,2,'Compatível',94.1,1,'Alta taxa de sobrevivência, útil contra Ralstonia solanacearum, porém reduz ligeiramente diâmetro/massa de frutos.');
INSERT OR IGNORE INTO "Compatibilidade" (id_compatibilidade, id_copa, id_porta_enxerto, status_compatibilidade, taxa_pegamento_pct, id_metodo, observacoes) VALUES(4,1,3,'Compatível',96.6,1,'Boa taxa de pegamento, mas inibe enchimento de frutos e reduz produtividade comercial.');
INSERT OR IGNORE INTO "Compatibilidade" (id_compatibilidade, id_copa, id_porta_enxerto, status_compatibilidade, taxa_pegamento_pct, id_metodo, observacoes) VALUES(5,6,7,'Compatível',100.0,2,'Superior desenvolvimento inicial, maior número de folhas e altura da muda.');
INSERT OR IGNORE INTO "Compatibilidade" (id_compatibilidade, id_copa, id_porta_enxerto, status_compatibilidade, taxa_pegamento_pct, id_metodo, observacoes) VALUES(6,6,8,'Compatível',95.0,2,'Bom desenvolvimento vegetativo inicial e vigor equilibrado.');
INSERT OR IGNORE INTO "Compatibilidade" (id_compatibilidade, id_copa, id_porta_enxerto, status_compatibilidade, taxa_pegamento_pct, id_metodo, observacoes) VALUES(7,10,13,'Compatível',90.0,1,'Evolução cambial harmônica, níveis similares de peroxidase entre copa e cavalo.');
INSERT OR IGNORE INTO "Compatibilidade" (id_compatibilidade, id_copa, id_porta_enxerto, status_compatibilidade, taxa_pegamento_pct, id_metodo, observacoes) VALUES(8,10,11,'Incompatibilidade Translocada',0.0,1,'Incompatibilidade severa por translocação de compostos e alta atividade de peroxidase/fenóis.');
INSERT OR IGNORE INTO "Compatibilidade" (id_compatibilidade, id_copa, id_porta_enxerto, status_compatibilidade, taxa_pegamento_pct, id_metodo, observacoes) VALUES(9,10,12,'Incompatibilidade Translocada',0.0,1,'Falha de brotação dos enxertos decorrente do estresse oxidativo e acúmulo fenólico.');
INSERT OR IGNORE INTO "Compatibilidade" (id_compatibilidade, id_copa, id_porta_enxerto, status_compatibilidade, taxa_pegamento_pct, id_metodo, observacoes) VALUES(10,15,16,'Compatível',98.0,4,'Excelente resistência a Fusarium de solo, baixa temperatura e excesso de umidade.');

-- Inserções Biomarcadores
INSERT OR IGNORE INTO "Biomarcadores" VALUES(1,10,'Média / Balanceada','Normal / Estável',0,'Funcional');
INSERT OR IGNORE INTO "Biomarcadores" VALUES(2,11,'Elevada','Muito Alta',1,'Deficiente / Não funcional');
INSERT OR IGNORE INTO "Biomarcadores" VALUES(3,12,'Elevada','Muito Alta',1,'Deficiente / Não funcional');
INSERT OR IGNORE INTO "Biomarcadores" VALUES(4,13,'Parecida com enxerto','Equilibrada',0,'Funcional');

-- Inserções Resistências
INSERT OR IGNORE INTO "Atributos_Resistencia" VALUES(1,2,'Resistente a Ralstonia solanacearum e fungos de solo','N/A','Resistente à seca','Vigoroso / Rústico');
INSERT OR IGNORE INTO "Atributos_Resistencia" VALUES(2,5,'Resistente a murcha bacteriana e Fusarium','N/A','Alta eficiência hídrica','Equilibrado / Produtivo');
INSERT OR IGNORE INTO "Atributos_Resistencia" VALUES(3,7,'Resistente a Phytophthora citrophthora (Gomose)','Memória de defesa (Priming)','Tolerante à seca','Vigoroso');
INSERT OR IGNORE INTO "Atributos_Resistencia" VALUES(4,9,'Sensível à gomose em solos úmidos','N/A','Tolerante à seca','Vigoroso');
INSERT OR IGNORE INTO "Atributos_Resistencia" VALUES(5,13,'Resistente aos nematoides Meloidogyne incognita e M. javanica','N/A','Adequada ancoragem radicular','Vigoroso');
INSERT OR IGNORE INTO "Atributos_Resistencia" VALUES(6,16,'Resistente à fusariose e patógenos de solo','N/A','Resistente ao excesso de umidade e frio','Ananicante a Médio');

