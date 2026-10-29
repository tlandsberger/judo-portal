package de.landsberger.judo.portal.backend.shared

import com.fasterxml.jackson.annotation.JsonValue

/**
 * Feste Rollen im Portal, siehe docs/adr/0003-keycloak-identity.md.
 * Im JSON und in Keycloak heißen sie wie [keycloakName], z. B. `"trainer"`.
 */
enum class Role {
    MEMBER,
    TRAINER,
    BOARD,
    TREASURER,
    ADMIN,
    ;

    /** Name der Realm-Rolle in Keycloak und Wert im JSON. */
    @get:JsonValue
    val keycloakName: String get() = name.lowercase()
}
