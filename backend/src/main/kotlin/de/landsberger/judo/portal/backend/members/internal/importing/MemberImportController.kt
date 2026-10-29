package de.landsberger.judo.portal.backend.members.internal.importing

import de.landsberger.judo.portal.backend.shared.InvalidInputException
import org.springframework.http.MediaType
import org.springframework.security.access.prepost.PreAuthorize
import org.springframework.web.bind.annotation.PostMapping
import org.springframework.web.bind.annotation.RequestMapping
import org.springframework.web.bind.annotation.RequestPart
import org.springframework.web.bind.annotation.RestController
import org.springframework.web.multipart.MultipartFile

/** Antwort der Vorschau und des Imports: Zähler und alle Zeilen (Fehler zuerst). */
data class ImportResponse(
    val created: Int,
    val updated: Int,
    val unchanged: Int,
    val failed: Int,
    val rows: List<ImportRow>,
) {
    companion object {
        fun of(rows: List<ImportRow>) =
            ImportResponse(
                created = rows.count { it.action == ImportAction.CREATE },
                updated = rows.count { it.action == ImportAction.UPDATE },
                unchanged = rows.count { it.action == ImportAction.UNCHANGED },
                failed = rows.count { it.action == ImportAction.ERROR },
                rows = rows,
            )
    }
}

/**
 * Import der bisherigen Mitgliederliste als CSV (nur Abteilungsleiter, wie Anlegen/Ändern).
 * Die Datei wird nur im Speicher verarbeitet, nie gespeichert oder geloggt.
 */
@RestController
@RequestMapping("/api/members/import")
@PreAuthorize("hasRole('DEPARTMENT_HEAD')")
class MemberImportController(
    private val imports: MemberImportService,
) {
    /** Zeigt, was der Import ändern würde; speichert nichts. */
    @PostMapping("/preview", consumes = [MediaType.MULTIPART_FORM_DATA_VALUE])
    fun preview(
        @RequestPart("file") file: MultipartFile,
    ): ImportResponse = ImportResponse.of(imports.preview(bytes(file)))

    /** Übernimmt alle fehlerfreien Zeilen; die Antwort entspricht der Vorschau zum Zeitpunkt des Imports. */
    @PostMapping(consumes = [MediaType.MULTIPART_FORM_DATA_VALUE])
    fun import(
        @RequestPart("file") file: MultipartFile,
    ): ImportResponse = ImportResponse.of(imports.import(bytes(file)))

    private fun bytes(file: MultipartFile): ByteArray {
        if (file.isEmpty) throw InvalidInputException("file", "Die Datei ist leer.")
        return file.bytes
    }
}
