package de.landsberger.judo.portal.backend.members.internal.domain

import de.landsberger.judo.portal.backend.shared.ConflictException
import de.landsberger.judo.portal.backend.shared.InvalidInputException
import de.landsberger.judo.portal.backend.shared.NotFoundException
import org.springframework.data.domain.Sort
import org.springframework.data.repository.findByIdOrNull
import org.springframework.stereotype.Service
import org.springframework.transaction.annotation.Transactional
import java.util.UUID

/** Anlegen, Ändern und Löschen von Mitgliedern. Wer das darf, prüft der Controller (Rollen). */
@Service
@Transactional
class MemberService(
    private val repository: MemberRepository,
) {
    @Transactional(readOnly = true)
    fun findAll(): List<Member> = repository.findAll(Sort.by("lastName", "firstName"))

    @Transactional(readOnly = true)
    fun get(id: UUID): Member = repository.findByIdOrNull(id) ?: throw NotFoundException("Das Mitglied gibt es nicht.")

    fun create(data: MemberData): Member {
        check(data, id = null)
        return repository.saveAndFlush(Member(data = data))
    }

    /** [version] ist der Stand, den der Nutzer bearbeitet hat; ist er veraltet, gibt es einen Konflikt. */
    fun update(
        id: UUID,
        version: Long,
        data: MemberData,
    ): Member {
        val member = get(id)
        if (member.version != version) {
            throw ConflictException("Das Mitglied wurde zwischenzeitlich geändert. Bitte neu laden.")
        }
        check(data, id)
        member.update(data)
        return repository.saveAndFlush(member)
    }

    fun delete(id: UUID) {
        repository.delete(get(id))
    }

    private fun check(
        data: MemberData,
        id: UUID?,
    ) {
        if (data.exitDate != null && data.exitDate.isBefore(data.entryDate)) {
            throw InvalidInputException("exitDate", "Der Austritt darf nicht vor dem Eintritt liegen.")
        }
        val sameNumber = data.memberNumber?.let(repository::findByMemberNumber)
        if (sameNumber != null && sameNumber.id != id) {
            throw ConflictException("Die Mitgliedsnummer ist bereits vergeben.", field = "memberNumber")
        }
    }
}
