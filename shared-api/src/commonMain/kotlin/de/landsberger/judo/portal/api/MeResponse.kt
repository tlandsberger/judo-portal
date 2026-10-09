package de.landsberger.judo.portal.api

import kotlinx.serialization.Serializable

/** Antwort von `GET /api/me`: der angemeldete Benutzer. */
@Serializable
data class MeResponse(
    /** Keycloak-User-ID (`sub` aus dem Token). */
    val subject: String,
    val displayName: String,
    val email: String? = null,
    val roles: Set<Role> = emptySet(),
)
