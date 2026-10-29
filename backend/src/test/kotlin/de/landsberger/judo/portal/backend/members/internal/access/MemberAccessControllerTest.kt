package de.landsberger.judo.portal.backend.members.internal.access

import de.landsberger.judo.portal.backend.shared.security.CurrentUserWebConfig
import de.landsberger.judo.portal.backend.shared.security.SecurityConfig
import org.junit.jupiter.api.Test
import org.springframework.beans.factory.annotation.Autowired
import org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest
import org.springframework.context.annotation.Import
import org.springframework.http.MediaType
import org.springframework.security.core.authority.SimpleGrantedAuthority
import org.springframework.security.oauth2.jwt.JwtDecoder
import org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.jwt
import org.springframework.test.context.bean.override.mockito.MockitoBean
import org.springframework.test.web.servlet.MockMvc
import org.springframework.test.web.servlet.get
import org.springframework.test.web.servlet.post
import java.util.UUID

/** Rollen und Eingabeprüfung; der Ablauf mit Keycloak steht in `MemberAccessIT`. */
@WebMvcTest(MemberAccessController::class, MyMembersController::class)
@Import(SecurityConfig::class, CurrentUserWebConfig::class, de.landsberger.judo.portal.backend.shared.TimeConfig::class)
class MemberAccessControllerTest(
    @Autowired private val mockMvc: MockMvc,
) {
    @MockitoBean
    private lateinit var jwtDecoder: JwtDecoder

    @MockitoBean
    private lateinit var accessService: MemberAccessService

    private val path = "/api/members/${UUID.randomUUID()}/access"

    private fun user(vararg roles: String) =
        jwt()
            .jwt { it.subject("user-1") }
            .authorities(roles.map { SimpleGrantedAuthority("ROLE_$it") })

    @Test
    fun `department head and admin may manage access`() {
        for (role in listOf("DEPARTMENT_HEAD", "ADMIN")) {
            mockMvc.get(path) { with(user(role)) }.andExpect { status { isOk() } }
        }
    }

    @Test
    fun `members, trainers and parents may not`() {
        for (roles in listOf(arrayOf("MEMBER", "TRAINER"), arrayOf())) {
            mockMvc.get(path) { with(user(*roles)) }.andExpect { status { isForbidden() } }
        }
    }

    @Test
    fun `invitation needs a valid email`() {
        mockMvc
            .post(path) {
                with(user("DEPARTMENT_HEAD"))
                contentType = MediaType.APPLICATION_JSON
                content = """{"relation":"guardian","email":"keine-mail","firstName":"A","lastName":"B"}"""
            }.andExpect {
                status { isBadRequest() }
                jsonPath("$.errors[0].field") { value("email") }
            }
    }

    @Test
    fun `everyone signed in may ask for their own members`() {
        mockMvc.get("/api/me/members") { with(user()) }.andExpect {
            status { isOk() }
            content { json("[]") }
        }
    }
}
