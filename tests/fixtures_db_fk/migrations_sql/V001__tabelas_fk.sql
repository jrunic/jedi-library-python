CREATE TABLE categorias (id INTEGER PRIMARY KEY, nome TEXT NOT NULL);
CREATE TABLE items_fk (id INTEGER PRIMARY KEY, categoria_id INTEGER NOT NULL REFERENCES categorias(id));
INSERT INTO items_fk (id, categoria_id) VALUES (1, 999);
