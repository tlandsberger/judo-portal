package de.landsberger.judo.portal.backend

import org.springframework.boot.test.context.SpringBootTest
import org.springframework.test.context.DynamicPropertyRegistry
import org.springframework.test.context.DynamicPropertySource
import org.testcontainers.containers.GenericContainer
import org.testcontainers.containers.wait.strategy.Wait
import org.testcontainers.postgresql.PostgreSQLContainer
import org.testcontainers.utility.MountableFile
import java.time.Duration

/**
 * Basis für Ende-zu-Ende-Tests gegen echte Container: Postgres (Flyway läuft) und Keycloak mit dem
 * Dev-Realm aus infra/keycloak/realm-judo-dev.json. Die Container starten einmal pro Testlauf und
 * alle Unterklassen teilen sich denselben Spring-Kontext.
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
abstract class IntegrationTestBase {
    companion object {
        // Versionen synchron halten mit infra/compose.dev.yaml.
        private const val POSTGRES_IMAGE = "postgres:18.6"
        private const val KEYCLOAK_IMAGE = "keycloak/keycloak:26.8.0"

        val postgres: PostgreSQLContainer = PostgreSQLContainer(POSTGRES_IMAGE).apply { start() }

        val keycloak: GenericContainer<*> =
            GenericContainer(KEYCLOAK_IMAGE)
                .withCommand("start-dev", "--import-realm")
                .withEnv("KC_BOOTSTRAP_ADMIN_USERNAME", "admin")
                .withEnv("KC_BOOTSTRAP_ADMIN_PASSWORD", "admin")
                .withCopyFileToContainer(
                    MountableFile.forHostPath(System.getProperty("judo.realm-file")),
                    "/opt/keycloak/data/import/realm-judo-dev.json",
                ).withExposedPorts(8080)
                .waitingFor(Wait.forHttp("/realms/judo").forPort(8080).withStartupTimeout(Duration.ofMinutes(3)))
                .apply { start() }

        val keycloakUrl: String get() = "http://${keycloak.host}:${keycloak.getMappedPort(8080)}"

        @DynamicPropertySource
        @JvmStatic
        fun properties(registry: DynamicPropertyRegistry) {
            registry.add("spring.datasource.url", postgres::getJdbcUrl)
            registry.add("spring.datasource.username", postgres::getUsername)
            registry.add("spring.datasource.password", postgres::getPassword)
            registry.add("spring.security.oauth2.resourceserver.jwt.issuer-uri") { "$keycloakUrl/realms/judo" }
        }
    }
}
