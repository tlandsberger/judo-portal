package de.landsberger.judo.portal.backend

import org.junit.jupiter.api.Test
import org.springframework.beans.factory.annotation.Value
import org.springframework.http.HttpStatus
import org.springframework.http.HttpStatusCode
import org.springframework.http.MediaType
import org.springframework.util.LinkedMultiValueMap
import org.springframework.web.client.RestClient
import org.springframework.web.client.toEntity
import kotlin.test.assertEquals
import kotlin.test.assertTrue

/** Token-Validierung inkl. Audience und Rollen-Mapping gegen echtes Keycloak (ADR 0006). */
class ApiSecurityIT(
    @Value("\${local.server.port}") private val port: Int,
) : IntegrationTestBase() {
    private val http = RestClient.create()

    @Test
    fun `trainer gets own profile with roles`() {
        val response = callMe(passwordToken("judo-dev-tools", "trainer@test.local"))

        assertEquals(HttpStatus.OK, response.statusCode)
        val body = response.body.orEmpty()
        assertTrue(""""displayName":"Tom Trainer"""" in body, body)
        assertTrue(""""roles":["member","trainer"]""" in body, body)
    }

    @Test
    fun `request without token is rejected`() {
        assertEquals(HttpStatus.UNAUTHORIZED, callMe(token = null).statusCode)
    }

    @Test
    fun `token without portal audience is rejected`() {
        createClientWithoutAudience("judo-no-audience")

        val response = callMe(passwordToken("judo-no-audience", "trainer@test.local"))

        assertEquals(HttpStatus.UNAUTHORIZED, response.statusCode)
    }

    @Test
    fun `health endpoint is public`() {
        val response =
            http
                .get()
                .uri("http://localhost:$port/actuator/health")
                .retrieve()
                .toEntity<String>()
        assertEquals(HttpStatus.OK, response.statusCode)
    }

    private fun callMe(token: String?) =
        http
            .get()
            .uri("http://localhost:$port/api/me")
            .headers { if (token != null) it.setBearerAuth(token) }
            .retrieve()
            .onStatus(HttpStatusCode::isError) { _, _ -> }
            .toEntity<String>()

    private fun passwordToken(
        clientId: String,
        username: String,
        realm: String = "judo",
    ): String {
        val form =
            LinkedMultiValueMap<String, String>().apply {
                add("grant_type", "password")
                add("client_id", clientId)
                add("username", username)
                add("password", if (realm == "master") "admin" else "test")
            }
        val response =
            http
                .post()
                .uri("$keycloakUrl/realms/$realm/protocol/openid-connect/token")
                .contentType(MediaType.APPLICATION_FORM_URLENCODED)
                .body(form)
                .retrieve()
                .body(Map::class.java)
        return response?.get("access_token") as String
    }

    /** Legt per Admin-API einen Client ohne Audience-Mapper an (Token ist gültig, aber nicht für die API). */
    private fun createClientWithoutAudience(clientId: String) {
        val adminToken = passwordToken("admin-cli", "admin", realm = "master")
        http
            .post()
            .uri("$keycloakUrl/admin/realms/judo/clients")
            .headers { it.setBearerAuth(adminToken) }
            .contentType(MediaType.APPLICATION_JSON)
            .body(
                """{"clientId":"$clientId","publicClient":true,"directAccessGrantsEnabled":true,""" +
                    """"standardFlowEnabled":false}""",
            ).retrieve()
            .toBodilessEntity()
    }
}
