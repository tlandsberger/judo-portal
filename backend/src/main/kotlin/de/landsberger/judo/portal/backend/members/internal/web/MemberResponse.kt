package de.landsberger.judo.portal.backend.members.internal.web

import de.landsberger.judo.portal.backend.members.internal.domain.Gender
import de.landsberger.judo.portal.backend.members.internal.domain.Member
import de.landsberger.judo.portal.backend.members.internal.domain.MembershipType
import java.time.LocalDate
import java.util.UUID

/** Ein Mitglied, wie es die API ausliefert. */
data class MemberResponse(
    val id: UUID,
    val memberNumber: String?,
    val firstName: String,
    val lastName: String,
    val birthDate: LocalDate,
    val gender: Gender?,
    val street: String?,
    val postalCode: String?,
    val city: String?,
    val phone: String?,
    val email: String?,
    val membershipType: MembershipType,
    val entryDate: LocalDate,
    val exitDate: LocalDate?,
    /** Austrittsdatum liegt in der Vergangenheit. */
    val left: Boolean,
    /** Für das Ändern zurückschicken (optimistisches Locking). */
    val version: Long,
) {
    companion object {
        fun from(
            member: Member,
            today: LocalDate,
        ) = MemberResponse(
            id = member.id,
            memberNumber = member.memberNumber,
            firstName = member.firstName,
            lastName = member.lastName,
            birthDate = member.birthDate,
            gender = member.gender,
            street = member.street,
            postalCode = member.postalCode,
            city = member.city,
            phone = member.phone,
            email = member.email,
            membershipType = member.membershipType,
            entryDate = member.entryDate,
            exitDate = member.exitDate,
            left = member.hasLeft(today),
            version = checkNotNull(member.version),
        )
    }
}
