package de.landsberger.judo.portal.backend

import org.junit.jupiter.api.Test
import org.springframework.beans.factory.annotation.Value
import org.springframework.web.client.RestClient
import java.nio.file.Files
import java.nio.file.Path
import kotlin.test.assertEquals

/**
 * Hält den API-Vertrag `api/openapi.json` synchron mit dem Backend (ADR 0007).
 *
 * Schlägt der Test fehl, hat sich die API geändert: Änderung prüfen und den Vertrag mit
 * `./gradlew :backend:test --tests '*OpenApiContractIT' -Popenapi.update` neu schreiben.
 */
class OpenApiContractIT(
    @Value("\${local.server.port}") private val port: Int,
) : IntegrationTestBase() {
    @Test
    fun `api contract file matches the running backend`() {
        val actual =
            RestClient
                .create()
                .get()
                .uri("http://localhost:$port/v3/api-docs")
                .retrieve()
                .body(String::class.java)
                .orEmpty()
                .trimEnd() + "\n"
        val contractFile = Path.of(System.getProperty("judo.openapi-file"))

        if (System.getProperty("judo.openapi-update").toBoolean()) {
            Files.createDirectories(contractFile.parent)
            Files.writeString(contractFile, actual)
            return
        }
        val expected = if (Files.exists(contractFile)) Files.readString(contractFile) else ""
        assertEquals(
            expected,
            actual,
            "api/openapi.json ist veraltet – mit `./gradlew :backend:test -Popenapi.update` aktualisieren",
        )
    }
}
