-- Mitglieder-Stammdaten (Schritt 6a). Bewusst ohne Bankdaten und Graduierungen
-- (Graduierungen liegen im DJB-Portal Doku-Me).
CREATE TABLE member (
    id              UUID PRIMARY KEY,
    member_number   VARCHAR(20) UNIQUE,
    first_name      VARCHAR(100) NOT NULL,
    last_name       VARCHAR(100) NOT NULL,
    birth_date      DATE         NOT NULL,
    gender          VARCHAR(10)  NOT NULL CHECK (gender IN ('FEMALE', 'MALE', 'DIVERSE')),
    street          VARCHAR(200),
    postal_code     VARCHAR(10),
    city            VARCHAR(100),
    phone           VARCHAR(50),
    email           VARCHAR(254),
    membership_type VARCHAR(10)  NOT NULL CHECK (membership_type IN ('ACTIVE', 'PASSIVE')),
    entry_date      DATE         NOT NULL,
    -- Ausgetreten ist, wessen Austrittsdatum in der Vergangenheit liegt (kein eigener Status).
    exit_date       DATE CHECK (exit_date IS NULL OR exit_date >= entry_date),
    version         BIGINT       NOT NULL,
    created_at      TIMESTAMPTZ  NOT NULL,
    updated_at      TIMESTAMPTZ  NOT NULL
);

CREATE INDEX member_name_idx ON member (last_name, first_name);
