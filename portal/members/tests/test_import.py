"""CSV-Import: Vorschau ohne Speichern, Abgleich über die Mitgliedsnummer, leere Zellen überschreiben nichts."""

from datetime import date
from decimal import Decimal

import pytest
from django.urls import reverse

from portal.members import csv_import
from portal.members.models import Interest, Member

pytestmark = pytest.mark.django_db

CSV = (
    "Mitgliedsnummer;Vorname;Nachname;Geburtsdatum;Geschlecht;Graduierung;Gewicht;Sonstiges\n"
    "1001;Mia;Muster;14.03.2015;w;6. Kyu;32,5;wird ignoriert\n"
    "1002;Ben;Beispiel;2012-07-01;m;;;\n"
)


def test_preview_saves_nothing() -> None:
    result = csv_import.preview(CSV)
    assert result.counts == {"new": 2, "changed": 0, "unchanged": 0, "error": 0}
    assert not Member.objects.exists()


def test_apply_creates_members() -> None:
    csv_import.apply(CSV)
    mia = Member.objects.get(member_number="1001")
    assert (mia.first_name, mia.birth_date, mia.gender) == ("Mia", date(2015, 3, 14), "w")
    assert mia.grade == "kyu6" and mia.weight == Decimal("32.5")
    ben = Member.objects.get(member_number="1002")
    assert ben.weight is None and ben.grade == ""


def test_reimport_is_idempotent_and_updates() -> None:
    csv_import.apply(CSV)
    assert csv_import.preview(CSV).counts["unchanged"] == 2
    changed = CSV.replace("6. Kyu", "5. Kyu")
    result = csv_import.preview(changed)
    assert result.counts["changed"] == 1
    assert result.rows[0].changes == ["Graduierung"]
    csv_import.apply(changed)
    assert Member.objects.get(member_number="1001").grade == "kyu5"
    assert Member.objects.count() == 2


def test_empty_cells_do_not_overwrite() -> None:
    csv_import.apply(CSV)
    mia = Member.objects.get(member_number="1001")
    mia.email = "mia@example.org"
    mia.save()
    csv_import.apply("Mitgliedsnummer;Vorname;Nachname;Geburtsdatum;E-Mail;Gewicht\n1001;Mia;Muster;14.03.2015;;\n")
    mia.refresh_from_db()
    assert mia.email == "mia@example.org" and mia.weight == Decimal("32.5")


def test_errors_are_reported_per_row_and_skipped() -> None:
    text = (
        "Mitgliedsnummer,Vorname,Nachname,Geburtsdatum,Graduierung,Gewicht\n"
        "1,Ada,A,31.02.2010,,\n"
        "2,Bo,B,01.01.2010,11. Kyu,\n"
        "3,Cy,C,01.01.2010,,viel\n"
        "4,,D,01.01.2010,,\n"
        "5,Ed,E,01.01.2010,1. Dan,80\n"
        "5,Ed,E,01.01.2010,,\n"
    )
    result = csv_import.preview(text)
    statuses = [row.status for row in result.rows]
    assert statuses == ["error", "error", "error", "error", "new", "error"]
    assert "Geburtsdatum" in result.rows[0].errors[0]
    assert "Vorname fehlt." in result.rows[3].errors
    assert "Zeile 6" in result.rows[5].errors[0]
    csv_import.apply(text)
    assert list(Member.objects.values_list("member_number", flat=True)) == ["5"]


def test_missing_required_column() -> None:
    with pytest.raises(csv_import.CsvError, match="Geburtsdatum"):
        csv_import.preview("Mitgliedsnummer;Vorname;Nachname\n1;A;B\n")


def test_excel_encoding_and_bom() -> None:
    text = csv_import.decode(
        "Mitgliedsnummer;Vorname;Nachname;Geburtsdatum\n1;Jörg;Müller;01.01.1980\n".encode("cp1252")
    )
    assert csv_import.preview(text).rows[0].name == "Jörg Müller"
    text = csv_import.decode(csv_import.template_csv().encode("utf-8"))
    assert csv_import.preview(text).counts["new"] == 1


def test_import_view_preview_then_apply(client, head) -> None:
    client.force_login(head)
    upload = client.post(reverse("member_import"), {"file": _file(CSV)})
    assert upload.status_code == 200 and "Vorschau des Imports" in upload.content.decode()
    assert not Member.objects.exists()
    response = client.post(reverse("member_import"), {"action": "apply"})
    assert response.status_code == 302 and Member.objects.count() == 2


def test_import_view_shows_file_errors(client, head) -> None:
    client.force_login(head)
    response = client.post(reverse("member_import"), {"file": _file("a;b\n1;2\n")})
    assert "Es fehlen Spalten" in response.content.decode()


def test_import_only_for_department_head(client, trainer) -> None:
    client.force_login(trainer)
    assert client.get(reverse("member_import")).status_code == 403
    assert client.get(reverse("member_import_template")).status_code == 403


def _file(text: str):
    from django.core.files.uploadedfile import SimpleUploadedFile

    return SimpleUploadedFile("mitglieder.csv", text.encode("utf-8"), content_type="text/csv")


def test_interests_column() -> None:
    kata, fight = Interest.objects.create(name="Kata"), Interest.objects.create(name="Wettkampf")
    text = "Mitgliedsnummer;Vorname;Nachname;Geburtsdatum;Interessen\n1001;Mia;Muster;14.03.2015;kata, Wettkampf\n"
    csv_import.apply(text)
    mia = Member.objects.get()
    assert set(mia.interests.all()) == {kata, fight}
    assert csv_import.preview(text).counts["unchanged"] == 1
    assert csv_import.preview(text.replace("kata, ", "")).rows[0].changes == ["Interessen"]
    bad = csv_import.preview(text.replace("Wettkampf", "Schwimmen"))
    assert "unbekannt: Schwimmen" in bad.rows[0].errors[0]
