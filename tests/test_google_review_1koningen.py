"""Regressies voor eenduidige Google-opmerkingen bij 1 Koningen."""

import json
from pathlib import Path

from scripts.apply_google_review_1koningen import (
    pas_tekst_aan,
    voeg_dubbelhartigheid_toe,
    voeg_zaaien_en_oogsten_toe,
)


ROOT = Path(__file__).resolve().parents[1]


def html(hoofdstuk, nummer):
    data = json.loads(
        (ROOT / "data" / "1koningen" / f"{hoofdstuk}.json").read_text(encoding="utf-8")
    )
    return next(item["text2026_html"] for item in data["verses"] if item["number"] == nummer)


def test_pas_tekst_aan_vervangt_noodde_en_houdt_html_gelijk():
    vers = {
        "text2026": "Maar Nathan noodde hij niet.",
        "text2026_html": "Maar Nathan noodde hij niet.",
        "textSV1888": "Maar Nathan noodde hij niet.",
        "phraseDiff": [],
    }

    pas_tekst_aan(vers, [("noodde hij niet", "nodigde hij niet uit")], "1 Koningen 1:10")

    assert vers["text2026"] == "Maar Nathan nodigde hij niet uit."
    assert vers["text2026_html"] == vers["text2026"]


def test_pas_tekst_aan_is_idempotent_als_nieuwe_woord_het_oude_bevat():
    vers = {
        "text2026": "De marskramers kwamen.",
        "text2026_html": "De marskramers kwamen.",
        "textSV1888": "De kramers kwamen.",
        "phraseDiff": [],
    }
    assert pas_tekst_aan(vers, [("kramers", "marskramers")], "test") is False
    assert vers["text2026"] == "De marskramers kwamen."


def test_pas_tekst_aan_weigert_onvindbare_brontekst():
    vers = {
        "text2026": "Zo gaf Hiram cederenhout.",
        "text2026_html": "Zo gaf Hiram cederenhout.",
        "textSV1888": "Zo gaf Hiram cederenhout.",
        "phraseDiff": [],
    }

    try:
        pas_tekst_aan(vers, [("ontbrekend", "nieuw")], "1 Koningen 5:10")
    except ValueError as error:
        assert "niet gevonden" in str(error)
    else:
        raise AssertionError("een ontbrekende brontekst mag niet stilzwijgend slagen")


def test_voeg_dubbelhartigheid_toe_maakt_een_tag_met_1_koningen_3_3():
    tags = {"tags": []}

    voeg_dubbelhartigheid_toe(tags)

    assert tags["tags"] == [{
        "id": "dubbelhartigheid",
        "naam": "Dubbelhartigheid",
        "beschrijving": "Een verdeelde toewijding aan JAHWEH en andere wegen.",
        "kleur": "#8b5e3c",
        "verzen": [{"ref": "1koningen 3:3", "rang": 1}],
    }]


