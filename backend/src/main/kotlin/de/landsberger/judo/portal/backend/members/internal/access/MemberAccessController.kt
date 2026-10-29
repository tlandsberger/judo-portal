package de.landsberger.judo.portal.backend.members.internal.access

import de.landsberger.judo.portal.backend.members.internal.web.MemberResponse
import de.landsberger.judo.portal.backend.shared.CurrentUser
import jakarta.validation.Valid
import jakarta.validation.constraints.Email
import jakarta.validation.constraints.NotBlank
import jakarta.validation.constraints.Size
import org.springframework.http.HttpStatus
import org.springframework.security.access.prepost.PreAuthorize
import org.springframework.web.bind.annotation.DeleteMapping
import org.springframework.web.bind.annotation.GetMapping
import org.springframework.web.bind.annotation.PathVariable
import org.springframework.web.bind.annotation.PostMapping
import org.springframework.web.bind.annotation.RequestBody
import org.springframework.web.bind.annotation.RequestMapping
import org.springframework.web.bind.annotation.ResponseStatus
import org.springframework.web.bind.annotation.RestController
import java.time.Clock
import java.time.Instant
import java.time.LocalDate
import java.util.UUID

/** Ein Zugang zu einem Mitglied, wie ihn die Verwaltung sieht. */
data class MemberAccessResponse(
    val id: UUID,
    val relation: AccessRelation,
    val email: String,
    val name: String,
    val status: AccessStatus,
    val createdAt: Instant,
) {
    companion object {
        fun from(view: AccessView) =
            MemberAccessResponse(
                id = view.access.id,
                relation = view.access.relation,
                email = view.access.accountEmail,
                name = view.access.accountName,
                status = view.status,
                createdAt = checkNotNull(view.access.createdAt),
            )
    }
}

/** Einladung: E-Mail; bei Erziehungsberechtigten zusätzlich der Name (beim eigenen Zugang aus dem Mitglied). */
data class InvitationRequest(
    val relation: AccessRelation,
    @field:NotBlank(message = "Bitte die E-Mail-Adresse angeben.")
    @field:Email(message = "Bitte eine gültige E-Mail-Adresse angeben.")
    @field:Size(max = 254, message = "Höchstens 254 Zeichen.")
    val email: String,
    @field:Size(max = 100, message = "Höchstens 100 Zeichen.")
    val firstName: String?,
    @field:Size(max = 100, message = "Höchstens 100 Zeichen.")
    val lastName: String?,
)

data class InvitationResponse(
    val access: MemberAccessResponse,
    /** `false`, wenn ein bereits aktives Konto nur verknüpft wurde. */
    val invitationSent: Boolean,
)

/**
 * Zugänge eines Mitglieds verwalten (ADR 0009): Abteilungsleiter und Administrator.
 */
@RestController
@RequestMapping("/api/members/{memberId}/access")
@PreAuthorize("hasAnyRole('DEPARTMENT_HEAD', 'ADMIN')")
class MemberAccessController(
    private val accesses: MemberAccessService,
) {
    @GetMapping
    fun list(
        @PathVariable memberId: UUID,
    ): List<MemberAccessResponse> = accesses.list(memberId).map(MemberAccessResponse::from)

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    fun invite(
        @PathVariable memberId: UUID,
        @Valid @RequestBody request: InvitationRequest,
    ): InvitationResponse {
        val result = accesses.invite(memberId, request.relation, request.email, request.firstName, request.lastName)
        return InvitationResponse(MemberAccessResponse.from(result.access), result.invitationSent)
    }

    @PostMapping("/{accessId}/resend")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    fun resend(
        @PathVariable memberId: UUID,
        @PathVariable accessId: UUID,
    ) = accesses.resend(memberId, accessId)

    @DeleteMapping("/{accessId}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    fun remove(
        @PathVariable memberId: UUID,
        @PathVariable accessId: UUID,
    ) = accesses.remove(memberId, accessId)
}

/** Ein Mitglied in der eigenen Sicht: man selbst oder das eigene Kind. */
data class MyMemberResponse(
    val relation: AccessRelation,
    val member: MemberResponse,
)

/** Eigene Daten und die der Kinder, nur lesend; für jeden Angemeldeten mit verknüpftem Zugang. */
@RestController
@RequestMapping("/api/me/members")
class MyMembersController(
    private val accesses: MemberAccessService,
    private val clock: Clock,
) {
    @GetMapping
    fun list(user: CurrentUser): List<MyMemberResponse> =
        accesses.visibleTo(user.subject).map { (relation, member) ->
            MyMemberResponse(relation, MemberResponse.from(member, LocalDate.now(clock)))
        }

    @GetMapping("/{memberId}")
    fun get(
        user: CurrentUser,
        @PathVariable memberId: UUID,
    ): MyMemberResponse {
        val (relation, member) = accesses.visibleMember(user.subject, memberId)
        return MyMemberResponse(relation, MemberResponse.from(member, LocalDate.now(clock)))
    }
}
