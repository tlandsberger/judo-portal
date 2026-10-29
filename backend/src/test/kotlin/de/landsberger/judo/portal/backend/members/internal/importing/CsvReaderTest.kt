package de.landsberger.judo.portal.backend.members.internal.importing

import de.landsberger.judo.portal.backend.shared.InvalidInputException
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.assertThrows
import java.nio.charset.Charset
import kotlin.test.assertEquals

class CsvReaderTest {
    private val header = "Mitgliedsnr;Anrede;Name;Vorname"

    @Test
    fun `reads Excel UTF-8 export with BOM and semicolons`() {
        val bytes =
            byteArrayOf(0xEF.toByte(), 0xBB.toByte(), 0xBF.toByte()) + "$header\n1;Frau;Müller;Jörg\n".toByteArray()

        val table = CsvReader.read(bytes)

        assertEquals(setOf("mitgliedsnr", "anrede", "name", "vorname"), table.columns)
        assertEquals("Müller", table.rows.single()["name"])
        assertEquals(2, table.rows.single().line)
    }

    @Test
    fun `falls back to Windows-1252 for classic Excel export`() {
        val bytes = "$header\r\n1;Herr;Groß;Björn\r\n".toByteArray(Charset.forName("windows-1252"))

        val row = CsvReader.read(bytes).rows.single()

        assertEquals("Groß", row["name"])
        assertEquals("Björn", row["vorname"])
    }

    @Test
    fun `detects commas, honours quotes and normalises headers`() {
        val csv = "  Mitgliedsnr , Telefon   Privat,Name\n7,\"040 1234, priv.\",\"Meier; Jr.\"\n"

        val row = CsvReader.read(csv.toByteArray()).rows.single()

        assertEquals("7", row["mitgliedsnr"])
        assertEquals("040 1234, priv.", row["telefon privat"])
        assertEquals("Meier; Jr.", row["name"])
    }

    @Test
    fun `skips empty rows but keeps Excel line numbers`() {
        val csv = "$header\n1;;A;B\n;;;\n2;;C;D\n"

        val rows = CsvReader.read(csv.toByteArray()).rows

        assertEquals(listOf(2L, 4L), rows.map { it.line })
        assertEquals("", rows.first()["unbekannt"])
    }

    @Test
    fun `rejects empty files`() {
        val error = assertThrows<InvalidInputException> { CsvReader.read(ByteArray(0)) }
        assertEquals("file", error.field)
    }
}
