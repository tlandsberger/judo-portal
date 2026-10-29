-- Schritt 6c: Zugänge zum Portal. Ein Keycloak-Konto (account_id = sub) sieht ein Mitglied entweder selbst
-- (SELF, ab 14 Jahren) oder als erziehungsberechtigte Person (GUARDIAN, solange das Kind minderjährig ist).
CREATE TABLE member_access (
    id            UUID PRIMARY KEY,
    member_id     UUID         NOT NULL REFERENCES member (id) ON DELETE CASCADE,
    account_id    VARCHAR(64)  NOT NULL,
    relation      VARCHAR(10)  NOT NULL CHECK (relation IN ('SELF', 'GUARDIAN')),
    account_email VARCHAR(254) NOT NULL,
    account_name  VARCHAR(200) NOT NULL,
    created_at    TIMESTAMPTZ  NOT NULL,
    UNIQUE (member_id, account_id)
);

-- Je Mitglied höchstens ein eigener Zugang, und ein Konto ist höchstens für ein Mitglied „selbst“.
CREATE UNIQUE INDEX member_access_self_member_idx ON member_access (member_id) WHERE relation = 'SELF';
CREATE UNIQUE INDEX member_access_self_account_idx ON member_access (account_id) WHERE relation = 'SELF';
CREATE INDEX member_access_account_idx ON member_access (account_id);
