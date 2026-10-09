package de.landsberger.judo.portal.backend

import org.junit.jupiter.api.Test
import org.springframework.modulith.core.ApplicationModules
import kotlin.test.assertEquals

class ModularityTest {
    private val modules = ApplicationModules.of(PortalApplication::class.java)

    @Test
    fun `module boundaries are respected`() {
        modules.verify()
    }

    @Test
    fun `all planned modules exist`() {
        val names = modules.map { it.identifier.toString() }.toSet()
        assertEquals(setOf("members", "events", "billing", "shared"), names)
    }
}