def test_eenduidige_lexicale_opmerkingen_zijn_als_principes_corpusbreed_verwerkt():
    """Niet alleen 1 Koningen, maar elk gelijk bronwoord gebruikt de modernisering."""
    oude_vormen = {
        "cederenhout",
        "granaatappelen",
        "gegotene",
        "raderen",
        "schoffelen",
    }
    aangetroffen = set()
    for pad in (ROOT / "data").glob("*/*.json"):
        try:
            inhoud = json.loads(pad.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        ruwe_verzen = inhoud.get("verses", []) if isinstance(inhoud, dict) else []
        verzen = ruwe_verzen.values() if isinstance(ruwe_verzen, dict) else ruwe_verzen
        for vers in verzen:
            if not isinstance(vers, dict):
                continue
            tekst = vers.get("text2026", "").lower()
            aangetroffen.update(vorm for vorm in oude_vormen if vorm in tekst)

    assert aangetroffen == set()


def test_nieuwe_eenduidige_feedbacktermen_zijn_corpusbreed_gemoderniseerd():
    """Veilige termen uit de leesopmerkingen blijven niet in andere boeken staan."""
    oude_vormen = {
        "uitgenomen",
        "vensteren",
        "zijkameren",
        "gebeurde het woord",
        "gaffelen",
    }
    aangetroffen = set()
    for pad in (ROOT / "data").glob("*/*.json"):
        try:
            inhoud = json.loads(pad.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        ruwe_verzen = inhoud.get("verses", []) if isinstance(inhoud, dict) else []
        verzen = ruwe_verzen.values() if isinstance(ruwe_verzen, dict) else ruwe_verzen
        for vers in verzen:
            if not isinstance(vers, dict):
                continue
            tekst = vers.get("text2026", "").lower()
            aangetroffen.update(vorm for vorm in oude_vormen if vorm in tekst)

    assert aangetroffen == set()


def test_bestaande_principe_labels_blijven_behouden_bij_nieuwe_corpus_sweeps():
    """Een veilige woordcorrectie mag herkomstlabels van aangrenzende diff-blokken niet wissen."""
    checks = {
        ("2koningen", 7, 2): "G1",
        ("2koningen", 7, 19): "G1",
        ("ezechiel", 41, 8): "N2",
        ("ezechiel", 41, 9): "N2",
        ("ezechiel", 1, 3): "V1230",
        ("ezechiel", 12, 1): "V1230",
    }
    for (boek, hoofdstuk, nummer), principe in checks.items():
        data = json.loads((ROOT / "data" / boek / f"{hoofdstuk}.json").read_text(encoding="utf-8"))
        vers = next(item for item in data["verses"] if item["number"] == nummer)
        assert principe in {item.get("principe") for item in vers["phraseDiff"]}


def test_profetische_formule_behoudt_een_hoofdletter_aan_het_begin_van_een_vers():
    data = json.loads((ROOT / "data" / "ezechiel" / "1.json").read_text(encoding="utf-8"))
    vers = next(item for item in data["verses"] if item["number"] == 3)

    assert vers["text2026"].startswith("Kwam het woord")
    assert "Kwam het woord" in vers["text2026_html"]


def test_aangrenzende_principes_behouden_beide_herkomstlabels():
    """Een nieuwe woordvervanging mag een reeds gelabelde buur niet wissen."""
    hoofdstuk = json.loads(
        (ROOT / "data" / "zefanja" / "2.json").read_text(encoding="utf-8")
    )
    vers = next(item for item in hoofdstuk["verses"] if item["number"] == 14)
    labels = {item.get("principe") for item in vers["phraseDiff"]}

    assert {"V416", "V1223"} <= labels


def test_eenduidige_termen_in_1_koningen_zeven_zijn_gemoderniseerd():
    hoofdstuk = json.loads(
        (ROOT / "data" / "1koningen" / "7.json").read_text(encoding="utf-8")
    )
    verzen = {item["number"]: item["text2026"] for item in hoofdstuk["verses"]}

    assert "vlechtwerk" in verzen[17]
    assert "scharnieren" in verzen[50]


def test_voeg_zaaien_en_oogsten_toe_koppelt_1_koningen_acht_32():
    tags = {"tags": [{"id": "zaaien-en-oogsten", "verzen": []}]}

    voeg_zaaien_en_oogsten_toe(tags)

    assert tags["tags"][0]["verzen"] == [{"ref": "1koningen 8:32", "rang": 1}]


def test_overige_eenduidige_1_koningen_opmerkingen_staan_in_de_leestekst():
    """Technische tempeltermen en heldere idiomen blijven niet als wachtrij liggen."""
    def vers(hoofdstuk, nummer):
        data = json.loads(
            (ROOT / "data" / "1koningen" / f"{hoofdstuk}.json").read_text(encoding="utf-8")
        )
        return next(item["text2026"] for item in data["verses"] if item["number"] == nummer)

    assert "herendienst" in vers(5, 14)
    assert "herendienst" in vers(9, 15)
    assert "slavenarbeid" in vers(9, 21)
    assert "onderstel" in vers(7, 28)
    assert "steunen" in vers(7, 30)
    assert "hoeveelheid" in vers(7, 47)
    assert "messen" in vers(7, 50)
    assert "gemeenschap" in vers(8, 5)
    assert "uit uw lichaam" in vers(8, 19)

    for nummer in (28, 32, 34, 35):
        assert "de onderstel" not in vers(7, nummer)
    assert "op elk onderstel" in vers(7, 38)

    kronieken = json.loads((ROOT / "data" / "2kronieken" / "8.json").read_text(encoding="utf-8"))
    vers_8 = next(item["text2026"] for item in kronieken["verses"] if item["number"] == 8)
    assert "slavenarbeid" in vers_8


def test_bestaande_principes_blijven_gekoppeld_bij_naburige_tekstcorrecties():
    checks = {
        (7, 28): "N2",
        (7, 30): "V732",
        (7, 34): "V735",
        (7, 35): "V735",
    }
    data = json.loads((ROOT / "data" / "1koningen" / "7.json").read_text(encoding="utf-8"))
    for (hoofdstuk, nummer), principe in checks.items():
        assert hoofdstuk == 7
        vers = next(item for item in data["verses"] if item["number"] == nummer)
        assert principe in {item.get("principe") for item in vers["phraseDiff"]}

    data = json.loads((ROOT / "data" / "1koningen" / "8.json").read_text(encoding="utf-8"))
    vers = next(item for item in data["verses"] if item["number"] == 5)
    assert "V3" in {item.get("principe") for item in vers["phraseDiff"]}


def test_vakmanschap_is_een_zelfstandig_onderwerp_met_tubal_kain_en_hiram():
    tags = json.loads((ROOT / "data" / "tags.json").read_text(encoding="utf-8"))["tags"]
    tag = next(item for item in tags if item["id"] == "vakmanschap")
    refs = {item["ref"] for item in tag["verzen"]}

    assert len(tag["topTien"]) == 10
    assert {"genesis 4:22", "exodus 31:3", "1koningen 7:14"} <= refs
    # De onderwerpenpagina zelf staat sinds de splitsing op Open Gods Woord.


def test_1_koningen_5_2_is_een_aankondiging_en_geen_zelfstandig_citaat():
    data = json.loads((ROOT / "data" / "1koningen" / "5.json").read_text(encoding="utf-8"))
    vers = next(item for item in data["verses"] if item["number"] == 2)

    assert "direct-speech" not in vers["text2026_html"]


def test_resterende_eenduidige_opmerkingen_uit_1_koningen_zijn_verwerkt():
    """Veilige lexicale verbeteringen uit de tweede reviewbatch blijven zichtbaar."""
    def vers(hoofdstuk, nummer):
        data = json.loads(
            (ROOT / "data" / "1koningen" / f"{hoofdstuk}.json").read_text(encoding="utf-8")
        )
        return next(item["text2026"] for item in data["verses"] if item["number"] == nummer)

    assert "marskramers" in vers(10, 15)
    assert "landvoogden" in vers(10, 15)
    assert "grote schilden" in vers(10, 16)
    assert "buitenlandse vrouwen" in vers(11, 1)
    assert "beste manschappen" in vers(12, 21)
    assert "zo deed hij" in vers(12, 32)
    assert "graf van uw vader" in vers(13, 22)
    assert "samenzwering" in vers(15, 27)
    assert "inwoners van Gilead" in vers(17, 1)
    assert "hand vol meel" in vers(17, 12)
    assert "herstelde het altaar" in vers(18, 30)
    assert "vermomde zich" in vers(22, 30)


def test_tweede_reviewbatch_behoudt_bestaande_principekoppelingen():
    """Nieuwe verbeteringen mogen oudere, onafhankelijke herkomstlabels niet wissen."""
    checks = [
        (10, 16, "V941"), (10, 18, "N4"), (10, 18, "V913"),
        (16, 9, "N2"), (16, 26, "N1"), (19, 2, "N4"),
        (20, 43, "V67"), (22, 30, "V42"),
    ]
    for hoofdstuk, nummer, principe in checks:
        data = json.loads(
            (ROOT / "data" / "1koningen" / f"{hoofdstuk}.json").read_text(encoding="utf-8")
        )
        vers = next(item for item in data["verses"] if item["number"] == nummer)
        assert principe in {item.get("principe") for item in vers["phraseDiff"]}


def test_citaten_scheiden_rede_van_vertelling_en_sprekers():
    assert html(11, 2).endswith("neigen;</i></span> aan deze hing Salomo met liefde.")
    assert html(12, 18).count('class="direct-speech"') == 0
    assert html(12, 24).endswith(
        "</i></span> En zij hoorden het woord van JAHWEH, en keerden weer, "
        "om weg te trekken naar het woord van JAHWEH."
    )
    assert html(14, 12).startswith('<span class="god-speaks"><i>')
    assert html(14, 16).startswith('<span class="god-speaks"><i>')
    assert html(18, 40).endswith(
        "</i></span> En zij grepen ze; en Elia voerde hen af naar de beek Kison, "
        "en slachtte hen daar."
    )
    assert html(22, 22).count('class="god-speaks"') == 2
    assert html(22, 22).count('class="direct-speech"') == 1
