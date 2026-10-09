package de.landsberger.judo.portal.backend.members.internal.web

import de.landsberger.judo.portal.api.MeResponse
import de.landsberger.judo.portal.backend.shared.CurrentUser
import org.springframework.web.bind.annotation.GetMapping
import org.springframework.web.bind.annotation.RequestMapping
import org.springframework.web.bind.annotation.RestController

@RestController
@RequestMapping("/api/me")
class MeController {
    /** Der angemeldete Benutzer. Die Verknüpfung mit dem Mitgliedsdatensatz folgt mit der Mitgliederverwaltung. */
    @GetMapping
    fun me(user: CurrentUser): MeResponse =
        MeResponse(
            subject = user.subject,
            displayName = user.displayName,
            email = user.email,
            roles = user.roles,
        )
}
