package de.landsberger.judo.portal.backend.members.internal.domain

import jakarta.persistence.Entity
import jakarta.persistence.EnumType
import jakarta.persistence.Enumerated
import jakarta.persistence.Id
import jakarta.persistence.Table
import jakarta.persistence.Version
import org.hibernate.annotations.CreationTimestamp
import org.hibernate.annotations.UpdateTimestamp
import java.time.Instant
import java.time.LocalDate
import java.util.UUID

/** Ein Vereinsmitglied, unabhängig davon, ob es einen Login im Portal hat. */
@Entity
@Table(name = "member")
class Member(
    @Id
    val id: UUID = UUID.randomUUID(),
    data: MemberData,
) {
    var memberNumber: String? = null
    lateinit var firstName: String
    lateinit var lastName: String
    lateinit var birthDate: LocalDate

    @Enumerated(EnumType.STRING)
    lateinit var gender: Gender
    var street: String? = null
    var postalCode: String? = null
    var city: String? = null
    var phone: String? = null
    var email: String? = null

    @Enumerated(EnumType.STRING)
    lateinit var membershipType: MembershipType
    lateinit var entryDate: LocalDate
    var exitDate: LocalDate? = null

    /** Optimistisches Locking; `null` heißt „noch nicht gespeichert“. */
    @Version
    var version: Long? = null

    @CreationTimestamp
    var createdAt: Instant? = null

    @UpdateTimestamp
    var updatedAt: Instant? = null

    init {
        update(data)
    }

    fun update(data: MemberData) {
        memberNumber = data.memberNumber
        firstName = data.firstName
        lastName = data.lastName
        birthDate = data.birthDate
        gender = data.gender
        street = data.street
        postalCode = data.postalCode
        city = data.city
        phone = data.phone
        email = data.email
        membershipType = data.membershipType
        entryDate = data.entryDate
        exitDate = data.exitDate
    }

    /** Ausgetreten ist, wessen Austrittsdatum vor [today] liegt; am Austrittstag selbst ist man noch Mitglied. */
    fun hasLeft(today: LocalDate): Boolean = exitDate?.isBefore(today) == true
}
