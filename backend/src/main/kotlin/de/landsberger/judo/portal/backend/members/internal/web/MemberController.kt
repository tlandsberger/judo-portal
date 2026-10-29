package de.landsberger.judo.portal.backend.members.internal.web

import de.landsberger.judo.portal.backend.members.internal.domain.MemberService
import de.landsberger.judo.portal.backend.shared.InvalidInputException
import jakarta.validation.Valid
import org.springframework.http.HttpStatus
import org.springframework.http.ResponseEntity
import org.springframework.security.access.prepost.PreAuthorize
import org.springframework.web.bind.annotation.DeleteMapping
import org.springframework.web.bind.annotation.GetMapping
import org.springframework.web.bind.annotation.PathVariable
import org.springframework.web.bind.annotation.PostMapping
import org.springframework.web.bind.annotation.PutMapping
import org.springframework.web.bind.annotation.RequestBody
import org.springframework.web.bind.annotation.RequestMapping
import org.springframework.web.bind.annotation.ResponseStatus
import org.springframework.web.bind.annotation.RestController
import org.springframework.web.servlet.support.ServletUriComponentsBuilder
import java.time.Clock
import java.time.LocalDate
import java.util.UUID

/**
 * Mitgliederverwaltung. Lesen: Vorstand, Kasse, Admin. Anlegen/Ändern: Vorstand, Admin.
 * Löschen nur Admin (für Fehleingaben; wer austritt, bekommt ein Austrittsdatum).
 */
@RestController
@RequestMapping("/api/members")
class MemberController(
    private val members: MemberService,
    private val clock: Clock,
) {
    @GetMapping
    @PreAuthorize(CAN_READ)
    fun list(): List<MemberResponse> = members.findAll().map { MemberResponse.from(it, today()) }

    @GetMapping("/{id}")
    @PreAuthorize(CAN_READ)
    fun get(
        @PathVariable id: UUID,
    ): MemberResponse = MemberResponse.from(members.get(id), today())

    @PostMapping
    @PreAuthorize(CAN_WRITE)
    @ResponseStatus(HttpStatus.CREATED)
    fun create(
        @Valid @RequestBody request: MemberRequest,
    ): ResponseEntity<MemberResponse> {
        val member = members.create(request.toData())
        val location =
            ServletUriComponentsBuilder
                .fromCurrentRequest()
                .path("/{id}")
                .buildAndExpand(member.id)
                .toUri()
        return ResponseEntity.created(location).body(MemberResponse.from(member, today()))
    }

    @PutMapping("/{id}")
    @PreAuthorize(CAN_WRITE)
    fun update(
        @PathVariable id: UUID,
        @Valid @RequestBody request: MemberRequest,
    ): MemberResponse {
        val version = request.version ?: throw InvalidInputException("version", "Die Version fehlt.")
        return MemberResponse.from(members.update(id, version, request.toData()), today())
    }

    @DeleteMapping("/{id}")
    @PreAuthorize(CAN_DELETE)
    @ResponseStatus(HttpStatus.NO_CONTENT)
    fun delete(
        @PathVariable id: UUID,
    ) {
        members.delete(id)
    }

    private fun today() = LocalDate.now(clock)

    private companion object {
        const val CAN_READ = "hasAnyRole('BOARD', 'TREASURER', 'ADMIN')"
        const val CAN_WRITE = "hasAnyRole('BOARD', 'ADMIN')"
        const val CAN_DELETE = "hasRole('ADMIN')"
    }
}
