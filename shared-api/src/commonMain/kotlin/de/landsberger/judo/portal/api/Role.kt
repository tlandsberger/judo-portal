package de.landsberger.judo.portal.api

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/**
 * Feste Rollen im Portal, siehe docs/adr/0003-keycloak-identity.md.
 * Die [SerialName]s entsprechen den Realm-Rollen in Keycloak.
 */
@Serializable
enum class Role {
    @SerialName("member")
    MEMBER,

    @SerialName("trainer")
    TRAINER,

    @SerialName("board")
    BOARD,

    @SerialName("treasurer")
    TREASURER,

    @SerialName("admin")
    ADMIN,
}
