"""Godsnaamweergave voor de website en PDF-uitgaven."""
import re


def heere(tekst):
    """Volg de klassieke leesoptie; behoud HTML-tags en hun attributen."""
    regels = (
        (r'\bGod JAHWEH\b', 'de HEERE God', 0),
        (r'\bJAHWEH van de legermachten\b', 'de HEERE der heirscharen', 0),
        (r'\b(op|van|aan|voor|tot|door|in|met|bij|over|onder|naast|achter|jegens|uit|na|sinds) JAHWEH\b', r'\1 de HEERE', re.I),
        (r'\b([Oo]) JAHWEH\b', r'\1 HEERE', 0),
        (r'\bJAHWEH!', 'HEERE!', 0),
        (r'(^|[.!?]\s+)JAHWEH\b', r'\1De HEERE', 0),
        (r'\bJAHWEH\b', 'de HEERE', 0),
        (r'\bde de HEERE\b', 'de HEERE', 0),
        (r'\bDe de HEERE\b', 'De HEERE', 0),
    )
    delen = re.split(r'(<[^>]+>)', tekst)
    for i in range(0, len(delen), 2):
        for patroon, vervanging, flags in regels:
            delen[i] = re.sub(patroon, vervanging, delen[i], flags=flags)
    return ''.join(delen)


def yhwh(tekst):
    """YHWH-uitgave: omzetting in tekst, met behoud van HTML en attributen."""
    delen = re.split(r'(<[^>]+>)', tekst)
    for i in range(0, len(delen), 2):
        t = delen[i]
        t = re.sub(r'\b([Dd])es HEEREN\b', lambda m: 'Van YHWH' if m[1] == 'D' else 'van YHWH', t)
        t = re.sub(r'\b(?:[Dd]e|[Dd]en) HEERE\b', 'YHWH', t)
        t = re.sub(r'\b(?:JAHWEH|HEERE|HEEREN)\b', 'YHWH', t)
        t = re.sub(r'\b(?:[Dd]e|[Dd]en) YHWH\b', 'YHWH', t)
        delen[i] = t
    return ''.join(delen)
