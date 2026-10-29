package de.landsberger.judo.portal.backend.members.internal.web

import de.landsberger.judo.portal.backend.members.internal.domain.Gender
import de.landsberger.judo.portal.backend.members.internal.domain.MemberData
import de.landsberger.judo.portal.backend.members.internal.domain.MembershipType
import jakarta.validation.constraints.Email
import jakarta.validation.constraints.NotBlank
import jakarta.validation.constraints.PastOrPresent
import jakarta.validation.constraints.Size
import java.time.LocalDate

/** Eingabe für Anlegen (`POST`) und Ändern (`PUT`) eines Mitglieds. Leere Texte werden zu `null`. */
data class MemberRequest(
    /** Nur beim Ändern (Pflicht): der Stand, der bearbeitet wurde. Ist er veraltet, antwortet die API mit 409. */
    val version: Long?,
    @field:Size(max = 20, message = "Höchstens 20 Zeichen.")
    val memberNumber: String?,
    @field:NotBlank(message = "Bitte den Vornamen angeben.")
    @field:Size(max = 100, message = "Höchstens 100 Zeichen.")
    val firstName: String,
    @field:NotBlank(message = "Bitte den Nachnamen angeben.")
    @field:Size(max = 100, message = "Höchstens 100 Zeichen.")
    val lastName: String,
    @field:PastOrPresent(message = "Das Geburtsdatum darf nicht in der Zukunft liegen.")
    val birthDate: LocalDate,
    val gender: Gender,
    @field:Size(max = 200, message = "Höchstens 200 Zeichen.")
    val street: String?,
    @field:Size(max = 10, message = "Höchstens 10 Zeichen.")
    val postalCode: String?,
    @field:Size(max = 100, message = "Höchstens 100 Zeichen.")
    val city: String?,
    @field:Size(max = 50, message = "Höchstens 50 Zeichen.")
    val phone: String?,
    @field:Email(message = "Bitte eine gültige E-Mail-Adresse angeben.")
    @field:Size(max = 254, message = "Höchstens 254 Zeichen.")
    val email: String?,
    val membershipType: MembershipType,
    val entryDate: LocalDate,
    val exitDate: LocalDate?,
) {
    fun toData(): MemberData =
        MemberData(
            memberNumber = memberNumber.clean(),
            firstName = firstName.trim(),
            lastName = lastName.trim(),
            birthDate = birthDate,
            gender = gender,
            street = street.clean(),
            postalCode = postalCode.clean(),
            city = city.clean(),
            phone = phone.clean(),
            email = email.clean(),
            membershipType = membershipType,
            entryDate = entryDate,
            exitDate = exitDate,
        )

    private fun String?.clean(): String? = this?.trim()?.ifEmpty { null }
}
