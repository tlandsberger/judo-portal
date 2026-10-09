package de.landsberger.judo.portal.backend.shared

import de.landsberger.judo.portal.api.Role
import de.landsberger.judo.portal.backend.shared.security.KeycloakRoles
import org.springframework.security.oauth2.jwt.Jwt

/**
 * Der angemeldete Benutzer, wie ihn die Fachmodule sehen.
 *
 * Controller bekommen ihn als Methodenparameter (`fun foo(user: CurrentUser)`), ohne Token-Details
 * zu kennen. Die Rollen sind bereits auf die festen Portal-Rollen gefiltert (ADR 0003).
 */
data class CurrentUser(
    /** Keycloak-User-ID (`sub`), stabil über Namens- und E-Mail-Änderungen hinweg. */
    val subject: String,
    val displayName: String,
    val email: String?,
    val roles: Set<Role>,
) {
    fun hasRole(role: Role): Boolean = role in roles

    companion object {
        fun from(jwt: Jwt): CurrentUser {
            val subject = KeycloakRoles.subject(jwt)
            return CurrentUser(
                subject = subject,
                displayName =
                    jwt.getClaimAsString("name")?.takeIf { it.isNotBlank() }
                        ?: jwt.getClaimAsString("preferred_username")
                        ?: subject,
                email = jwt.getClaimAsString("email"),
                roles = KeycloakRoles.from(jwt),
            )
        }
    }
}
