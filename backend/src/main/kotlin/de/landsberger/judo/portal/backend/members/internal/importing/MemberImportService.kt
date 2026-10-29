package de.landsberger.judo.portal.backend.members.internal.importing

import de.landsberger.judo.portal.backend.members.internal.domain.Gender
import de.landsberger.judo.portal.backend.members.internal.domain.Member
import de.landsberger.judo.portal.backend.members.internal.domain.MemberData
import de.landsberger.judo.portal.backend.members.internal.domain.MemberRepository
import de.landsberger.judo.portal.backend.members.internal.domain.MembershipType
import de.landsberger.judo.portal.backend.members.internal.web.MemberRequest
import de.landsberger.judo.portal.backend.shared.InvalidInputException
import jakarta.validation.Validator
import org.springframework.stereotype.Service
import org.springframework.transaction.annotation.Transactional
import java.time.LocalDate
import java.time.format.DateTimeFormatter
import java.time.format.DateTimeParseException
import java.time.format.ResolverStyle

/** Ergebnis für eine Zeile der Datei. */
data class ImportRow(
    val line: Long,
    val memberNumber: String?,
    val name: String,
    val action: ImportAction,
    /** Deutsche Bezeichnungen der Felder, die sich ändern. */
    val changes: List<String>,
    val errors: List<String>,
    /** Hinweise, die den Import nicht verhindern (z. B. unbekannte Anrede). */
    val notes: List<String>,
)

/**
 * Import der bisherigen Mitgliederliste (Excel als CSV). Abgleich über die Mitgliedsnummer: neue Nummern
 * werden angelegt, bekannte aktualisiert, alle anderen Mitglieder bleiben unberührt. Für ihre Spalten gilt die
 * Datei (leere Zelle = leeres Feld); Adresse und Art der Mitgliedschaft stehen nicht darin und bleiben erhalten.
 */
