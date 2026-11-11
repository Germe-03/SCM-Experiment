"""CEO-Avatare für Spielmodus Phase 4: Übernahmen, Holding und CEOs.

Reine Logik ohne Import der Simulation; siehe
docs/spielmodus-phase4-schnittstelle.md, Abschnitt market_sim/game/ceos.py.
Die 20 Avatare stammen aus docs/avatar-prompts.md.
"""

from __future__ import annotations

from dataclasses import dataclass


# Tendenz und Anzeigelabel je Stil (siehe Schnittstellendokument).
STYLE_TENDENCY = {
    "vorsichtig": "reliable",
    "wachstum": "growth",
    "sparsam": "low_cost",
    "marketing": "premium",
}
STYLE_LABEL = {
    "vorsichtig": "Vorsichtig",
    "wachstum": "Auf Wachstum aus",
    "sparsam": "Sparsam",
    "marketing": "Auf Marketing aus",
}
CAUTIOUS_TENDENCY = "reliable"  # Tochter ohne CEO
RETIRE_AGE = 65  # mit diesem Alter geht ein Avatar in Pension
MIN_AGE = 25  # ab diesem Alter wählbar


@dataclass(frozen=True)
class Avatar:
    """Ein CEO-Avatar mit Stammdaten aus docs/avatar-prompts.md."""

    nr: int                  # 1..20
    name: str
    sex: str                 # "w" | "m"
    birth_month: int         # Geburtstag: Monat
    birth_day: int           # Geburtstag: Tag
    appear_year: int         # Spieljahr (Dokument-Zählung, 0-basiert) des Auftauchens
    appear_age: int          # Alter beim Auftauchen (am Jahresbeginn von appear_year)
    style: str               # "vorsichtig" | "wachstum" | "sparsam" | "marketing"
    salary: float            # CHF pro Jahr


# Reihenfolge der Felder: nr, name, sex, birth_month, birth_day,
# appear_year, appear_age, style, salary.
# Lohn: 240'000 CHF Grundlage, +4'000 je Lebensjahr über 25,
# +60'000 für Stil "wachstum", gedeckelt bei 480'000 (feste Werte).
AVATARS: list[Avatar] = [
    Avatar(1, "Lea Brunner", "w", 3, 14, 0, 25, "wachstum", 300000.0),
    Avatar(2, "Marco Bianchi", "m", 7, 2, 0, 27, "marketing", 248000.0),
    Avatar(3, "Aylin Demir", "w", 11, 21, 0, 30, "sparsam", 260000.0),
    Avatar(4, "Jonas Keller", "m", 1, 9, 0, 33, "vorsichtig", 272000.0),
    Avatar(5, "Chiara Rossi", "w", 5, 30, 0, 36, "marketing", 284000.0),
    Avatar(6, "Samuel Okafor", "m", 8, 17, 0, 39, "wachstum", 356000.0),
    Avatar(7, "Nadia Meier", "w", 12, 3, 0, 42, "vorsichtig", 308000.0),
    Avatar(8, "Luca Steiner", "m", 4, 26, 0, 45, "sparsam", 320000.0),
    Avatar(9, "Mei Lin Huber", "w", 9, 11, 0, 48, "wachstum", 392000.0),
    Avatar(10, "Reto Gerber", "m", 2, 28, 0, 52, "vorsichtig", 348000.0),
    Avatar(11, "Elena Vogel", "w", 6, 7, 12, 25, "wachstum", 300000.0),
    Avatar(12, "Noah Schmid", "m", 10, 19, 16, 26, "sparsam", 244000.0),
    Avatar(13, "Fatima Berisha", "w", 2, 1, 14, 20, "marketing", 240000.0),
    Avatar(14, "Tim Baumann", "m", 7, 23, 22, 30, "vorsichtig", 260000.0),
    Avatar(15, "Sofia Costa", "w", 12, 12, 20, 20, "wachstum", 300000.0),
    Avatar(16, "Arjun Patel", "m", 4, 5, 28, 35, "sparsam", 280000.0),
    Avatar(17, "Laura Frei", "w", 9, 29, 31, 28, "vorsichtig", 252000.0),
    Avatar(18, "Elias Fontana", "m", 1, 15, 34, 41, "marketing", 304000.0),
    Avatar(19, "Mira Graf", "w", 8, 8, 32, 20, "wachstum", 300000.0),
    Avatar(20, "Nils Ammann", "m", 3, 22, 39, 33, "sparsam", 272000.0),
]

AVATAR_BY_NR: dict[int, Avatar] = {a.nr: a for a in AVATARS}


def _birthday_index(avatar: Avatar, dpy: int) -> int:
    """Tag-im-Jahr-Index des Geburtstags (0-basiert), höchstens dpy - 1."""
    idx = round(
        (avatar.birth_month - 1) * dpy / 12 + (avatar.birth_day - 1) * dpy / 365
    )
    return min(idx, dpy - 1)


