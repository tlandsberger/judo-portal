package de.landsberger.judo.portal.backend.members.internal.access

import java.time.LocalDate
import java.time.Period

/** Altersregeln für Zugänge (rein fachlich, ohne Datenbank – gut testbar). */
object AccessRules {
    /** Ab diesem Alter darf ein Mitglied einen eigenen Zugang bekommen. */
    const val SELF_MIN_AGE = 14

    /** Ab diesem Alter endet der Zugriff der Eltern. */
    const val ADULT_AGE = 18

    fun age(
        birthDate: LocalDate,
        today: LocalDate,
    ): Int = Period.between(birthDate, today).years

    fun mayHaveOwnAccess(
        birthDate: LocalDate,
        today: LocalDate,
    ) = age(birthDate, today) >= SELF_MIN_AGE

    fun isMinor(
        birthDate: LocalDate,
        today: LocalDate,
    ) = age(birthDate, today) < ADULT_AGE

    /** Sieht ein Konto mit dieser Verbindung das Mitglied heute? */
    fun isVisible(
        relation: AccessRelation,
        birthDate: LocalDate,
        today: LocalDate,
    ) = relation == AccessRelation.SELF || isMinor(birthDate, today)
}
