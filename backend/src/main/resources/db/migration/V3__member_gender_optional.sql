-- Schritt 6b: Beim Import aus der bisherigen Excel-Liste ist das Geschlecht nur über die Anrede bekannt.
-- Fehlt sie oder ist sie nicht eindeutig, bleibt das Geschlecht leer und wird im Portal nachgetragen.
ALTER TABLE member ALTER COLUMN gender DROP NOT NULL;
