package de.landsberger.judo.portal.backend.members

import de.landsberger.judo.portal.backend.IntegrationTestBase
import org.junit.jupiter.api.Test
import org.springframework.beans.factory.annotation.Value
import org.springframework.core.io.ByteArrayResource
import org.springframework.http.HttpStatus
import org.springframework.http.HttpStatusCode
import org.springframework.http.MediaType
import org.springframework.http.ResponseEntity
import org.springframework.util.LinkedMultiValueMap
import org.springframework.web.client.RestClient
import org.springframework.web.client.toEntity
import tools.jackson.databind.JsonNode
import tools.jackson.databind.json.JsonMapper
import java.nio.charset.Charset
import kotlin.test.assertEquals
import kotlin.test.assertNotNull
import kotlin.test.assertTrue

/** CSV-Import Ende-zu-Ende: Vorschau, Import, Wiederholung und Aktualisierung gegen die echte Datenbank. */
class MembersImportIT(
    @Value("\${local.server.port}") private val port: Int,
) : IntegrationTestBase() {
    private val http = RestClient.create()
    private val json = JsonMapper.builder().build()
    private val head by lazy { tokenFor("abteilungsleiter@test.local") }

    private val header =
        "Mitgliedsnr;Anrede;Name;Vorname;Geburtsdatum;Telefon privat;E-Mail;Vereinseintritt;Vereinsaustritt"

    @Test
    fun `preview, import, repeat and update`() {
        val csv =
            """
            $header
            CSV-1;Frau;Ahrens;Lena;12.05.2013;040 123;lena@example.org;1.9.2019;
            CSV-2;;Becker;Jonas;3.2.2011;;;15.01.2018;31.12.2024
            CSV-3;Herr;Claussen;;31.02.2015;;keine-mail;01.03.2022;
            """.trimIndent()

        val preview = upload("/api/members/import/preview", csv).json()
        assertEquals(2, preview["created"].asInt())
        assertEquals(1, preview["failed"].asInt())
        val failed = preview["rows"][0]
        assertEquals("error", failed["action"].asString())
        assertEquals(4, failed["line"].asInt())
        val errors = failed["errors"].joinToString { it.asString() }
        assertTrue("Geburtsdatum „31.02.2015“" in errors, errors)
        assertTrue("Vorname" in errors && "E-Mail" in errors, errors)
        val becker = preview["rows"].first { it["memberNumber"].asString() == "CSV-2" }
        assertTrue(becker["notes"][0].asString().startsWith("Keine Anrede"))
        assertEquals(
            0,
            members().count { it["memberNumber"].asString().startsWith("CSV-") },
            "Vorschau speichert nichts",
        )

        val imported = upload("/api/members/import", csv).json()
        assertEquals(2, imported["created"].asInt())
        val lena = members().single { it["memberNumber"].asString() == "CSV-1" }
        assertEquals("female", lena["gender"].asString())
        assertEquals("2019-09-01", lena["entryDate"].asString())
        assertEquals("active", lena["membershipType"].asString())
        val jonas = members().single { it["memberNumber"].asString() == "CSV-2" }
        assertTrue(jonas["gender"].isNull)
        assertEquals(true, jonas["left"].asBoolean())

        val again = upload("/api/members/import/preview", csv).json()
        assertEquals(0, again["created"].asInt())
        assertEquals(2, again["unchanged"].asInt())

        // Telefon geleert, E-Mail geändert, Windows-1252 mit Komma als Trennzeichen.
        val changed =
            """
            ${header.replace(';', ',')}
            CSV-1,Frau,Ahrens,Lena,12.05.2013,,lena.ahrens@example.org,01.09.2019,
            """.trimIndent()
        val update = upload("/api/members/import", changed, Charset.forName("windows-1252")).json()
        assertEquals(1, update["updated"].asInt())
        val changes = update["rows"][0]["changes"].toList().map { it.asString() }
        assertEquals(listOf("Telefon", "E-Mail"), changes)
        val updated = members().single { it["memberNumber"].asString() == "CSV-1" }
        assertTrue(updated["phone"].isNull)
        assertEquals("lena.ahrens@example.org", updated["email"].asString())
    }

    @Test
    fun `duplicate numbers and missing columns are reported`() {
        val duplicates = "$header\nCSV-9;Herr;A;B;01.01.2000;;;01.01.2020;\nCSV-9;Herr;C;D;01.01.2000;;;01.01.2020;"
        val rows = upload("/api/members/import/preview", duplicates).json()["rows"]
        assertTrue(rows.all { it["action"].asString() == "error" })
        assertTrue("mehrfach" in rows[0]["errors"][0].asString())

        val missing = upload("/api/members/import/preview", "Mitgliedsnr;Name\n1;A")
        assertEquals(HttpStatus.BAD_REQUEST, missing.statusCode)
        assertTrue("Vorname" in missing.json()["detail"].asString())
    }

    @Test
    fun `files over 1 MB are rejected`() {
        val response = upload("/api/members/import/preview", "x".repeat(1_100_000))
        assertEquals(413, response.statusCode.value())
    }

    private fun upload(
        path: String,
        csv: String,
        charset: Charset = Charsets.UTF_8,
    ): ResponseEntity<String> {
        val file =
            object : ByteArrayResource(csv.toByteArray(charset)) {
                override fun getFilename() = "liste.csv"
            }
        val body = LinkedMultiValueMap<String, Any>().apply { add("file", file) }
        return http
            .post()
            .uri("http://localhost:$port$path")
            .headers { it.setBearerAuth(head) }
            .contentType(MediaType.MULTIPART_FORM_DATA)
            .body(body)
            .retrieve()
            .onStatus(HttpStatusCode::isError) { _, _ -> }
            .toEntity<String>()
    }

    private fun members(): List<JsonNode> =
        http
            .get()
            .uri("http://localhost:$port/api/members")
            .headers { it.setBearerAuth(head) }
            .retrieve()
            .toEntity<String>()
            .json()
            .toList()

    private fun ResponseEntity<String>.json(): JsonNode = json.readTree(assertNotNull(body))
}
