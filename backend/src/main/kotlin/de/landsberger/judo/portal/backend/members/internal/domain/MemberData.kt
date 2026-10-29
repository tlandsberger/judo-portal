package de.landsberger.judo.portal.backend.members.internal.domain

import java.time.LocalDate

/** Pflegbare Stammdaten eines Mitglieds (ohne Id, Version und Zeitstempel). */
data class MemberData(
    val memberNumber: String?,
    val firstName: String,
    val lastName: String,
    val birthDate: LocalDate,
    val gender: Gender,
    val street: String?,
    val postalCode: String?,
    val city: String?,
    val phone: String?,
    val email: String?,
    val membershipType: MembershipType,
    val entryDate: LocalDate,
    val exitDate: LocalDate?,
)
