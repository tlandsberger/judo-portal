package de.landsberger.judo.portal.backend.members.internal.web

import de.landsberger.judo.portal.backend.shared.Role

/** Antwort von `GET /api/me`: der angemeldete Benutzer. */
data class MeResponse(
    /** Keycloak-User-ID (`sub` aus dem Token). */
    val subject: String,
    val displayName: String,
    val email: String?,
    val roles: Set<Role>,
)
