package de.landsberger.judo.portal.backend.members.internal.web

import de.landsberger.judo.portal.backend.members.internal.domain.MemberService
import de.landsberger.judo.portal.backend.shared.TimeConfig
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
import org.springframework.test.web.servlet.delete
import org.springframework.test.web.servlet.get
import org.springframework.test.web.servlet.post
import org.springframework.test.web.servlet.put
import java.util.UUID

/** Rollenmatrix und Eingabeprüfung; der Ablauf mit echter Datenbank steht in `MembersIT`. */
@WebMvcTest(MemberController::class)
@Import(SecurityConfig::class, CurrentUserWebConfig::class, TimeConfig::class)
class MemberControllerTest(
    @Autowired private val mockMvc: MockMvc,
) {
    @MockitoBean
    private lateinit var jwtDecoder: JwtDecoder

    @MockitoBean
    private lateinit var memberService: MemberService

    private fun user(vararg roles: String) =
        jwt()
            .jwt { it.subject("user-1") }
            .authorities(roles.map { SimpleGrantedAuthority("ROLE_$it") })

    @Test
    fun `without token the request is rejected`() {
        mockMvc.get("/api/members").andExpect { status { isUnauthorized() } }
    }

    @Test
    fun `board, treasurer and admin may read the member list`() {
        for (role in listOf("BOARD", "TREASURER", "ADMIN")) {
            mockMvc.get("/api/members") { with(user(role)) }.andExpect {
                status { isOk() }
                content { json("[]") }
            }
        }
    }

    @Test
    fun `members and trainers may not read the member list`() {
        mockMvc.get("/api/members") { with(user("MEMBER", "TRAINER")) }.andExpect { status { isForbidden() } }
    }

    @Test
    fun `treasurer may not create members`() {
        mockMvc
            .post("/api/members") {
                with(user("TREASURER"))
                contentType = MediaType.APPLICATION_JSON
                content = VALID_MEMBER
            }.andExpect { status { isForbidden() } }
    }

    @Test
    fun `only admin may delete members`() {
        mockMvc.delete("/api/members/${UUID.randomUUID()}") { with(user("BOARD")) }.andExpect {
            status { isForbidden() }
        }
    }

    @Test
    fun `invalid input is answered with field errors`() {
        mockMvc
            .post("/api/members") {
                with(user("BOARD"))
                contentType = MediaType.APPLICATION_JSON
                content = VALID_MEMBER.replace("\"Erika\"", "\" \"").replace("erika@example.org", "keine-mail")
            }.andExpect {
                status { isBadRequest() }
                content { contentType(MediaType.APPLICATION_PROBLEM_JSON) }
                jsonPath("$.errors[?(@.field == 'firstName')].message") { value("Bitte den Vornamen angeben.") }
                jsonPath("$.errors[?(@.field == 'email')]") { exists() }
            }
    }

    @Test
    fun `update without version is rejected`() {
        mockMvc
            .put("/api/members/${UUID.randomUUID()}") {
                with(user("BOARD"))
                contentType = MediaType.APPLICATION_JSON
                content = VALID_MEMBER
            }.andExpect {
                status { isBadRequest() }
                jsonPath("$.errors[0].field") { value("version") }
            }
    }

    private companion object {
        const val VALID_MEMBER = """
            {"memberNumber":"1","firstName":"Erika","lastName":"Muster","birthDate":"2012-03-04","gender":"female",
             "email":"erika@example.org","membershipType":"active","entryDate":"2019-08-01"}
        """
    }
}
