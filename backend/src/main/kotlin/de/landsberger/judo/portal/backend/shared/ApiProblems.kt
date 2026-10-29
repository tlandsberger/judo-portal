package de.landsberger.judo.portal.backend.shared

import org.springframework.http.HttpStatus

/**
 * Fachliche Fehler, die die API als Problem Details (RFC 9457) beantwortet.
 * [field] ordnet den Fehler einem Eingabefeld zu, damit die PWA ihn direkt am Feld anzeigt.
 */
sealed class ApiProblemException(
    val status: HttpStatus,
    message: String,
    val field: String? = null,
) : RuntimeException(message)

/** 404: Der angefragte Datensatz existiert nicht. */
class NotFoundException(
    message: String,
) : ApiProblemException(HttpStatus.NOT_FOUND, message)

/** 409: Widerspruch zu vorhandenen Daten, z. B. doppelte Nummer oder veraltete Version. */
class ConflictException(
    message: String,
    field: String? = null,
) : ApiProblemException(HttpStatus.CONFLICT, message, field)

/** 400: Eingabe ist fachlich ungültig (Prüfungen über mehrere Felder, die Bean Validation nicht abdeckt). */
class InvalidInputException(
    field: String,
    message: String,
) : ApiProblemException(HttpStatus.BAD_REQUEST, message, field)
