CREATE TABLE meta (k TEXT, v TEXT);
INSERT INTO meta VALUES ('desc', 'item; com ponto e vírgula');
CREATE TRIGGER after_insert_items
AFTER INSERT ON items
BEGIN
    INSERT INTO meta VALUES ('last', CAST(new.id AS TEXT));
END;