@Service
class MemberImportService(
    private val repository: MemberRepository,
    private val validator: Validator,
) {
    /** Zeigt, was ein Import ändern würde, ohne etwas zu speichern. */
    @Transactional(readOnly = true)
    fun preview(file: ByteArray): List<ImportRow> = analyze(file).map { it.row }

    /** Übernimmt alle fehlerfreien Zeilen in einer Transaktion; Fehlerzeilen werden übersprungen. */
    @Transactional
    fun import(file: ByteArray): List<ImportRow> {
        val planned = analyze(file)
        planned.forEach { plan ->
            when (plan.row.action) {
                ImportAction.CREATE -> repository.save(Member(data = checkNotNull(plan.data)))
                ImportAction.UPDATE -> checkNotNull(plan.existing).update(checkNotNull(plan.data))
                ImportAction.UNCHANGED, ImportAction.ERROR -> Unit
            }
        }
        repository.flush()
        return planned.map { it.row }
    }

    private class Plan(
        val row: ImportRow,
        val data: MemberData? = null,
        val existing: Member? = null,
    )

    private fun analyze(file: ByteArray): List<Plan> {
        val table = CsvReader.read(file)
        val missing = REQUIRED_COLUMNS.filterNot { it in table.columns }
        if (missing.isNotEmpty()) {
            throw InvalidInputException(
                "file",
                "Es fehlen Spalten: ${missing.joinToString { COLUMN_TITLES.getValue(it) }}. " +
                    "Erwartet wird die Kopfzeile der bisherigen Mitgliederliste.",
            )
        }
        if (table.rows.isEmpty()) {
            throw InvalidInputException("file", "Die Datei enthält keine Mitglieder.")
        }
        val existing = repository.findAll().filter { it.memberNumber != null }.associateBy { it.memberNumber }
        val numberCounts = table.rows.groupingBy { it[NUMBER] }.eachCount()
        return table.rows
            .map { analyzeRow(it, existing, numberCounts) }
            // Fehler zuerst, dann neu, geändert, unverändert – jeweils in Dateireihenfolge.
            .sortedWith(compareBy({ it.row.action != ImportAction.ERROR }, { it.row.action.ordinal }, { it.row.line }))
    }

    private fun analyzeRow(
        row: CsvRow,
        existing: Map<String?, Member>,
        numberCounts: Map<String, Int>,
    ): Plan {
        val number = row[NUMBER]
        val name = listOf(row[LAST_NAME], row[FIRST_NAME]).filter { it.isNotEmpty() }.joinToString(", ")
        val errors = mutableListOf<String>()
        val notes = mutableListOf<String>()

        fun error(): Plan =
            Plan(
                ImportRow(
                    row.line,
                    number.ifEmpty {
                        null
                    },
                    name,
                    ImportAction.ERROR,
                    emptyList(),
                    errors,
                    notes,
                ),
            )

        if (number.isEmpty()) {
            errors += "Die Mitgliedsnummer fehlt."
        } else if ((numberCounts[number] ?: 0) > 1) {
            errors += "Die Mitgliedsnummer $number kommt mehrfach in der Datei vor."
        }
        val birthDate = date(row, BIRTH_DATE, required = true, errors)
        val entryDate = date(row, ENTRY_DATE, required = true, errors)
        val exitDate = date(row, EXIT_DATE, required = false, errors)
        val member = existing[number]
        val salutation = row[SALUTATION]
        val gender = SALUTATIONS[salutation.lowercase()] ?: member?.gender
        if (gender == null) {
            notes +=
                if (salutation.isEmpty()) {
                    "Keine Anrede – Geschlecht bitte im Portal nachtragen."
                } else {
                    "Anrede „$salutation“ unbekannt – Geschlecht bitte im Portal nachtragen."
                }
        }

        // Dieselben Regeln wie beim Anlegen im Portal (Bean Validation von MemberRequest).
        val request =
            MemberRequest(
                version = null,
                memberNumber = number,
                firstName = row[FIRST_NAME],
                lastName = row[LAST_NAME],
                birthDate = birthDate ?: PLACEHOLDER_DATE,
                gender = gender,
                street = member?.street,
                postalCode = member?.postalCode,
                city = member?.city,
                phone = row[PHONE],
                email = row[EMAIL],
                membershipType = member?.membershipType ?: MembershipType.ACTIVE,
                entryDate = entryDate ?: PLACEHOLDER_DATE,
                exitDate = exitDate,
            )
        errors +=
            validator
                .validate(request)
                .sortedBy { it.propertyPath.toString() }
                .map { "${FIELD_TITLES[it.propertyPath.toString()] ?: it.propertyPath}: ${it.message}" }
        if (entryDate != null && exitDate != null && exitDate.isBefore(entryDate)) {
            errors += "Der Austritt darf nicht vor dem Eintritt liegen."
        }
        if (errors.isNotEmpty()) {
            return error()
        }

        val data = request.toData()
        if (member == null) {
            return Plan(ImportRow(row.line, number, name, ImportAction.CREATE, emptyList(), errors, notes), data)
        }
        val changes = changes(member, data)
        val action = if (changes.isEmpty()) ImportAction.UNCHANGED else ImportAction.UPDATE
        return Plan(ImportRow(row.line, number, name, action, changes, errors, notes), data, member)
    }

    private fun date(
        row: CsvRow,
        column: String,
        required: Boolean,
        errors: MutableList<String>,
    ): LocalDate? {
        val value = row[column]
        val title = COLUMN_TITLES.getValue(column)
        if (value.isEmpty()) {
            if (required) errors += "$title fehlt."
            return null
        }
        return try {
            LocalDate.parse(value, GERMAN_DATE)
        } catch (_: DateTimeParseException) {
            errors += "$title „$value“ ist kein Datum im Format TT.MM.JJJJ."
            null
        }
    }

    private fun changes(
        member: Member,
        data: MemberData,
    ): List<String> =
        listOfNotNull(
            "Vorname".takeIf { member.firstName != data.firstName },
            "Nachname".takeIf { member.lastName != data.lastName },
            "Geburtsdatum".takeIf { member.birthDate != data.birthDate },
            "Geschlecht".takeIf { member.gender != data.gender },
            "Telefon".takeIf { member.phone != data.phone },
            "E-Mail".takeIf { member.email != data.email },
            "Eintritt".takeIf { member.entryDate != data.entryDate },
            "Austritt".takeIf { member.exitDate != data.exitDate },
        )

    private companion object {
        const val NUMBER = "mitgliedsnr"
        const val SALUTATION = "anrede"
        const val LAST_NAME = "name"
        const val FIRST_NAME = "vorname"
        const val BIRTH_DATE = "geburtsdatum"
        const val PHONE = "telefon privat"
        const val EMAIL = "e-mail"
        const val ENTRY_DATE = "vereinseintritt"
        const val EXIT_DATE = "vereinsaustritt"

        val REQUIRED_COLUMNS = listOf(NUMBER, LAST_NAME, FIRST_NAME, BIRTH_DATE, ENTRY_DATE)
        val COLUMN_TITLES =
            mapOf(
                NUMBER to "Mitgliedsnr",
                SALUTATION to "Anrede",
                LAST_NAME to "Name",
                FIRST_NAME to "Vorname",
                BIRTH_DATE to "Geburtsdatum",
                PHONE to "Telefon privat",
                EMAIL to "E-Mail",
                ENTRY_DATE to "Vereinseintritt",
                EXIT_DATE to "Vereinsaustritt",
            )
        val FIELD_TITLES =
            mapOf(
                "memberNumber" to "Mitgliedsnr",
                "firstName" to "Vorname",
                "lastName" to "Name",
                "birthDate" to "Geburtsdatum",
                "phone" to "Telefon privat",
                "email" to "E-Mail",
            )
        val SALUTATIONS =
            mapOf(
                "herr" to Gender.MALE,
                "hr." to Gender.MALE,
                "frau" to Gender.FEMALE,
                "fr." to Gender.FEMALE,
            )

        /** `T.M.JJJJ` und `TT.MM.JJJJ`, streng (kein 31.02.). */
        val GERMAN_DATE: DateTimeFormatter =
            DateTimeFormatter.ofPattern("d.M.uuuu").withResolverStyle(ResolverStyle.STRICT)

        /** Nur damit die übrigen Felder geprüft werden können, wenn ein Datum fehlt (Zeile ist dann ohnehin Fehler). */
        val PLACEHOLDER_DATE: LocalDate = LocalDate.of(2000, 1, 1)
    }
}
