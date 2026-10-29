package de.landsberger.judo.portal.backend.shared.security

import com.fasterxml.jackson.annotation.JsonIgnoreProperties
import com.fasterxml.jackson.annotation.JsonProperty
import de.landsberger.judo.portal.backend.shared.Account
import de.landsberger.judo.portal.backend.shared.AccountDirectory
import de.landsberger.judo.portal.backend.shared.ExternalServiceException
import de.landsberger.judo.portal.backend.shared.Role
import org.slf4j.LoggerFactory
import org.springframework.beans.factory.annotation.Value
import org.springframework.http.HttpMethod
import org.springframework.http.HttpStatus
import org.springframework.http.HttpStatusCode
import org.springframework.http.MediaType
import org.springframework.stereotype.Component
import org.springframework.util.LinkedMultiValueMap
import org.springframework.web.client.RestClient
import org.springframework.web.client.RestClientException
import org.springframework.web.client.body
import java.time.Clock
import java.time.Duration
import java.time.Instant

/**
 * [AccountDirectory] über die Keycloak-Admin-REST-API. Das Backend meldet sich als Service-Account des
 * vertraulichen Clients `judo-portal-backend` an (Client Credentials), der nur Benutzer verwalten darf (ADR 0009).
 */
@Component
internal class KeycloakAccountDirectory(
    @Value("\${portal.keycloak.url}") private val keycloakUrl: String,
    @Value("\${portal.keycloak.realm}") private val realm: String,
    @Value("\${portal.keycloak.client-id}") private val clientId: String,
    @Value("\${portal.keycloak.client-secret}") private val clientSecret: String,
    @Value("\${portal.public-url}") private val publicUrl: String,
    private val clock: Clock,
) : AccountDirectory {
    private val log = LoggerFactory.getLogger(javaClass)
    private val http = RestClient.create()
    private val admin get() = "$keycloakUrl/admin/realms/$realm"

    @Volatile
    private var token: CachedToken? = null

    override fun findByEmail(email: String): Account? =
        call("Konto suchen") {
            http
                .get()
                .uri("$admin/users?email={email}&exact=true", email)
                .headers { it.setBearerAuth(accessToken()) }
                .retrieve()
                .body<List<UserRepresentation>>()
                .orEmpty()
                .firstOrNull { it.email.equals(email, ignoreCase = true) }
                ?.toAccount()
        }

    override fun find(id: String): Account? =
        call("Konto lesen") {
            http
                .get()
                .uri("$admin/users/{id}", id)
                .headers { it.setBearerAuth(accessToken()) }
                .retrieve()
                .onStatus({ it.value() == HttpStatus.NOT_FOUND.value() }) { _, _ -> }
                .toEntity(UserRepresentation::class.java)
                .takeIf { it.statusCode.is2xxSuccessful }
                ?.body
                ?.toAccount()
        }

    override fun create(
        email: String,
        firstName: String,
        lastName: String,
    ): Account =
        call("Konto anlegen") {
            val user =
                mapOf(
                    "username" to email,
                    "email" to email,
                    "firstName" to firstName,
                    "lastName" to lastName,
                    "enabled" to true,
                    "emailVerified" to false,
                    // Einladungs- und Login-Seiten auf Deutsch.
                    "attributes" to mapOf("locale" to listOf("de")),
                )
            val location =
                http
                    .post()
                    .uri("$admin/users")
                    .headers { it.setBearerAuth(accessToken()) }
                    .contentType(MediaType.APPLICATION_JSON)
                    .body(user)
                    .retrieve()
                    .toBodilessEntity()
                    .headers.location ?: error("Keycloak hat keine User-ID geliefert")
            Account(location.path.substringAfterLast('/'), email, firstName, lastName, emailVerified = false)
        }

    override fun sendInvitation(id: String) =
        call("Einladungs-Mail senden") {
            http
                .put()
                .uri(
                    "$admin/users/{id}/execute-actions-email?client_id={client}&redirect_uri={redirect}&lifespan={lifespan}",
                    id,
                    PORTAL_CLIENT,
                    "${publicUrl.trimEnd('/')}/",
                    INVITATION_LIFESPAN.seconds,
                ).headers { it.setBearerAuth(accessToken()) }
                .contentType(MediaType.APPLICATION_JSON)
                .body(listOf("UPDATE_PASSWORD", "VERIFY_EMAIL"))
                .retrieve()
                .toBodilessEntity()
            Unit
        }

    override fun grantRole(
        id: String,
        role: Role,
    ) = changeRole(id, role, grant = true)

    override fun revokeRole(
        id: String,
        role: Role,
    ) = changeRole(id, role, grant = false)

    private fun changeRole(
        id: String,
        role: Role,
        grant: Boolean,
    ) = call(if (grant) "Rolle vergeben" else "Rolle entziehen") {
        val mappings = "$admin/users/{id}/role-mappings/realm"
        // Ohne Recht „view-realm“ liefert nur diese Liste die Rollen-IDs.
        val candidates = if (grant) "$mappings/available" else mappings
        val representation =
            http
                .get()
                .uri(candidates, id)
                .headers { it.setBearerAuth(accessToken()) }
                .retrieve()
                .body<List<RoleRepresentation>>()
                .orEmpty()
                .firstOrNull { it.name == role.keycloakName }
                ?: return@call
        val request = if (grant) http.post() else http.method(HttpMethod.DELETE)
        request
            .uri(mappings, id)
            .headers { it.setBearerAuth(accessToken()) }
            .contentType(MediaType.APPLICATION_JSON)
            .body(listOf(representation))
            .retrieve()
            .toBodilessEntity()
        Unit
    }

    /** Fehler von Keycloak werden als 502 mit deutscher Meldung weitergegeben; Details nur im Log. */
    private fun <T> call(
        action: String,
        block: () -> T,
    ): T =
        try {
            block()
        } catch (e: RestClientException) {
            log.warn("Keycloak: {} fehlgeschlagen: {}", action, e.message)
            throw ExternalServiceException("$action ist fehlgeschlagen. Bitte später erneut versuchen.")
        }

    private fun accessToken(): String {
        val now = Instant.now(clock)
        token?.takeIf { it.validUntil.isAfter(now) }?.let { return it.value }
        val form =
            LinkedMultiValueMap<String, String>().apply {
                add("grant_type", "client_credentials")
                add("client_id", clientId)
                add("client_secret", clientSecret)
            }
        val response =
            http
                .post()
                .uri("$keycloakUrl/realms/$realm/protocol/openid-connect/token")
                .contentType(MediaType.APPLICATION_FORM_URLENCODED)
                .body(form)
                .retrieve()
                .onStatus(HttpStatusCode::isError) { _, res ->
                    throw RestClientException("Token-Anfrage abgelehnt (${res.statusCode})")
                }.body<TokenResponse>() ?: throw RestClientException("Leere Token-Antwort")
        // Etwas früher erneuern, damit kein Aufruf mit gerade abgelaufenem Token startet.
        val cached = CachedToken(response.accessToken, now.plusSeconds(response.expiresIn - 30))
        token = cached
        return cached.value
    }

    private data class CachedToken(
        val value: String,
        val validUntil: Instant,
    )

    @JsonIgnoreProperties(ignoreUnknown = true)
    data class TokenResponse(
        @JsonProperty("access_token") val accessToken: String,
        @JsonProperty("expires_in") val expiresIn: Long,
    )

    @JsonIgnoreProperties(ignoreUnknown = true)
    data class UserRepresentation(
        val id: String,
        val email: String?,
        val firstName: String?,
        val lastName: String?,
        val emailVerified: Boolean = false,
    ) {
        fun toAccount() = Account(id, email.orEmpty(), firstName, lastName, emailVerified)
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    data class RoleRepresentation(
        val id: String,
        val name: String,
    )

    private companion object {
        const val PORTAL_CLIENT = "judo-portal-app"
        val INVITATION_LIFESPAN: Duration = Duration.ofDays(7)
    }
}
