package de.landsberger.judo.portal.backend.members.internal.importing

import de.landsberger.judo.portal.backend.shared.security.CurrentUserWebConfig
import de.landsberger.judo.portal.backend.shared.security.SecurityConfig
import org.junit.jupiter.api.Test
import org.springframework.beans.factory.annotation.Autowired
import org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest
import org.springframework.context.annotation.Import
import org.springframework.mock.web.MockMultipartFile
import org.springframework.security.core.authority.SimpleGrantedAuthority
import org.springframework.security.oauth2.jwt.JwtDecoder
import org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.jwt
import org.springframework.test.context.bean.override.mockito.MockitoBean
import org.springframework.test.web.servlet.MockMvc
import org.springframework.test.web.servlet.multipart

/** Nur der Abteilungsleiter darf importieren; der Ablauf selbst steht in `MembersImportIT`. */
@WebMvcTest(MemberImportController::class)
@Import(SecurityConfig::class, CurrentUserWebConfig::class)
class MemberImportControllerTest(
    @Autowired private val mockMvc: MockMvc,
) {
    @MockitoBean
    private lateinit var jwtDecoder: JwtDecoder

    @MockitoBean
    private lateinit var importService: MemberImportService

    private val file = MockMultipartFile("file", "liste.csv", "text/csv", "Mitgliedsnr\n1\n".toByteArray())

    private fun user(vararg roles: String) =
        jwt()
            .jwt { it.subject("user-1") }
            .authorities(roles.map { SimpleGrantedAuthority("ROLE_$it") })

    @Test
    fun `admin and trainer may not import`() {
        for (role in listOf("ADMIN", "TRAINER")) {
            for (path in listOf("/api/members/import", "/api/members/import/preview")) {
                mockMvc
                    .multipart(path) {
                        file(file)
                        with(user(role))
                    }.andExpect { status { isForbidden() } }
            }
        }
    }

    @Test
    fun `department head gets a preview`() {
        mockMvc
            .multipart("/api/members/import/preview") {
                file(file)
                with(user("DEPARTMENT_HEAD"))
            }.andExpect {
                status { isOk() }
                jsonPath("$.created") { value(0) }
            }
    }

    @Test
    fun `empty file is rejected`() {
        mockMvc
            .multipart("/api/members/import/preview") {
                file(MockMultipartFile("file", "leer.csv", "text/csv", ByteArray(0)))
                with(user("DEPARTMENT_HEAD"))
            }.andExpect {
                status { isBadRequest() }
                jsonPath("$.errors[0].field") { value("file") }
            }
    }
}