def age(avatar: Avatar, year: int, day_of_year: int, days_per_year: int) -> int:
    """Alter im 1-basierten Spieljahr year (Spieljahr 1 = "Spieljahr 0" im Dokument).

    appear_age gilt am Jahresbeginn von appear_year; am Geburtstag kommt ein Jahr dazu.
    """
    value = avatar.appear_age + (year - 1 - avatar.appear_year)
    birthday = _birthday_index(avatar, days_per_year)
    if 0 < birthday <= day_of_year:
        value += 1
    return value


def visible(avatar: Avatar, year: int, day: int, dpy: int) -> bool:
    """True, sobald der Avatar aufgetaucht ist (year - 1 >= appear_year)."""
    return year - 1 >= avatar.appear_year


def available(avatar: Avatar, year: int, day: int, dpy: int) -> bool:
    """Sichtbar und im wählbaren Bereich MIN_AGE bis RETIRE_AGE."""
    return visible(avatar, year, day, dpy) and (
        MIN_AGE <= age(avatar, year, day, dpy) < RETIRE_AGE
    )


def stage(avatar: Avatar, year: int, day: int, dpy: int) -> str:
    """Altersstufe: "jung" (< 40), "mittel" (< 55) oder "alt"."""
    years = age(avatar, year, day, dpy)
    if years < 40:
        return "jung"
    if years < 55:
        return "mittel"
    return "alt"


def image_name(avatar: Avatar, year: int, day: int, dpy: int) -> str:
    """Bildname je Altersstufe, z.B. "ceo_01_jung.png"."""
    return f"ceo_{avatar.nr:02d}_{stage(avatar, year, day, dpy)}.png"


class CeoBook:
    """Zuordnung von Firmen-IDs zu Avatar-Nummern (ein CEO führt nur eine Firma)."""

    def __init__(self) -> None:
        self.assignments: dict[str, int] = {}  # firm_id -> avatar nr

    def ceo_of(self, firm_id: str) -> Avatar | None:
        """Avatar des CEOs der Firma oder None."""
        nr = self.assignments.get(firm_id)
        return AVATAR_BY_NR.get(nr) if nr is not None else None

    def firm_of(self, nr: int) -> str | None:
        """Firmen-ID, bei der der Avatar CEO ist, oder None."""
        for firm_id, cur in self.assignments.items():
            if cur == nr:
                return firm_id
        return None

    def hire(self, firm_id: str, nr: int, year: int, day: int, dpy: int) -> None:
        """Avatar nr als CEO der Firma einsetzen; ersetzt den bisherigen CEO."""
        avatar = AVATAR_BY_NR.get(nr)
        if avatar is None:
            raise ValueError(f"Unbekannter Avatar mit Nummer {nr}.")
        if not available(avatar, year, day, dpy):
            raise ValueError(f"{avatar.name} ist nicht als CEO verfügbar.")
        other = self.firm_of(nr)
        if other is not None and other != firm_id:
            raise ValueError(f"{avatar.name} ist bereits CEO einer anderen Firma.")
        self.assignments[firm_id] = nr  # ersetzt bisherigen CEO

    def fire(self, firm_id: str) -> Avatar | None:
        """CEO der Firma entfernen; gibt den Avatar zurück oder None."""
        nr = self.assignments.pop(firm_id, None)
        return AVATAR_BY_NR.get(nr) if nr is not None else None

    def retire_due(self, year: int, day: int, dpy: int) -> list[tuple[str, Avatar]]:
        """Alle CEOs mit Alter >= RETIRE_AGE entfernen; Liste von (firm_id, avatar)."""
        removed: list[tuple[str, Avatar]] = []
        for firm_id, nr in list(self.assignments.items()):
            avatar = AVATAR_BY_NR.get(nr)
            if avatar is not None and age(avatar, year, day, dpy) >= RETIRE_AGE:
                del self.assignments[firm_id]
                removed.append((firm_id, avatar))
        return removed

    def roster(self, year: int, day: int, dpy: int) -> list[dict]:
        """Alle sichtbaren Avatare, sortiert nach nr."""
        entries: list[dict] = []
        for avatar in sorted(AVATARS, key=lambda a: a.nr):
            if not visible(avatar, year, day, dpy):
                continue
            entries.append(
                {
                    "nr": avatar.nr,
                    "name": avatar.name,
                    "sex": avatar.sex,
                    "age": age(avatar, year, day, dpy),
                    "style": avatar.style,
                    "style_label": STYLE_LABEL[avatar.style],
                    "salary": avatar.salary,
                    "image": image_name(avatar, year, day, dpy),
                    "available": available(avatar, year, day, dpy),
                    "firm": self.firm_of(avatar.nr),
                }
            )
        return entries
