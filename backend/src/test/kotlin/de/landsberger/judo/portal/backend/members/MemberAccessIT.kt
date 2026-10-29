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
import java.time.LocalDate
import kotlin.test.assertEquals
import kotlin.test.assertNotNull
import kotlin.test.assertTrue

/**
 * Zugänge Ende-zu-Ende gegen echtes Keycloak und Mailpit: Einladung per Mail, Eltern sehen ihre Kinder,
 * eigener Zugang ab 14 mit Rolle `member`, Elternzugriff endet mit 18.
 */
class MemberAccessIT(
    @Value("\${local.server.port}") private val port: Int,
) : IntegrationTestBase() {
    private val http = RestClient.create()
    private val json = JsonMapper.builder().build()
    private val head by lazy { tokenFor("abteilungsleiter@test.local") }
    private val run = System.nanoTime()

    @Test
    fun `invite parents and teenagers, parents see their children until 18`() {
        val today = LocalDate.now()
        val child = createMember("Kind", today.minusYears(10))
        val teen = createMember("Teen", today.minusYears(15))
        val adult = createMember("Erwachsen", today.minusYears(40))
        val mother = "mutter-$run@example.org"

        // Elternteil einladen: Konto wird angelegt, Keycloak schickt die Einladung.
        val invited = invite(child, "guardian", mother, "Maria", "Muster")
        assertEquals(HttpStatus.CREATED, invited.statusCode)
        assertEquals(true, invited.json()["invitationSent"].asBoolean())
        assertEquals("invited", invited.json()["access"]["status"].asString())
        assertTrue("action-token" in waitForMail(mother), "Einladungslink fehlt")

        // Altersregeln.
        assertEquals("relation", invite(child, "self", "kind-$run@example.org").json()["errors"][0]["field"].asString())
        assertEquals(HttpStatus.BAD_REQUEST, invite(adult, "guardian", mother, "Maria", "Muster").statusCode)

        // Eigener Zugang ab 14 bekommt die Rolle member.
        val teenMail = "teen-$run@example.org"
        assertEquals(HttpStatus.CREATED, invite(teen, "self", teenMail).statusCode)
        assertEquals(HttpStatus.CONFLICT, invite(teen, "self", "zweiter-$run@example.org").statusCode)
        activate(teenMail)
        val teenToken = passwordToken("judo-dev-tools", teenMail)
        assertTrue(
            "member" in call(HttpMethod.GET, "/api/me", teenToken).json()["roles"].toList().map { it.asString() },
        )
        assertEquals(listOf("self"), myMembers(teenToken).map { it["relation"].asString() })

        // Nach dem Einladungslink ist die Mutter aktiv und sieht nur ihr Kind, schreibgeschützt.
        activate(mother)
        val motherToken = passwordToken("judo-dev-tools", mother)
        assertEquals(listOf(child), myMembers(motherToken).map { it["member"]["id"].asString() })
        assertEquals(HttpStatus.NOT_FOUND, call(HttpMethod.GET, "/api/me/members/$teen", motherToken).statusCode)
        assertEquals(HttpStatus.FORBIDDEN, call(HttpMethod.GET, "/api/members/$child", motherToken).statusCode)
        assertEquals("active", accesses(child).single()["status"].asString())

        // Bestehendes, aktives Konto wird nur verknüpft – keine neue Mail.
        val second = invite(teen, "guardian", mother, "Maria", "Muster")
        assertEquals(false, second.json()["invitationSent"].asBoolean())
        assertEquals(2, myMembers(motherToken).size)

        // Mit 18 endet der Elternzugriff automatisch.
        makeAdult(teen)
        assertEquals(listOf(child), myMembers(motherToken).map { it["member"]["id"].asString() })
        val guardianOfTeen = accesses(teen).single { it["relation"].asString() == "guardian" }
        assertEquals("expired", guardianOfTeen["status"].asString())

        // Eigenen Zugang entfernen: Rolle member ist weg (neues Token).
        val self = accesses(teen).single { it["relation"].asString() == "self" }["id"].asString()
        assertEquals(HttpStatus.NO_CONTENT, call(HttpMethod.DELETE, "/api/members/$teen/access/$self", head).statusCode)
        val newTeenToken = passwordToken("judo-dev-tools", teenMail)
        assertTrue(
            "member" !in call(HttpMethod.GET, "/api/me", newTeenToken).json()["roles"].toList().map { it.asString() },
        )
        assertTrue(myMembers(newTeenToken).isEmpty())
    }

    @Test
    fun `only department head and admin manage access`() {
        val child = createMember("Rechte", LocalDate.now().minusYears(8))
        assertEquals(
            HttpStatus.FORBIDDEN,
            call(HttpMethod.GET, "/api/members/$child/access", tokenFor("trainer@test.local")).statusCode,
        )
        assertEquals(
            HttpStatus.OK,
            call(HttpMethod.GET, "/api/members/$child/access", tokenFor("admin@test.local")).statusCode,
        )
        val byAdmin = invite(child, "guardian", "vater-$run@example.org", "Max", "Muster", tokenFor("admin@test.local"))
        assertEquals(HttpStatus.CREATED, byAdmin.statusCode)
    }

    private fun createMember(
        lastName: String,
        birthDate: LocalDate,
    ): String {
        val body =
            mapOf(
                "firstName" to "Test",
                "lastName" to lastName,
                "birthDate" to birthDate.toString(),
                "gender" to "diverse",
                "membershipType" to "active",
                "entryDate" to "2020-01-01",
            )
        return call(HttpMethod.POST, "/api/members", head, json.writeValueAsString(body)).json()["id"].asString()
    }

    private fun makeAdult(memberId: String) {
        val member = call(HttpMethod.GET, "/api/members/$memberId", head).json()
        val body =
            json.writeValueAsString(
                json.convertValue(member, Map::class.java).toMutableMap().apply {
                    put("birthDate", LocalDate.now().minusYears(18).toString())
                },
            )
        assertEquals(HttpStatus.OK, call(HttpMethod.PUT, "/api/members/$memberId", head, body).statusCode)
    }

    private fun invite(
        memberId: String,
        relation: String,
        email: String,
        firstName: String? = null,
        lastName: String? = null,
        token: String = head,
    ): ResponseEntity<String> {
        val body = mapOf("relation" to relation, "email" to email, "firstName" to firstName, "lastName" to lastName)
        return call(HttpMethod.POST, "/api/members/$memberId/access", token, json.writeValueAsString(body))
    }

    private fun accesses(memberId: String): List<JsonNode> =
        call(HttpMethod.GET, "/api/members/$memberId/access", head).json().toList()

    private fun myMembers(token: String): List<JsonNode> =
        call(HttpMethod.GET, "/api/me/members", token).json().toList()

    /** Simuliert den Klick auf den Einladungslink: E-Mail bestätigt, Passwort `test`. */
    private fun activate(email: String) {
        val adminToken = passwordToken("admin-cli", "admin", realm = "master")
        val users = "$keycloakUrl/admin/realms/judo/users"
        val id =
            json
                .readTree(
                    http
                        .get()
                        .uri("$users?email={email}&exact=true", email)
                        .headers { it.setBearerAuth(adminToken) }
                        .retrieve()
                        .body(String::class.java),
                )[0]["id"]
                .asString()
        http
            .put()
            .uri("$users/$id")
            .headers { it.setBearerAuth(adminToken) }
            .contentType(MediaType.APPLICATION_JSON)
            .body("""{"emailVerified":true,"requiredActions":[]}""")
            .retrieve()
            .toBodilessEntity()
        http
            .put()
            .uri("$users/$id/reset-password")
            .headers { it.setBearerAuth(adminToken) }
            .contentType(MediaType.APPLICATION_JSON)
            .body("""{"type":"password","value":"test","temporary":false}""")
            .retrieve()
            .toBodilessEntity()
    }

    /** Wartet auf die Einladungs-Mail in Mailpit und liefert ihren Text. */
    private fun waitForMail(to: String): String {
        repeat(20) {
            val found =
                json.readTree(
                    http
                        .get()
                        .uri("$mailpitUrl/api/v1/search?query={query}", "to:\"$to\"")
                        .retrieve()
                        .body(String::class.java),
                )["messages"]
            if (found != null && found.size() > 0) {
                val id = found[0]["ID"].asString()
                return json
                    .readTree(
                        http
                            .get()
                            .uri("$mailpitUrl/api/v1/message/$id")
                            .retrieve()
                            .body(String::class.java),
                    )["Text"]
                    .asString()
            }
            Thread.sleep(500)
        }
        error("Keine Mail an $to angekommen")
    }

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

    private fun ResponseEntity<String>.json(): JsonNode =
        json.readTree(assertNotNull(body, "Leere Antwort: $statusCode"))
}
