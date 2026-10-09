package de.landsberger.judo.portal.backend.shared.security

import de.landsberger.judo.portal.api.Role
import org.springframework.security.core.GrantedAuthority
import org.springframework.security.core.authority.SimpleGrantedAuthority
import org.springframework.security.oauth2.jwt.Jwt
import org.springframework.security.oauth2.server.resource.InvalidBearerTokenException

/** Liest Benutzer-ID und Portal-Rollen aus Keycloak-Tokens (Rollen aus `realm_access.roles`). */
internal object KeycloakRoles {
    /** Nur die festen Portal-Rollen; Keycloak-interne Rollen wie `offline_access` fallen weg. */
    fun from(jwt: Jwt): Set<Role> {
        val names =
            (jwt.getClaimAsMap("realm_access")?.get("roles") as? Collection<*>)
                ?.filterIsInstance<String>()
                ?.toSet()
                ?: return emptySet()
        return Role.entries.filter { it.keycloakName in names }.toSet()
    }

    /** Keycloak-User-ID; ein Token ohne `sub` ist für das Portal unbrauchbar und wird abgelehnt. */
    fun subject(jwt: Jwt): String = jwt.subject ?: throw InvalidBearerTokenException("Token enthält keinen 'sub'-Claim")

    fun authorities(jwt: Jwt): List<GrantedAuthority> = from(jwt).map { SimpleGrantedAuthority(it.authority) }

    /** Name der Realm-Rolle in Keycloak, entspricht dem `@SerialName` in `shared-api`. */
    private val Role.keycloakName: String get() = name.lowercase()

    /** Spring-Authority, z. B. `ROLE_TRAINER` – nutzbar mit `hasRole("TRAINER")`. */
    val Role.authority: String get() = "ROLE_$name"
}
