package de.landsberger.judo.portal.backend.members

import de.landsberger.judo.portal.backend.IntegrationTestBase
import org.junit.jupiter.api.Test
import org.springframework.beans.factory.annotation.Value
import org.springframework.http.HttpMethod
import org.springframework.http.HttpStatus
import org.springframework.http.HttpStatusCode
import org.springframework.http.MediaType
import org.springframework.http.ResponseEntity
import org.springframework.web.client.RestClient
import org.springframework.web.client.toEntity
import tools.jackson.databind.JsonNode
import tools.jackson.databind.json.JsonMapper
import kotlin.test.assertEquals
import kotlin.test.assertNotNull
import kotlin.test.assertTrue

/** Mitgliederverwaltung Ende-zu-Ende: echte Tokens, echte Datenbank mit Flyway-Schema. */
class MembersIT(
    @Value("\${local.server.port}") private val port: Int,
) : IntegrationTestBase() {
    private val http = RestClient.create()
    private val json = JsonMapper.builder().build()
    private val board by lazy { tokenFor("vorstand@test.local") }

    @Test
    fun `board creates, reads, updates and admin deletes a member`() {
        val created = call(HttpMethod.POST, "/api/members", board, memberJson(number = "IT-1"))
        assertEquals(HttpStatus.CREATED, created.statusCode)
        val member = created.json()
        val id = member["id"].asString()
        assertTrue(
            created.headers.location
                .toString()
                .endsWith("/api/members/$id"),
        )
        assertEquals("Erika", member["firstName"].asString())
        assertEquals("female", member["gender"].asString())
        assertEquals(false, member["left"].asBoolean())

        val list = call(HttpMethod.GET, "/api/members", tokenFor("kasse@test.local"))
        assertEquals(HttpStatus.OK, list.statusCode)
        assertTrue(list.json().any { it["id"].asString() == id })

        val version = member["version"].asLong()
        val updated =
            call(
                HttpMethod.PUT,
                "/api/members/$id",
                board,
                memberJson(number = "IT-1", version = version, city = "Wedel", exitDate = "2020-12-31"),
            )
        assertEquals(HttpStatus.OK, updated.statusCode)
        assertEquals("Wedel", updated.json()["city"].asString())
        assertEquals(true, updated.json()["left"].asBoolean())
        assertEquals(version + 1, updated.json()["version"].asLong())

        // Zweiter Bearbeiter mit veraltetem Stand.
        val stale = call(HttpMethod.PUT, "/api/members/$id", board, memberJson(number = "IT-1", version = version))
        assertEquals(HttpStatus.CONFLICT, stale.statusCode)

        assertEquals(HttpStatus.FORBIDDEN, call(HttpMethod.DELETE, "/api/members/$id", board).statusCode)
        val admin = tokenFor("admin@test.local")
        assertEquals(HttpStatus.NO_CONTENT, call(HttpMethod.DELETE, "/api/members/$id", admin).statusCode)
        assertEquals(HttpStatus.NOT_FOUND, call(HttpMethod.GET, "/api/members/$id", admin).statusCode)
    }

    @Test
    fun `duplicate member number and exit before entry are rejected with field errors`() {
        assertEquals(
            HttpStatus.CREATED,
            call(HttpMethod.POST, "/api/members", board, memberJson(number = "IT-2")).statusCode,
        )

        val duplicate = call(HttpMethod.POST, "/api/members", board, memberJson(number = "IT-2"))
        assertEquals(HttpStatus.CONFLICT, duplicate.statusCode)
        assertEquals("memberNumber", duplicate.json()["errors"][0]["field"].asString())

        val exitBeforeEntry =
            call(HttpMethod.POST, "/api/members", board, memberJson(number = "IT-3", exitDate = "2000-01-01"))
        assertEquals(HttpStatus.BAD_REQUEST, exitBeforeEntry.statusCode)
        assertEquals("exitDate", exitBeforeEntry.json()["errors"][0]["field"].asString())
    }

    @Test
    fun `members are hidden from trainers and members`() {
        for (user in listOf("trainer@test.local", "mitglied@test.local")) {
            assertEquals(HttpStatus.FORBIDDEN, call(HttpMethod.GET, "/api/members", tokenFor(user)).statusCode)
        }
    }

    private fun memberJson(
        number: String,
        version: Long? = null,
        city: String? = null,
        exitDate: String? = null,
    ) = json.writeValueAsString(
        mapOf(
            "version" to version,
            "memberNumber" to number,
            "firstName" to "Erika",
            "lastName" to "Muster",
            "birthDate" to "2012-03-04",
            "gender" to "female",
            "city" to city,
            "email" to "erika@example.org",
            "membershipType" to "active",
            "entryDate" to "2019-08-01",
            "exitDate" to exitDate,
        ),
    )

    private fun call(
        method: HttpMethod,
        path: String,
        token: String,
        body: String? = null,
    ): ResponseEntity<String> =
        http
            .method(method)
            .uri("http://localhost:$port$path")
            .headers { it.setBearerAuth(token) }
            .apply { if (body != null) contentType(MediaType.APPLICATION_JSON).body(body) }
            .retrieve()
            .onStatus(HttpStatusCode::isError) { _, _ -> }
            .toEntity<String>()

    private fun ResponseEntity<String>.json(): JsonNode = json.readTree(assertNotNull(body))
}
