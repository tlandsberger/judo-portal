package de.landsberger.judo.portal.backend.members.internal.web

import de.landsberger.judo.portal.backend.shared.security.CurrentUserWebConfig
import de.landsberger.judo.portal.backend.shared.security.SecurityConfig
import org.junit.jupiter.api.Test
import org.springframework.beans.factory.annotation.Autowired
import org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest
import org.springframework.context.annotation.Import
import org.springframework.security.oauth2.jwt.JwtDecoder
import org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.jwt
import org.springframework.test.context.bean.override.mockito.MockitoBean
import org.springframework.test.web.servlet.MockMvc
import org.springframework.test.web.servlet.get

@WebMvcTest(MeController::class)
@Import(SecurityConfig::class, CurrentUserWebConfig::class)
class MeControllerTest(
    @Autowired private val mockMvc: MockMvc,
) {
    @MockitoBean
    private lateinit var jwtDecoder: JwtDecoder

    @Test
    fun `without token the request is rejected`() {
        mockMvc.get("/api/me").andExpect {
            status { isUnauthorized() }
            header { exists("WWW-Authenticate") }
        }
    }

    @Test
    fun `returns the current user with portal roles`() {
        mockMvc
            .get("/api/me") {
                with(
                    jwt().jwt {
                        it
                            .subject("user-42")
                            .claim("name", "Tom Trainer")
                            .claim("email", "trainer@test.local")
                            .claim("realm_access", mapOf("roles" to listOf("trainer", "member", "offline_access")))
                    },
                )
            }.andExpect {
                status { isOk() }
                content {
                    // Rollen als Keycloak-Namen (@JsonValue), Keycloak-interne Rollen herausgefiltert.
                    json(
                        """
                        {"subject":"user-42","displayName":"Tom Trainer","email":"trainer@test.local",
                         "roles":["member","trainer"]}
                        """,
                        strict = true,
                    )
                }
            }
    }

    @Test
    fun `falls back to preferred_username and tolerates missing roles`() {
        mockMvc
            .get("/api/me") {
                with(jwt().jwt { it.subject("user-7").claim("preferred_username", "mitglied@test.local") })
            }.andExpect {
                status { isOk() }
                content {
                    json(
                        """{"subject":"user-7","displayName":"mitglied@test.local","email":null,"roles":[]}""",
                        strict = true,
                    )
                }
            }
    }
}
