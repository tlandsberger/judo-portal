package de.landsberger.judo.portal.backend.shared

import com.fasterxml.jackson.annotation.JsonValue

/**
 * Feste Rollen im Portal, siehe docs/adr/0008-rollen-nach-vereinsfunktionen.md.
 * Im JSON und in Keycloak heißen sie wie [keycloakName], z. B. `"department_head"`.
 */
enum class Role {
    MEMBER,
    TRAINER,

    /** Abteilungsleiter der Judo-Abteilung. */
    DEPARTMENT_HEAD,

    /** Administrator (technisch): Konten, Rollen, Löschen von Fehleingaben. */
    ADMIN,
    ;

    /** Name der Realm-Rolle in Keycloak und Wert im JSON. */
    @get:JsonValue
    val keycloakName: String get() = name.lowercase()
}
