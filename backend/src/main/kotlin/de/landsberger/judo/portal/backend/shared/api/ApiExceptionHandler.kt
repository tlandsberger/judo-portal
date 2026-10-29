package de.landsberger.judo.portal.backend.shared.api

import de.landsberger.judo.portal.backend.shared.ApiProblemException
import org.springframework.dao.DataIntegrityViolationException
import org.springframework.http.HttpHeaders
import org.springframework.http.HttpStatus
import org.springframework.http.HttpStatusCode
import org.springframework.http.ProblemDetail
import org.springframework.http.ResponseEntity
import org.springframework.orm.ObjectOptimisticLockingFailureException
import org.springframework.web.bind.MethodArgumentNotValidException
import org.springframework.web.bind.annotation.ExceptionHandler
import org.springframework.web.bind.annotation.RestControllerAdvice
import org.springframework.web.context.request.WebRequest
import org.springframework.web.servlet.mvc.method.annotation.ResponseEntityExceptionHandler

/**
 * Einheitliche Fehlerantworten als Problem Details (RFC 9457). Feldfehler stehen in der Eigenschaft
 * `errors` als Liste von `{field, message}`, die Texte sind deutsch und für Nutzer gedacht.
 * Ersetzt den Standard-Handler von Spring Boot (`spring.mvc.problemdetails`).
 */
@RestControllerAdvice
class ApiExceptionHandler : ResponseEntityExceptionHandler() {
    override fun handleMethodArgumentNotValid(
        ex: MethodArgumentNotValidException,
        headers: HttpHeaders,
        status: HttpStatusCode,
        request: WebRequest,
    ): ResponseEntity<Any>? {
        val problem = ProblemDetail.forStatusAndDetail(status, "Die Eingaben sind ungültig.")
        problem.setProperty(
            ERRORS,
            ex.bindingResult.fieldErrors.map { FieldProblem(it.field, it.defaultMessage ?: "ist ungültig") },
        )
        return handleExceptionInternal(ex, problem, headers, status, request)
    }

    @ExceptionHandler(ApiProblemException::class)
    fun handleApiProblem(ex: ApiProblemException): ProblemDetail =
        ProblemDetail.forStatusAndDetail(ex.status, ex.message.orEmpty()).apply {
            ex.field?.let { setProperty(ERRORS, listOf(FieldProblem(it, ex.message.orEmpty()))) }
        }

    @ExceptionHandler(ObjectOptimisticLockingFailureException::class)
    fun handleOptimisticLocking(): ProblemDetail =
        ProblemDetail.forStatusAndDetail(
            HttpStatus.CONFLICT,
            "Der Datensatz wurde zwischenzeitlich geändert. Bitte neu laden.",
        )

    @ExceptionHandler(DataIntegrityViolationException::class)
    fun handleDataIntegrity(): ProblemDetail =
        ProblemDetail.forStatusAndDetail(HttpStatus.CONFLICT, "Die Änderung widerspricht vorhandenen Daten.")

    data class FieldProblem(
        val field: String,
        val message: String,
    )

    private companion object {
        const val ERRORS = "errors"
    }
}
