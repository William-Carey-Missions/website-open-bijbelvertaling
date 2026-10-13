import importlib.util
import json
from collections import Counter
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "import_inline_woordnummers", ROOT / "scripts" / "import_inline_woordnummers.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

AUDIT_SPEC = importlib.util.spec_from_file_location(
    "audit_woordnummers", ROOT / "scripts" / "audit_woordnummers.py"
)
AUDIT = importlib.util.module_from_spec(AUDIT_SPEC)
AUDIT_SPEC.loader.exec_module(AUDIT)


def _write_usj(path):
    path.write_text(
        json.dumps(
            {
                "type": "USJ",
                "version": "3.1",
                "content": [
                    {"type": "chapter", "marker": "c", "number": "1"},
                    {
                        "type": "para",
                        "marker": "p",
                        "content": [
                            {"type": "verse", "marker": "v", "number": "1"},
                            {"type": "char", "marker": "w", "strong": "G1722", "content": ["In"]},
                            " ",
                            {"type": "char", "marker": "w", "strong": "G746", "content": ["beginning"]},
                        ],
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def test_parse_usj_extracts_word_level_strongs_per_verse(tmp_path):
    source = tmp_path / "44JHN.usj"
    _write_usj(source)

    verses = MODULE.parse_usj(source)

    assert verses[(1, 1)] == [
        {"text": "In", "strongs": ["G1722"]},
        {"text": "beginning", "strongs": ["G746"]},
    ]


def test_parse_tr_utr_separates_display_strong_morphology_and_lemma(tmp_path):
    source = tmp_path / "JOH.UTR"
    source.write_text(
        "1:1 en 1722 {PREP} arch 746 {N-DSF} hn 1510 5707 {V-IAI-3S} "
        "o 3588 {T-NSM} logov 3056 {N-NSM} 5740 {V-PNP-ASM} "
        "2064 5740 {V-PNP-NSN}\n",
        encoding="utf-8",
    )

    verses = MODULE.parse_tr_utr(source)

    assert verses[(1, 1)] == [
        {"text": "en", "lemma_strong": "G1722", "display_strong": "G1722", "morphology": "PREP", "tvm": None},
        {"text": "arch", "lemma_strong": "G746", "display_strong": "G746", "morphology": "N-DSF", "tvm": None},
        {"text": "hn", "lemma_strong": "G1510", "display_strong": "G2258", "morphology": "V-IAI-3S", "tvm": "G5713"},
        {"text": "o", "lemma_strong": "G3588", "display_strong": "G3588", "morphology": "T-NSM", "tvm": None},
        {"text": "logov", "lemma_strong": "G3056", "display_strong": "G3056", "morphology": "N-NSM", "tvm": None},
    ]


def test_parse_tagnt_tr_prefers_traditional_form_number(tmp_path):
    source = tmp_path / "TAGNT.txt"
    source.write_text(
        "Jhn.1.1#03=NKO\tἦν (ēn)\twas\tG1510=V-IAI-3S\tεἰμί=to be\tNA28+TR+Byz"
        "\t\t\t\tto be\t#03\tG1510_A\tG2258\n",
        encoding="utf-8",
    )

    verses = MODULE.parse_tagnt_tr(source, "Jhn", 1)

    assert verses[(1, 1)] == [{
        "text": "ἦν",
        "lemma_strong": "G1510",
        "display_strong": "G2258",
        "morphology": "V-IAI-3S",
        "sequence": 3,
    }]


def test_build_mapping_requires_review_and_matching_source_sequence():
    local = [
        {"woord": "Ἐν", "strongs": "G1722", "transliteratie": "En", "gloss": "in"},
        {"woord": "ἀρχῇ", "strongs": "G746", "transliteratie": "arche", "gloss": "begin"},
    ]
    external = [
        {"text": "In", "strongs": ["G1722"]},
        {"text": "beginning", "strongs": ["G746"]},
    ]
    source = {"id": "bsb-full-strongs-usj", "version": "v5.6", "sha256": "abc"}

    with pytest.raises(ValueError, match="reviewstatus"):
        MODULE.build_inline_mapping(
            {"tekst": "In", "voorkomen": 1, "bronindices": [0], "reviewstatus": "voorstel"},
            external,
            local,
            source,
            "JHN 1:1",
        )

    with pytest.raises(ValueError, match="bronvolgorde"):
        MODULE.build_inline_mapping(
            {
                "tekst": "In",
                "voorkomen": 1,
                "bronindices": [1],
                "confidence": 1.0,
                "reviewstatus": "handmatig_gecontroleerd",
            },
            [{"text": "In", "strongs": ["G1722"]}],
            local,
            source,
            "JHN 1:1",
        )

    result = MODULE.build_inline_mapping(
        {
            "tekst": "het begin",
            "voorkomen": 1,
            "bronindices": [1],
            "confidence": 1.0,
            "reviewstatus": "handmatig_gecontroleerd",
        },
        external,
        local,
        source,
        "JHN 1:1",
    )
    assert result["strongs"] == ["G746"]
    assert result["bronwoorden"] == ["ἀρχῇ"]
    assert result["herkomst"] == {
        "dataset": "bsb-full-strongs-usj",
        "versie": "v5.6",
        "sha256": "abc",
        "referentie": "JHN 1:1",
        "bronindices": [1],
    }


def test_build_mapping_bewaart_lokaal_lemma_bij_gedocumenteerde_gidsafwijking():
    result = MODULE.build_inline_mapping(
        {
            "tekst": "zette",
            "bronindices": [0],
            "grondindices": [0],
            "confidence": 1,
            "reviewstatus": "handmatig_gecontroleerd",
        },
        [{"text": "and placed him", "strongs": ["H5117"]}],
        [{"woord": "וַ/יַּנִּחֵ/הוּ", "strongs": "H3240"}],
        {"id": "bsb-full-strongs-usj", "version": "5.6", "sha256": "abc"},
        "GEN 2:15",
        lemma_afwijking={
            "reden": "lemma_afwijking",
            "bronindices": [0],
            "grondindices": [0],
            "bron_strongs": ["H5117"],
            "grondtekst_strongs": ["H3240"],
        },
    )

    assert result["strongs"] == ["H3240"]
    assert result["gids_strongs"] == ["H5117"]
    assert result["herkomst"]["bronindices"] == [0]


def test_merge_preserves_existing_manually_checked_mapping():
    existing = {
        "tekst": "In",
        "voorkomen": 1,
        "strongs": ["G1722"],
        "reviewstatus": "handmatig_gecontroleerd",
        "confidence": 1.0,
        "herkomst": {"dataset": "redactie"},
    }
    verse = {"text2026": "In het begin", "woordnummers": [existing.copy()]}
    proposed = [
        {**existing, "strongs": ["G9999"], "herkomst": {"dataset": "import"}},
        {
            "tekst": "begin",
            "voorkomen": 1,
            "strongs": ["G746"],
            "reviewstatus": "handmatig_gecontroleerd",
            "confidence": 1.0,
            "herkomst": {"dataset": "import"},
        },
    ]

    added, preserved = MODULE.merge_reviewed_mappings(verse, proposed)

    assert (added, preserved) == (1, 1)
    assert verse["woordnummers"][0] == existing
    assert verse["woordnummers"][1]["strongs"] == ["G746"]


def test_replace_reviewed_mappings_vervangt_alleen_dezelfde_bron_en_reviewvers():
    target_provenance = {
        "dataset": "bsb-full-strongs-usj",
        "versie": "5.6",
        "sha256": "ABC",
        "referentie": "GEN 1:1",
    }
    obsolete = {
        "tekst": "In het begin schiep God de hemel en de aarde.",
        "voorkomen": 1,
        "strongs": ["H7225", "H1254"],
        "herkomst": target_provenance.copy(),
    }
    other_verse = {
        "tekst": "Ander vers",
        "voorkomen": 1,
        "strongs": ["H1"],
        "herkomst": {**target_provenance, "referentie": "GEN 1:2"},
    }
    editorial = {
        "tekst": "God",
        "voorkomen": 1,
        "strongs": ["H430"],
        "herkomst": {"dataset": "redactie", "referentie": "GEN 1:1"},
    }
    verse = {"woordnummers": [obsolete, other_verse, editorial]}
    replacement = {
        "tekst": "begin",
        "voorkomen": 1,
        "strongs": ["H7225"],
        "herkomst": {**target_provenance, "bronindices": [0]},
    }

    replaced = MODULE.replace_reviewed_mappings(
        verse, [replacement], target_provenance
    )

    assert replaced == 1
    assert verse["woordnummers"] == [other_verse, editorial, replacement]


def test_apply_review_file_vervangt_opt_in_alleen_het_reviewvers(tmp_path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    source_path = source_dir / "44JHN.usj"
    _write_usj(source_path)
    source_hash = MODULE._sha256(source_path)
    data_dir = tmp_path / "data" / "johannes"
    data_dir.mkdir(parents=True)
    provenance = {
        "dataset": "bsb-full-strongs-usj",
        "versie": "5.6",
        "sha256": "SOURCE",
        "referentie": "JHN 1:1",
    }
    chapter = {
        "verses": [
            {
                "number": 1,
                "text2026": "In het begin",
                "grondtekst": [
                    {"woord": "In", "strongs": "G1722"},
                    {"woord": "beginning", "strongs": "G746"},
                ],
                "woordnummers": [
                    {"tekst": "In het begin", "voorkomen": 1, "strongs": ["G1722", "G746"], "herkomst": provenance},
                    {"tekst": "In", "voorkomen": 1, "strongs": ["G1722"], "herkomst": {"dataset": "redactie"}},
                ],
            }
        ]
    }
    (data_dir / "1.json").write_text(json.dumps(chapter), encoding="utf-8")
    review = {
        "source": {"id": "bsb-full-strongs-usj", "version": "5.6", "sha256": "SOURCE"},
        "books": [{
            "code": "JHN", "repo_book": "johannes", "chapter": 1,
            "source_file": "44JHN.usj", "source_file_sha256": source_hash,
            "verses": [{
                "verse": 1, "vervang_bronrecords": True,
                "mappings": [
                    {"tekst": "In", "bronindices": [0], "grondindices": [0], "confidence": 1, "reviewstatus": "handmatig_gecontroleerd"},
                    {"tekst": "begin", "bronindices": [1], "grondindices": [1], "confidence": 1, "reviewstatus": "handmatig_gecontroleerd"},
                ],
            }],
        }],
    }
    review_path = tmp_path / "review.json"
    review_path.write_text(json.dumps(review), encoding="utf-8")

    report = MODULE.apply_review_file(review_path, source_dir, tmp_path / "data", write=True)
    saved = json.loads((data_dir / "1.json").read_text(encoding="utf-8"))

    assert report["replaced"] == 1
    assert [item["tekst"] for item in saved["verses"][0]["woordnummers"]] == ["In", "In", "begin"]
    assert saved["verses"][0]["woordnummers"][0]["herkomst"] == {"dataset": "redactie"}


def test_apply_review_file_beperkt_import_tot_gevraagde_verzen(tmp_path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    source_path = source_dir / "44JHN.usj"
    _write_usj(source_path)
    source_hash = MODULE._sha256(source_path)
    data_dir = tmp_path / "data" / "johannes"
    data_dir.mkdir(parents=True)
    (data_dir / "1.json").write_text(json.dumps({"verses": [
        {"number": 1, "text2026": "In", "grondtekst": [{"woord": "In", "strongs": "G1722"}]},
        {"number": 2, "text2026": "Leeg", "grondtekst": []},
    ]}), encoding="utf-8")
    review = {
        "source": {"id": "bsb-full-strongs-usj", "version": "5.6", "sha256": "SOURCE"},
        "books": [{
            "code": "JHN", "repo_book": "johannes", "chapter": 1,
            "source_file": "44JHN.usj", "source_file_sha256": source_hash,
            "verses": [
                {"verse": 1, "mappings": [{"tekst": "In", "bronindices": [0], "grondindices": [0], "confidence": 1, "reviewstatus": "handmatig_gecontroleerd"}]},
                {"verse": 2, "mappings": []},
            ],
        }],
    }
    review_path = tmp_path / "review.json"
    review_path.write_text(json.dumps(review), encoding="utf-8")

    report = MODULE.apply_review_file(
        review_path, source_dir, tmp_path / "data", write=True, verse_numbers={1}
    )

    assert report["verses"] == 1
    saved = json.loads((data_dir / "1.json").read_text(encoding="utf-8"))
    assert saved["verses"][0]["woordnummers"][0]["strongs"] == ["G1722"]
    assert "woordnummers" not in saved["verses"][1]


def test_apply_review_file_adresseert_gidsvers_in_ander_hoofdstuk(tmp_path):
    # 1 Samuel 24:1 hoort bij gidsvers 23:29: het lokale vers staat in
    # hoofdstuk 24, maar de uitlijngids telt dat vers nog bij hoofdstuk 23.
    # Het optionele veld source_chapter maakt die verwijzing adresseerbaar.
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    source_path = source_dir / "091SA.usj"
    source_path.write_text(
        json.dumps(
            {
                "type": "USJ",
                "content": [
                    {"type": "chapter", "marker": "c", "number": "23"},
                    {
                        "type": "para",
                        "marker": "p",
                        "content": [
                            {"type": "verse", "marker": "v", "number": "29"},
                            {"type": "char", "marker": "w", "strong": "H5927", "content": ["went up"]},
                            " ",
                            {"type": "char", "marker": "w", "strong": "H1732", "content": ["David"]},
                        ],
                    },
                    {"type": "chapter", "marker": "c", "number": "24"},
                    {
                        "type": "para",
                        "marker": "p",
                        "content": [
                            {"type": "verse", "marker": "v", "number": "1"},
                            {"type": "char", "marker": "w", "strong": "H1961", "content": ["it came to pass"]},
                        ],
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    source_hash = MODULE._sha256(source_path)
    data_dir = tmp_path / "data" / "1samuel"
    data_dir.mkdir(parents=True)
    (data_dir / "24.json").write_text(json.dumps({"verses": [
        {
            "number": 1,
            "text2026": "En David trok op",
            "grondtekst": [
                {"woord": "וַיַּעַל", "strongs": "H5927"},
                {"woord": "דָּוִד", "strongs": "H1732"},
            ],
        },
    ]}), encoding="utf-8")
    review = {
        "source": {"id": "bsb-full-strongs-usj", "version": "5.6", "sha256": "SOURCE"},
        "books": [{
            "code": "1SA", "repo_book": "1samuel", "chapter": 24,
            "source_file": "091SA.usj", "source_file_sha256": source_hash,
            "verses": [{
                "verse": 1, "source_chapter": 23, "source_verse": 29,
                "mappings": [
                    {"tekst": "trok op", "bronindices": [0], "grondindices": [0], "confidence": 1, "reviewstatus": "handmatig_gecontroleerd"},
                    {"tekst": "David", "bronindices": [1], "grondindices": [1], "confidence": 1, "reviewstatus": "handmatig_gecontroleerd"},
                ],
            }],
        }],
    }
    review_path = tmp_path / "review.json"
    review_path.write_text(json.dumps(review), encoding="utf-8")

    report = MODULE.apply_review_file(review_path, source_dir, tmp_path / "data", write=True)
    saved = json.loads((data_dir / "24.json").read_text(encoding="utf-8"))

    assert report["added"] == 2
    strongs = [item["strongs"] for item in saved["verses"][0]["woordnummers"]]
    assert strongs == [["H5927"], ["H1732"]]
    # De herkomstreferentie noemt het gidshoofdstuk, niet het lokale hoofdstuk.
    assert saved["verses"][0]["woordnummers"][0]["herkomst"]["referentie"] == "1SA 23:29"


def test_apply_review_file_kan_een_lokaal_vers_over_twee_gidsverzen_verdelen(tmp_path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    source_path = source_dir / "46TST.usj"
    source_path.write_text(
        json.dumps(
            {
                "type": "USJ",
                "content": [
                    {"type": "chapter", "marker": "c", "number": "1"},
                    {
                        "type": "para",
                        "marker": "p",
                        "content": [
                            {"type": "verse", "marker": "v", "number": "1"},
                            {"type": "char", "marker": "w", "strong": "G3756", "content": ["not"]},
                            {"type": "verse", "marker": "v", "number": "2"},
                            {"type": "char", "marker": "w", "strong": "G1537", "content": ["from"]},
                            " ",
                            {"type": "char", "marker": "w", "strong": "G2041", "content": ["works"]},
                            " ",
                            {"type": "char", "marker": "w", "strong": "G1398", "content": ["serve"]},
                        ],
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    source_hash = MODULE._sha256(source_path)
    data_dir = tmp_path / "data" / "testboek"
    data_dir.mkdir(parents=True)
    (data_dir / "1.json").write_text(
        json.dumps(
            {
                "verses": [
                    {
                        "number": 1,
                        "text2026": "niet uit werken",
                        "grondtekst": [
                            {"woord": "οὐ", "strongs": "G3756"},
                            {"woord": "ἐξ", "strongs": "G1537"},
                            {"woord": "ἔργων", "strongs": "G2041"},
                        ],
                    },
                    {
                        "number": 2,
                        "text2026": "dienen",
                        "grondtekst": [{"woord": "δουλεύσει", "strongs": "G1398"}],
                    },
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    mapping_meta = {"confidence": 1, "reviewstatus": "handmatig_gecontroleerd"}
    review = {
        "source": {"id": "bsb-full-strongs-usj", "version": "5.6", "sha256": "SOURCE"},
        "books": [
            {
                "code": "TST",
                "repo_book": "testboek",
                "chapter": 1,
                "source_file": "46TST.usj",
                "source_file_sha256": source_hash,
                "verses": [
                    {
                        "verse": 1,
                        "source_verse": 1,
                        "vervang_bronrecords": True,
                        "mappings": [
                            {"tekst": "niet", "bronindices": [0], "grondindices": [0], **mapping_meta},
                            {"tekst": "uit", "bronindices": [0], "grondindices": [1], "source_verse": 2, **mapping_meta},
                            {"tekst": "werken", "bronindices": [1], "grondindices": [2], "source_verse": 2, **mapping_meta},
                        ],
                    },
                    {
                        "verse": 2,
                        "source_verse": 2,
                        "vervang_bronrecords": True,
                        "mappings": [
                            {"tekst": "dienen", "bronindices": [2], "grondindices": [0], **mapping_meta},
                        ],
                    },
                ],
            }
        ],
    }
    review_path = tmp_path / "review.json"
    review_path.write_text(json.dumps(review, ensure_ascii=False), encoding="utf-8")

    report = MODULE.apply_review_file(review_path, source_dir, tmp_path / "data", write=True)
    second_report = MODULE.apply_review_file(
        review_path, source_dir, tmp_path / "data", write=True
    )
    saved = json.loads((data_dir / "1.json").read_text(encoding="utf-8"))

    assert report["added"] == 4
    assert second_report["replaced"] == 4
    assert len(saved["verses"][0]["woordnummers"]) == 3
    assert [item["strongs"] for item in saved["verses"][0]["woordnummers"]] == [
        ["G3756"],
        ["G1537"],
        ["G2041"],
    ]
    assert [item["herkomst"]["referentie"] for item in saved["verses"][0]["woordnummers"]] == [
        "TST 1:1",
        "TST 1:2",
        "TST 1:2",
    ]
    assert saved["verses"][1]["woordnummers"][0]["herkomst"]["referentie"] == "TST 1:2"


def test_apply_review_file_reviewt_apocrief_tegen_lokale_grondtekst(tmp_path):
    # Apocriefe boeken hebben geen externe uitlijngids; het reviewbestand
    # verklaart source_type lokale-grondtekst en pint de tokenlaag met een
    # hash die stabiel blijft wanneer de import woordnummers wegschrijft.
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    data_dir = tmp_path / "data" / "tobit"
    data_dir.mkdir(parents=True)
    chapter = {"verses": [
        {
            "number": 1,
            "text2026": "Het boek van de woorden van Tobit",
            "grondtekst": [
                {"woord": "βίβλος", "strongs": "G976", "transliteratie": "biblos"},
                {"woord": "λόγων", "strongs": "G3056", "transliteratie": "logon"},
            ],
        },
    ]}
    (data_dir / "1.json").write_text(json.dumps(chapter, ensure_ascii=False), encoding="utf-8")
    ground_hash = MODULE._grondtekst_sha256(chapter)
    review = {
        "source": {"id": "lokale-grondtekst", "version": "1", "sha256": ground_hash},
        "books": [{
            "code": "TOB", "repo_book": "tobit", "chapter": 1,
            "source_type": "lokale-grondtekst",
            "grondtekst_sha256": ground_hash,
            "verses": [{
                "verse": 1,
                "mappings": [
                    {"tekst": "boek", "bronindices": [0], "grondindices": [0], "confidence": 1, "reviewstatus": "handmatig_gecontroleerd"},
                    {"tekst": "woorden", "bronindices": [1], "grondindices": [1], "confidence": 1, "reviewstatus": "handmatig_gecontroleerd"},
                ],
            }],
        }],
    }
    review_path = tmp_path / "review.json"
    review_path.write_text(json.dumps(review, ensure_ascii=False), encoding="utf-8")

    report = MODULE.apply_review_file(review_path, source_dir, tmp_path / "data", write=True)
    saved = json.loads((data_dir / "1.json").read_text(encoding="utf-8"))

    assert report["added"] == 2
    first = saved["verses"][0]["woordnummers"][0]
    assert first["strongs"] == ["G976"]
    assert first["herkomst"]["dataset"] == "lokale-grondtekst"
    assert first["herkomst"]["referentie"] == "TOB 1:1"
    # De hash blijft na de import geldig: woordnummers tellen niet mee.
    assert MODULE._grondtekst_sha256(saved) == ground_hash


def test_apply_review_file_weigert_lokale_bron_met_verkeerde_hash(tmp_path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    data_dir = tmp_path / "data" / "tobit"
    data_dir.mkdir(parents=True)
    (data_dir / "1.json").write_text(json.dumps({"verses": [
        {"number": 1, "text2026": "Het boek", "grondtekst": [{"woord": "βίβλος", "strongs": "G976"}]},
    ]}, ensure_ascii=False), encoding="utf-8")
    review = {
        "source": {"id": "lokale-grondtekst", "version": "1", "sha256": "DEAD"},
        "books": [{
            "code": "TOB", "repo_book": "tobit", "chapter": 1,
            "source_type": "lokale-grondtekst",
            "grondtekst_sha256": "DEADBEEF",
            "verses": [{"verse": 1, "mappings": [
                {"tekst": "boek", "bronindices": [0], "grondindices": [0], "confidence": 1, "reviewstatus": "handmatig_gecontroleerd"},
            ]}],
        }],
    }
    review_path = tmp_path / "review.json"
    review_path.write_text(json.dumps(review, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="Grondtekst-hash wijkt af"):
        MODULE.apply_review_file(review_path, source_dir, tmp_path / "data", write=False)


def test_build_mapping_bewaart_niet_vertaald_woord_zichtbaar_bij_anker():
    result = MODULE.build_inline_mapping(
        {
            "tekst": "",
            "anker": "God",
            "plaats": "na",
            "status": "niet_afzonderlijk_weergegeven",
            "bronindices": [0],
            "grondindices": [0],
            "confidence": 1,
            "reviewstatus": "handmatig_gecontroleerd",
        },
        [{"text": "et", "strongs": ["H853"]}],
        [{"woord": "אֵת", "strongs": "H853"}],
        {"id": "bsb-full-strongs-usj", "version": "5.6", "sha256": "abc"},
        "GEN 1:1",
    )

    assert result["tekst"] == ""
    assert result["anker"] == "God"
    assert result["plaats"] == "na"
    assert result["status"] == "niet_afzonderlijk_weergegeven"


def test_johannes_1_1_tot_5_is_tr_reviewed_without_text_changes():
    data = json.loads((ROOT / "data" / "johannes" / "1.json").read_text(encoding="utf-8"))
    verses = {verse["number"]: verse for verse in data["verses"]}

    for number in range(1, 6):
        mappings = verses[number].get("woordnummers", [])
        assert mappings, f"Johannes 1:{number} mist inline woordnummers"
        assert all(item["reviewstatus"] == "handmatig_gecontroleerd" for item in mappings)
        assert all(item["confidence"] == 1.0 for item in mappings)
        assert all(item["herkomst"]["dataset"] == "robinson-scrivener-tr" for item in mappings)
        assert all(item["herkomst"]["versie"] == "7fd4d02c3e5adebd379ebfbc824040820dde10fc" for item in mappings)

    assert verses[1]["text2026"] == "In het begin was het Woord, en het Woord was bij God, en het Woord was God."


def test_johannes_1_publiceert_ieder_tr_grondwoord_inline_ook_zonder_vertaling():
    data = json.loads((ROOT / "data" / "johannes" / "1.json").read_text(encoding="utf-8"))
    assert len(data["verses"]) == 52

    for verse in data["verses"]:
        ground = [str(word.get("strongs") or "") for word in verse.get("grondtekst", [])]
        mappings = verse.get("woordnummers", [])
        linked = [number for mapping in mappings for number in mapping.get("strongs", [])]
        assert ground, f"Johannes 1:{verse['number']} mist de TR-grondtekst"
        source_indices = [
            index for mapping in mappings
            for index in mapping.get("herkomst", {}).get("bronindices", [])
        ]
        assert Counter(linked) == Counter(ground), f"Johannes 1:{verse['number']} publiceert niet ieder TR-woord"
        assert len(source_indices) == len(ground)
        assert len(set(source_indices)) == len(source_indices), f"Johannes 1:{verse['number']} koppelt een TR-token dubbel"
        assert all(mapping.get("reviewstatus") == "handmatig_gecontroleerd" for mapping in mappings)
        assert all(mapping.get("herkomst", {}).get("dataset") == "robinson-scrivener-tr" for mapping in mappings)
        assert all(
            any("\u0370" <= char <= "\u03ff" for char in str(word.get("woord") or ""))
            for word in verse["grondtekst"]
            ), f"Johannes 1:{verse['number']} bevat geen eenduidige Griekse TR-woordvorm"


def test_johannes_1_onderscheidt_vertaalde_en_niet_afzonderlijk_vertaalde_tr_woorden():
    data = json.loads((ROOT / "data" / "johannes" / "1.json").read_text(encoding="utf-8"))
    verses = {int(verse["number"]): verse for verse in data["verses"]}

    def mapping(verse, source_index):
        return next(
            item for item in verses[verse]["woordnummers"]
            if source_index in item.get("herkomst", {}).get("bronindices", [])
        )

    assert mapping(14, 0)["tekst"] == "En"
    assert mapping(14, 0)["status"] == "vertaald"
    assert mapping(18, 5)["tekst"] == "eniggeboren Zoon"
    assert mapping(18, 5)["status"] == "vertaald"
    assert mapping(12, 5)["tekst"] == ""
    assert mapping(12, 5)["status"] == "niet_afzonderlijk_weergegeven"

    first_was = next(
        mapping for mapping in data["verses"][0]["woordnummers"]
        if mapping.get("tekst") == "was" and mapping.get("voorkomen") == 1
    )
    assert first_was["strongs"] == ["G2258"]
    assert first_was["lemma_strongs"] == ["G1510"]

    assert data["verses"][37]["text2026"].endswith("zei tot hen:")
    assert data["verses"][38]["text2026"].startswith("Wat zoekt u?")
    assert data["verses"][51]["grondtekst"][-1]["strongs"] == "G444"


def test_generieke_tr_bron_leest_johannes_2_met_exacte_griekse_woordvormen():
    from scripts.rebuild_nt_tr_strongs import load_tr_chapter

    verses = load_tr_chapter(
        Path(r"C:\tmp\greektext-textus-receptus\parsed\JOH.UTR"),
        Path(r"C:\tmp\crosswire-kjv\kjv.osis.xml"),
        chapter=2,
        osis_book="John",
    )

    assert len(verses) == 25
    assert verses[1][0]["woord"] == "και"
    assert verses[1][0]["display_strong"] == "G2532"
    assert all(
        any("\u0370" <= char <= "\u03ff" for char in token["woord"])
        for tokens in verses.values() for token in tokens
    )


def test_generieke_tr_bron_bewaart_vergelijkende_vormstrong_naast_het_lemma():
    from scripts.rebuild_nt_tr_strongs import load_tr_chapter

    verses = load_tr_chapter(
        Path(r"C:\tmp\greektext-textus-receptus\parsed\JOH.UTR"),
        Path(r"C:\tmp\crosswire-kjv\kjv.osis.xml"),
        chapter=4,
        osis_book="John",
    )
    comparative = verses[1][11]
    assert comparative["woord"] == "πλειονας"
    assert comparative["lemma_strong"] == "G4183"
    assert comparative["display_strong"] == "G4119"


def test_tr_bron_behoudt_utr_lemma_bij_mattheus_21_8_vormpresentatie():
    from scripts.rebuild_nt_tr_strongs import load_tr_chapter
    verses = load_tr_chapter(Path(r"C:\tmp\greektext-textus-receptus\parsed\MT.UTR"), Path(r"C:\tmp\crosswire-kjv\kjv.osis.xml"), chapter=21, osis_book="Matt")
    token = verses[8][2]
    assert token["lemma_strong"] == "G4183"
    assert token["morphology"] == "A-NSM-S"
    assert token["display_strong"] == "G4118"


def test_tr_bron_herindexeert_osis_variantstroom_bij_mattheus_23_14():
    from scripts.rebuild_nt_tr_strongs import load_tr_chapter

    verses = load_tr_chapter(
        Path(r"C:\tmp\greektext-textus-receptus\parsed\MT.UTR"),
        Path(r"C:\tmp\crosswire-kjv\kjv.osis.xml"),
        chapter=23,
        osis_book="Matt",
    )

    assert len(verses[14]) == 20
    assert verses[14][0]["woord"] == "ουαι"
    assert verses[14][-1]["woord"] == "κριμα"


def test_tr_bron_behoudt_utr_lemma_bij_mattheus_26_45_vormpresentatie():
    from scripts.rebuild_nt_tr_strongs import load_tr_chapter

    verses = load_tr_chapter(
        Path(r"C:\tmp\greektext-textus-receptus\parsed\MT.UTR"),
        Path(r"C:\tmp\crosswire-kjv\kjv.osis.xml"),
        chapter=26,
        osis_book="Matt",
    )
    token = verses[45][11]
    assert token["woord"] == "λοιπον"
    assert token["lemma_strong"] == "G3062"
    assert token["morphology"] == "A-ASN"
    assert token["display_strong"] == "G3063"


def test_mattheus_21_publiceert_ieder_tr_token_precies_eenmaal():
    data = json.loads((ROOT / "data" / "mattheus" / "21.json").read_text(encoding="utf-8"))
    verses = {int(verse["number"]): verse for verse in data["verses"]}

    for number in range(1, 47):
        verse = verses[number]
        ground = verse.get("grondtekst", [])
        source_indices = [
            index
            for mapping in verse.get("woordnummers", [])
            for index in mapping.get("herkomst", {}).get("bronindices", [])
        ]
        assert ground, f"Mattheüs 21:{number} mist TR-grondtekst"
        assert sorted(source_indices) == list(range(len(ground)))
        assert len(set(source_indices)) == len(ground)
        assert all(mapping.get("reviewstatus") == "handmatig_gecontroleerd" for mapping in verse["woordnummers"])

    variant = next(
        mapping for mapping in verses[8]["woordnummers"]
        if 2 in mapping["herkomst"]["bronindices"]
    )
    assert variant["strongs"][variant["herkomst"]["bronindices"].index(2)] == "G4118"
    assert variant["lemma_strongs"][variant["herkomst"]["bronindices"].index(2)] == "G4183"
    shifted = next(
        mapping for mapping in verses[2]["woordnummers"]
        if mapping["herkomst"]["bronindices"] == [0, 1]
    )
    assert shifted["status"] == "niet_afzonderlijk_weergegeven"
    assert shifted["anker"] == "Ga"


def test_mattheus_22_publiceert_ieder_tr_token_precies_eenmaal():
    data = json.loads((ROOT / "data" / "mattheus" / "22.json").read_text(encoding="utf-8"))
    for verse in data["verses"]:
        ground = verse.get("grondtekst", [])
        source_indices = [
            index
            for mapping in verse.get("woordnummers", [])
            for index in mapping.get("herkomst", {}).get("bronindices", [])
        ]
        assert ground, f"Mattheüs 22:{verse['number']} mist TR-grondtekst"
        assert sorted(source_indices) == list(range(len(ground)))
        assert len(set(source_indices)) == len(ground)
        assert all(mapping.get("reviewstatus") == "handmatig_gecontroleerd" for mapping in verse["woordnummers"])


def test_mattheus_23_publiceert_ieder_tr_token_precies_eenmaal():
    data = json.loads((ROOT / "data" / "mattheus" / "23.json").read_text(encoding="utf-8"))
    for verse in data["verses"]:
        ground = verse.get("grondtekst", [])
        source_indices = [index for mapping in verse.get("woordnummers", []) for index in mapping.get("herkomst", {}).get("bronindices", [])]
        assert ground, f"Mattheüs 23:{verse['number']} mist TR-grondtekst"
        assert sorted(source_indices) == list(range(len(ground)))
        assert len(set(source_indices)) == len(ground)


def test_mattheus_24_publiceert_ieder_tr_token_precies_eenmaal():
    data = json.loads((ROOT / "data" / "mattheus" / "24.json").read_text(encoding="utf-8"))
    for verse in data["verses"]:
        ground = verse.get("grondtekst", [])
        source_indices = [index for mapping in verse.get("woordnummers", []) for index in mapping.get("herkomst", {}).get("bronindices", [])]
        assert ground, f"Mattheüs 24:{verse['number']} mist TR-grondtekst"
        assert sorted(source_indices) == list(range(len(ground)))
        assert len(set(source_indices)) == len(ground)


def test_mattheus_25_publiceert_ieder_tr_token_precies_eenmaal():
    data = json.loads((ROOT / "data" / "mattheus" / "25.json").read_text(encoding="utf-8"))
    for verse in data["verses"]:
        ground = verse.get("grondtekst", [])
        source_indices = [index for mapping in verse.get("woordnummers", []) for index in mapping.get("herkomst", {}).get("bronindices", [])]
        assert ground, f"Mattheüs 25:{verse['number']} mist TR-grondtekst"
        assert sorted(source_indices) == list(range(len(ground)))
        assert len(set(source_indices)) == len(ground)


def test_mattheus_26_publiceert_ieder_tr_token_precies_eenmaal():
    data = json.loads((ROOT / "data" / "mattheus" / "26.json").read_text(encoding="utf-8"))
    for verse in data["verses"]:
        ground = verse.get("grondtekst", [])
        source_indices = [index for mapping in verse.get("woordnummers", []) for index in mapping.get("herkomst", {}).get("bronindices", [])]
        assert ground, f"Mattheüs 26:{verse['number']} mist TR-grondtekst"
        assert sorted(source_indices) == list(range(len(ground)))
        assert len(set(source_indices)) == len(ground)


def test_mattheus_27_publiceert_ieder_tr_token_precies_eenmaal():
    data = json.loads((ROOT / "data" / "mattheus" / "27.json").read_text(encoding="utf-8"))
    for verse in data["verses"]:
        ground = verse.get("grondtekst", [])
        source_indices = [index for mapping in verse.get("woordnummers", []) for index in mapping.get("herkomst", {}).get("bronindices", [])]
        assert ground, f"Mattheüs 27:{verse['number']} mist TR-grondtekst"
        assert sorted(source_indices) == list(range(len(ground)))
        assert len(set(source_indices)) == len(ground)


def test_mattheus_28_publiceert_ieder_tr_token_precies_eenmaal():
    data = json.loads((ROOT / "data" / "mattheus" / "28.json").read_text(encoding="utf-8"))
    for verse in data["verses"]:
        ground = verse.get("grondtekst", [])
        source_indices = [index for mapping in verse.get("woordnummers", []) for index in mapping.get("herkomst", {}).get("bronindices", [])]
        assert ground, f"Mattheüs 28:{verse['number']} mist TR-grondtekst"
        assert sorted(source_indices) == list(range(len(ground)))
        assert len(set(source_indices)) == len(ground)


def test_generieke_tr_bron_leest_markus_1_van_gepinde_utr():
    from scripts.rebuild_nt_tr_strongs import load_tr_chapter
    verses = load_tr_chapter(
        Path(r"C:\tmp\greektext-textus-receptus\parsed\MR.UTR"),
        Path(r"C:\tmp\crosswire-kjv\kjv.osis.xml"),
        chapter=1,
        osis_book="Mark",
    )
    assert len(verses) == 45


def test_generieke_tr_bron_leest_handelingen_1_van_gepinde_utr():
    from scripts.rebuild_nt_tr_strongs import load_tr_chapter

    verses = load_tr_chapter(
        Path(r"C:\tmp\greektext-textus-receptus\parsed\AC.UTR"),
        Path(r"C:\tmp\crosswire-kjv\kjv.osis.xml"),
        chapter=1,
        osis_book="Acts",
    )

    assert len(verses) == 26
    assert sum(len(tokens) for tokens in verses.values()) == 515
    assert verses[1][0]["woord"] == "\u03c4\u03bf\u03bd"


def test_osis_parser_negeert_niet_utr_lezing_met_n_bronindex_in_romeinen_1_3():
    from scripts.rebuild_nt_tr_strongs import parse_osis_chapter

    verses = parse_osis_chapter(Path(r"C:\tmp\crosswire-kjv\kjv.osis.xml"), "Rom", 1)

    assert sorted(verses[3]) == list(range(11))
    assert verses[3][0]["lemma_strong"] == "G4012"


def test_markus_1_publiceert_ieder_tr_token_precies_eenmaal():
    data = json.loads((ROOT / "data" / "markus" / "1.json").read_text(encoding="utf-8"))
    for verse in data["verses"]:
        ground = verse.get("grondtekst", [])
        source_indices = [index for mapping in verse.get("woordnummers", []) for index in mapping.get("herkomst", {}).get("bronindices", [])]
        assert ground, f"Markus 1:{verse['number']} mist TR-grondtekst"
        assert sorted(source_indices) == list(range(len(ground)))
        assert len(set(source_indices)) == len(ground)


def test_markus_2_publiceert_ieder_tr_token_precies_eenmaal():
    data = json.loads((ROOT / "data" / "markus" / "2.json").read_text(encoding="utf-8"))
    for verse in data["verses"]:
        ground = verse.get("grondtekst", [])
        source_indices = [index for mapping in verse.get("woordnummers", []) for index in mapping.get("herkomst", {}).get("bronindices", [])]
        assert ground, f"Markus 2:{verse['number']} mist TR-grondtekst"
        assert sorted(source_indices) == list(range(len(ground)))
        assert len(set(source_indices)) == len(ground)


def test_markus_3_publiceert_ieder_tr_token_precies_eenmaal():
    data = json.loads((ROOT / "data" / "markus" / "3.json").read_text(encoding="utf-8"))
    for verse in data["verses"]:
        ground = verse.get("grondtekst", [])
        source_indices = [index for mapping in verse.get("woordnummers", []) for index in mapping.get("herkomst", {}).get("bronindices", [])]
        assert ground, f"Markus 3:{verse['number']} mist TR-grondtekst"
        assert sorted(source_indices) == list(range(len(ground)))
        assert len(set(source_indices)) == len(ground)


def test_markus_4_publiceert_ieder_tr_token_precies_eenmaal():
    data = json.loads((ROOT / "data" / "markus" / "4.json").read_text(encoding="utf-8"))
    for verse in data["verses"]:
        ground = verse.get("grondtekst", [])
        source_indices = [index for mapping in verse.get("woordnummers", []) for index in mapping.get("herkomst", {}).get("bronindices", [])]
        assert ground, f"Markus 4:{verse['number']} mist TR-grondtekst"
        assert sorted(source_indices) == list(range(len(ground)))
        assert len(set(source_indices)) == len(ground)


def test_markus_5_publiceert_ieder_tr_token_precies_eenmaal():
    data = json.loads((ROOT / "data" / "markus" / "5.json").read_text(encoding="utf-8"))
    for verse in data["verses"]:
        ground = verse.get("grondtekst", [])
        source_indices = [index for mapping in verse.get("woordnummers", []) for index in mapping.get("herkomst", {}).get("bronindices", [])]
        assert ground, f"Markus 5:{verse['number']} mist TR-grondtekst"
        assert sorted(source_indices) == list(range(len(ground)))
        assert len(set(source_indices)) == len(ground)


def test_markus_6_publiceert_ieder_tr_token_precies_eenmaal():
    data = json.loads((ROOT / "data" / "markus" / "6.json").read_text(encoding="utf-8"))
    for verse in data["verses"]:
        ground = verse.get("grondtekst", [])
        source_indices = [index for mapping in verse.get("woordnummers", []) for index in mapping.get("herkomst", {}).get("bronindices", [])]
        assert ground, f"Markus 6:{verse['number']} mist TR-grondtekst"
        assert sorted(source_indices) == list(range(len(ground)))
        assert len(set(source_indices)) == len(ground)


def test_markus_7_publiceert_ieder_tr_token_precies_eenmaal():
    data = json.loads((ROOT / "data" / "markus" / "7.json").read_text(encoding="utf-8"))
    for verse in data["verses"]:
        ground = verse.get("grondtekst", [])
        source_indices = [index for mapping in verse.get("woordnummers", []) for index in mapping.get("herkomst", {}).get("bronindices", [])]
        assert ground and sorted(source_indices) == list(range(len(ground))) and len(set(source_indices)) == len(ground)


def test_markus_8_publiceert_ieder_tr_token_precies_eenmaal():
    data = json.loads((ROOT / "data" / "markus" / "8.json").read_text(encoding="utf-8"))
    for verse in data["verses"]:
        ground = verse.get("grondtekst", [])
        source_indices = [index for mapping in verse.get("woordnummers", []) for index in mapping.get("herkomst", {}).get("bronindices", [])]
        assert ground and sorted(source_indices) == list(range(len(ground))) and len(set(source_indices)) == len(ground)


def test_markus_9_publiceert_ieder_tr_token_precies_eenmaal():
    data = json.loads((ROOT / "data" / "markus" / "9.json").read_text(encoding="utf-8"))
    for verse in data["verses"]:
        ground = verse.get("grondtekst", [])
        source_indices = [index for mapping in verse.get("woordnummers", []) for index in mapping.get("herkomst", {}).get("bronindices", [])]
        assert ground and sorted(source_indices) == list(range(len(ground))) and len(set(source_indices)) == len(ground)


def test_markus_10_publiceert_ieder_tr_token_precies_eenmaal():
    data = json.loads((ROOT / "data" / "markus" / "10.json").read_text(encoding="utf-8"))
    for verse in data["verses"]:
        ground = verse.get("grondtekst", [])
        source_indices = [index for mapping in verse.get("woordnummers", []) for index in mapping.get("herkomst", {}).get("bronindices", [])]
        assert ground and sorted(source_indices) == list(range(len(ground))) and len(set(source_indices)) == len(ground)


def test_markus_11_publiceert_ieder_tr_token_precies_eenmaal():
    data = json.loads((ROOT / "data" / "markus" / "11.json").read_text(encoding="utf-8"))
    for verse in data["verses"]:
        ground = verse.get("grondtekst", [])
        source_indices = [index for mapping in verse.get("woordnummers", []) for index in mapping.get("herkomst", {}).get("bronindices", [])]
        assert ground and sorted(source_indices) == list(range(len(ground))) and len(set(source_indices)) == len(ground)


def test_markus_12_publiceert_ieder_tr_token_precies_eenmaal():
    data = json.loads((ROOT / "data" / "markus" / "12.json").read_text(encoding="utf-8"))
    for verse in data["verses"]:
        ground = verse.get("grondtekst", [])
        source_indices = [index for mapping in verse.get("woordnummers", []) for index in mapping.get("herkomst", {}).get("bronindices", [])]
        assert ground and sorted(source_indices) == list(range(len(ground))) and len(set(source_indices)) == len(ground)


def test_markus_13_publiceert_ieder_tr_token_precies_eenmaal():
    data = json.loads((ROOT / "data" / "markus" / "13.json").read_text(encoding="utf-8"))
    for verse in data["verses"]:
        indices = [i for m in verse.get("woordnummers", []) for i in m.get("herkomst", {}).get("bronindices", [])]
        assert verse.get("grondtekst") and sorted(indices) == list(range(len(verse["grondtekst"]))) and len(indices) == len(set(indices))


def test_markus_14_publiceert_ieder_tr_token_precies_eenmaal():
    data = json.loads((ROOT / "data" / "markus" / "14.json").read_text(encoding="utf-8"))
    for verse in data["verses"]:
        indices = [i for m in verse.get("woordnummers", []) for i in m.get("herkomst", {}).get("bronindices", [])]
        assert verse.get("grondtekst") and sorted(indices) == list(range(len(verse["grondtekst"]))) and len(indices) == len(set(indices))


def test_markus_15_publiceert_ieder_tr_token_precies_eenmaal():
    data = json.loads((ROOT / "data" / "markus" / "15.json").read_text(encoding="utf-8"))
    for verse in data["verses"]:
        indices = [i for m in verse.get("woordnummers", []) for i in m.get("herkomst", {}).get("bronindices", [])]
        assert verse.get("grondtekst") and sorted(indices) == list(range(len(verse["grondtekst"]))) and len(indices) == len(set(indices))


def test_markus_16_publiceert_ieder_tr_token_precies_eenmaal():
    data = json.loads((ROOT / "data" / "markus" / "16.json").read_text(encoding="utf-8"))
    for verse in data["verses"]:
        indices = [i for m in verse.get("woordnummers", []) for i in m.get("herkomst", {}).get("bronindices", [])]
        assert verse.get("grondtekst") and sorted(indices) == list(range(len(verse["grondtekst"]))) and len(indices) == len(set(indices))


def test_lukas_1_publiceert_ieder_tr_token_precies_eenmaal():
    data = json.loads((ROOT / "data" / "lukas" / "1.json").read_text(encoding="utf-8"))
    for verse in data["verses"]:
        indices = [i for m in verse.get("woordnummers", []) for i in m.get("herkomst", {}).get("bronindices", [])]
        assert verse.get("grondtekst") and sorted(indices) == list(range(len(verse["grondtekst"]))) and len(indices) == len(set(indices))


def test_lukas_2_publiceert_ieder_tr_token_precies_eenmaal():
    data = json.loads((ROOT / "data" / "lukas" / "2.json").read_text(encoding="utf-8"))
    for verse in data["verses"]:
        indices = [i for m in verse.get("woordnummers", []) for i in m.get("herkomst", {}).get("bronindices", [])]
        assert verse.get("grondtekst") and sorted(indices) == list(range(len(verse["grondtekst"]))) and len(indices) == len(set(indices))


def test_lukas_3_publiceert_ieder_tr_token_precies_eenmaal():
    data = json.loads((ROOT / "data" / "lukas" / "3.json").read_text(encoding="utf-8"))
    for verse in data["verses"]:
        indices = [i for m in verse.get("woordnummers", []) for i in m.get("herkomst", {}).get("bronindices", [])]
        assert verse.get("grondtekst") and sorted(indices) == list(range(len(verse["grondtekst"]))) and len(indices) == len(set(indices))


def test_lukas_4_publiceert_ieder_tr_token_precies_eenmaal():
    data = json.loads((ROOT / "data" / "lukas" / "4.json").read_text(encoding="utf-8"))
    for verse in data["verses"]:
        indices = [i for m in verse.get("woordnummers", []) for i in m.get("herkomst", {}).get("bronindices", [])]
        assert verse.get("grondtekst") and sorted(indices) == list(range(len(verse["grondtekst"]))) and len(indices) == len(set(indices))


def test_lukas_5_publiceert_ieder_tr_token_precies_eenmaal():
    data = json.loads((ROOT / "data" / "lukas" / "5.json").read_text(encoding="utf-8"))
    for verse in data["verses"]:
        indices = [i for m in verse.get("woordnummers", []) for i in m.get("herkomst", {}).get("bronindices", [])]
        assert verse.get("grondtekst") and sorted(indices) == list(range(len(verse["grondtekst"]))) and len(indices) == len(set(indices))


def test_lukas_6_publiceert_ieder_tr_token_precies_eenmaal():
    data = json.loads((ROOT / "data" / "lukas" / "6.json").read_text(encoding="utf-8"))
    for verse in data["verses"]:
        indices = [i for m in verse.get("woordnummers", []) for i in m.get("herkomst", {}).get("bronindices", [])]
        assert verse.get("grondtekst") and sorted(indices) == list(range(len(verse["grondtekst"]))) and len(indices) == len(set(indices))


def test_lukas_7_publiceert_ieder_tr_token_precies_eenmaal():
    data = json.loads((ROOT / "data" / "lukas" / "7.json").read_text(encoding="utf-8"))
    for verse in data["verses"]:
        indices = [i for m in verse.get("woordnummers", []) for i in m.get("herkomst", {}).get("bronindices", [])]
        assert verse.get("grondtekst") and sorted(indices) == list(range(len(verse["grondtekst"]))) and len(indices) == len(set(indices))


def test_lukas_8_publiceert_ieder_tr_token_precies_eenmaal():
    data = json.loads((ROOT / "data" / "lukas" / "8.json").read_text(encoding="utf-8"))
    for verse in data["verses"]:
        indices = [i for m in verse.get("woordnummers", []) for i in m.get("herkomst", {}).get("bronindices", [])]
        assert verse.get("grondtekst") and sorted(indices) == list(range(len(verse["grondtekst"]))) and len(indices) == len(set(indices))


def test_lukas_9_publiceert_ieder_tr_token_precies_eenmaal():
    data = json.loads((ROOT / "data" / "lukas" / "9.json").read_text(encoding="utf-8"))
    for verse in data["verses"]:
        indices = [i for m in verse.get("woordnummers", []) for i in m.get("herkomst", {}).get("bronindices", [])]
        assert verse.get("grondtekst") and sorted(indices) == list(range(len(verse["grondtekst"]))) and len(indices) == len(set(indices))


def test_lukas_10_publiceert_ieder_tr_token_precies_eenmaal():
    data = json.loads((ROOT / "data" / "lukas" / "10.json").read_text(encoding="utf-8"))
    for verse in data["verses"]:
        indices = [i for m in verse.get("woordnummers", []) for i in m.get("herkomst", {}).get("bronindices", [])]
        assert verse.get("grondtekst") and sorted(indices) == list(range(len(verse["grondtekst"]))) and len(indices) == len(set(indices))


def test_lukas_11_publiceert_ieder_tr_token_precies_eenmaal():
    data = json.loads((ROOT / "data" / "lukas" / "11.json").read_text(encoding="utf-8"))
    for verse in data["verses"]:
        indices = [i for m in verse.get("woordnummers", []) for i in m.get("herkomst", {}).get("bronindices", [])]
        assert verse.get("grondtekst") and sorted(indices) == list(range(len(verse["grondtekst"]))) and len(indices) == len(set(indices))


def test_lukas_12_publiceert_ieder_tr_token_precies_eenmaal():
    data = json.loads((ROOT / "data" / "lukas" / "12.json").read_text(encoding="utf-8"))
    for verse in data["verses"]:
        indices = [i for m in verse.get("woordnummers", []) for i in m.get("herkomst", {}).get("bronindices", [])]
        assert verse.get("grondtekst") and sorted(indices) == list(range(len(verse["grondtekst"]))) and len(indices) == len(set(indices))


def test_lukas_13_publiceert_ieder_tr_token_precies_eenmaal():
    data = json.loads((ROOT / "data" / "lukas" / "13.json").read_text(encoding="utf-8"))
    for verse in data["verses"]:
        indices = [i for m in verse.get("woordnummers", []) for i in m.get("herkomst", {}).get("bronindices", [])]
        assert verse.get("grondtekst") and sorted(indices) == list(range(len(verse["grondtekst"]))) and len(indices) == len(set(indices))


def test_lukas_14_publiceert_ieder_tr_token_precies_eenmaal():
    data = json.loads((ROOT / "data" / "lukas" / "14.json").read_text(encoding="utf-8"))
    for verse in data["verses"]:
        indices = [i for m in verse.get("woordnummers", []) for i in m.get("herkomst", {}).get("bronindices", [])]
        assert verse.get("grondtekst") and sorted(indices) == list(range(len(verse["grondtekst"]))) and len(indices) == len(set(indices))


def test_lukas_15_publiceert_ieder_tr_token_precies_eenmaal():
    data = json.loads((ROOT / "data" / "lukas" / "15.json").read_text(encoding="utf-8"))
    for verse in data["verses"]:
        indices = [i for m in verse.get("woordnummers", []) for i in m.get("herkomst", {}).get("bronindices", [])]
        assert verse.get("grondtekst") and sorted(indices) == list(range(len(verse["grondtekst"]))) and len(indices) == len(set(indices))


def test_lukas_16_publiceert_ieder_tr_token_precies_eenmaal():
    data = json.loads((ROOT / "data" / "lukas" / "16.json").read_text(encoding="utf-8"))
    for verse in data["verses"]:
        indices = [i for m in verse.get("woordnummers", []) for i in m.get("herkomst", {}).get("bronindices", [])]
        assert verse.get("grondtekst") and sorted(indices) == list(range(len(verse["grondtekst"]))) and len(indices) == len(set(indices))


def test_lukas_17_publiceert_ieder_tr_token_precies_eenmaal():
    data = json.loads((ROOT / "data" / "lukas" / "17.json").read_text(encoding="utf-8"))
    for verse in data["verses"]:
        indices = [i for m in verse.get("woordnummers", []) for i in m.get("herkomst", {}).get("bronindices", [])]
        assert verse.get("grondtekst") and sorted(indices) == list(range(len(verse["grondtekst"]))) and len(indices) == len(set(indices))


def test_lukas_18_publiceert_ieder_tr_token_precies_eenmaal():
    data = json.loads((ROOT / "data" / "lukas" / "18.json").read_text(encoding="utf-8"))
    for verse in data["verses"]:
        indices = [i for m in verse.get("woordnummers", []) for i in m.get("herkomst", {}).get("bronindices", [])]
        assert verse.get("grondtekst") and sorted(indices) == list(range(len(verse["grondtekst"]))) and len(indices) == len(set(indices))


def test_lukas_19_publiceert_ieder_tr_token_precies_eenmaal():
    data = json.loads((ROOT / "data" / "lukas" / "19.json").read_text(encoding="utf-8"))
    for verse in data["verses"]:
        indices = [i for m in verse.get("woordnummers", []) for i in m.get("herkomst", {}).get("bronindices", [])]
        assert verse.get("grondtekst") and sorted(indices) == list(range(len(verse["grondtekst"]))) and len(indices) == len(set(indices))


def test_lukas_20_publiceert_ieder_tr_token_precies_eenmaal():
    data = json.loads((ROOT / "data" / "lukas" / "20.json").read_text(encoding="utf-8"))
    for verse in data["verses"]:
        indices = [i for m in verse.get("woordnummers", []) for i in m.get("herkomst", {}).get("bronindices", [])]
        assert verse.get("grondtekst") and sorted(indices) == list(range(len(verse["grondtekst"]))) and len(indices) == len(set(indices))


def test_lukas_21_publiceert_ieder_tr_token_precies_eenmaal():
    data = json.loads((ROOT / "data" / "lukas" / "21.json").read_text(encoding="utf-8"))
    for verse in data["verses"]:
        indices = [i for m in verse.get("woordnummers", []) for i in m.get("herkomst", {}).get("bronindices", [])]
        assert verse.get("grondtekst") and sorted(indices) == list(range(len(verse["grondtekst"]))) and len(indices) == len(set(indices))


def test_lukas_22_publiceert_ieder_tr_token_precies_eenmaal():
    data = json.loads((ROOT / "data" / "lukas" / "22.json").read_text(encoding="utf-8"))
    for verse in data["verses"]:
        indices = [i for m in verse.get("woordnummers", []) for i in m.get("herkomst", {}).get("bronindices", [])]
        assert verse.get("grondtekst") and sorted(indices) == list(range(len(verse["grondtekst"]))) and len(indices) == len(set(indices))


def test_lukas_23_publiceert_ieder_tr_token_precies_eenmaal():
    data = json.loads((ROOT / "data" / "lukas" / "23.json").read_text(encoding="utf-8"))
    for verse in data["verses"]:
        indices = [i for m in verse.get("woordnummers", []) for i in m.get("herkomst", {}).get("bronindices", [])]
        assert verse.get("grondtekst") and sorted(indices) == list(range(len(verse["grondtekst"]))) and len(indices) == len(set(indices))


def test_lukas_24_publiceert_ieder_tr_token_precies_eenmaal():
    data = json.loads((ROOT / "data" / "lukas" / "24.json").read_text(encoding="utf-8"))
    for verse in data["verses"]:
        indices = [i for m in verse.get("woordnummers", []) for i in m.get("herkomst", {}).get("bronindices", [])]
        assert verse.get("grondtekst") and sorted(indices) == list(range(len(verse["grondtekst"]))) and len(indices) == len(set(indices))


def test_handelingen_1_publiceert_ieder_tr_token_precies_eenmaal():
    data = json.loads((ROOT / "data" / "handelingen" / "1.json").read_text(encoding="utf-8"))
    for verse in data["verses"]:
        indices = [i for m in verse.get("woordnummers", []) for i in m.get("herkomst", {}).get("bronindices", [])]
        assert verse.get("grondtekst") and sorted(indices) == list(range(len(verse["grondtekst"]))) and len(indices) == len(set(indices))


def test_handelingen_2_publiceert_ieder_tr_token_precies_eenmaal():
    data = json.loads((ROOT / "data" / "handelingen" / "2.json").read_text(encoding="utf-8"))
    for verse in data["verses"]:
        indices = [i for m in verse.get("woordnummers", []) for i in m.get("herkomst", {}).get("bronindices", [])]
        assert verse.get("grondtekst") and sorted(indices) == list(range(len(verse["grondtekst"]))) and len(indices) == len(set(indices))


def test_handelingen_3_publiceert_ieder_tr_token_precies_eenmaal():
    data = json.loads((ROOT / "data" / "handelingen" / "3.json").read_text(encoding="utf-8"))
    for verse in data["verses"]:
        indices = [i for m in verse.get("woordnummers", []) for i in m.get("herkomst", {}).get("bronindices", [])]
        assert verse.get("grondtekst") and sorted(indices) == list(range(len(verse["grondtekst"]))) and len(indices) == len(set(indices))


def test_handelingen_4_publiceert_ieder_tr_token_precies_eenmaal():
    data = json.loads((ROOT / "data" / "handelingen" / "4.json").read_text(encoding="utf-8"))
    for verse in data["verses"]:
        indices = [i for m in verse.get("woordnummers", []) for i in m.get("herkomst", {}).get("bronindices", [])]
        assert verse.get("grondtekst") and sorted(indices) == list(range(len(verse["grondtekst"]))) and len(indices) == len(set(indices))


def test_handelingen_5_publiceert_ieder_tr_token_precies_eenmaal():
    data = json.loads((ROOT / "data" / "handelingen" / "5.json").read_text(encoding="utf-8"))
    for verse in data["verses"]:
        indices = [i for m in verse.get("woordnummers", []) for i in m.get("herkomst", {}).get("bronindices", [])]
        assert verse.get("grondtekst") and sorted(indices) == list(range(len(verse["grondtekst"]))) and len(indices) == len(set(indices))


def test_handelingen_6_publiceert_ieder_tr_token_precies_eenmaal():
    data = json.loads((ROOT / "data" / "handelingen" / "6.json").read_text(encoding="utf-8"))
    for verse in data["verses"]:
        indices = [i for m in verse.get("woordnummers", []) for i in m.get("herkomst", {}).get("bronindices", [])]
        assert verse.get("grondtekst") and sorted(indices) == list(range(len(verse["grondtekst"]))) and len(indices) == len(set(indices))


def test_handelingen_7_publiceert_ieder_tr_token_precies_eenmaal():
    data = json.loads((ROOT / "data" / "handelingen" / "7.json").read_text(encoding="utf-8"))
    for verse in data["verses"]:
        indices = [i for m in verse.get("woordnummers", []) for i in m.get("herkomst", {}).get("bronindices", [])]
        assert verse.get("grondtekst") and sorted(indices) == list(range(len(verse["grondtekst"]))) and len(indices) == len(set(indices))


@pytest.mark.parametrize("chapter", range(8, 29))
def test_handelingen_overige_hoofdstukken_publiceren_ieder_tr_token_precies_eenmaal(chapter):
    data = json.loads((ROOT / "data" / "handelingen" / f"{chapter}.json").read_text(encoding="utf-8"))
    for verse in data["verses"]:
        indices = [i for mapping in verse.get("woordnummers", []) for i in mapping.get("herkomst", {}).get("bronindices", [])]
        assert verse.get("grondtekst") and sorted(indices) == list(range(len(verse["grondtekst"]))) and len(indices) == len(set(indices))


@pytest.mark.parametrize("chapter", range(1, 17))
def test_romeinen_hoofdstukken_publiceren_ieder_tr_token_precies_eenmaal(chapter):
    data = json.loads((ROOT / "data" / "romeinen" / f"{chapter}.json").read_text(encoding="utf-8"))
    for verse in data["verses"]:
        indices = [
            index
            for mapping in verse.get("woordnummers", [])
            for index in mapping.get("herkomst", {}).get(
                "grondindices",
                mapping.get("herkomst", {}).get("bronindices", []),
            )
        ]
        if not verse.get("grondtekst"):
            assert not indices
            continue
        assert sorted(indices) == list(range(len(verse["grondtekst"]))) and len(indices) == len(set(indices))


@pytest.mark.parametrize("chapter", range(1, 17))
def test_1korinthiers_hoofdstukken_publiceren_ieder_tr_token_precies_eenmaal(chapter):
    data = json.loads((ROOT / "data" / "1korinthiers" / f"{chapter}.json").read_text(encoding="utf-8"))
    for verse in data["verses"]:
        indices = [
            index
            for mapping in verse.get("woordnummers", [])
            for index in mapping.get("herkomst", {}).get(
                "grondindices",
                mapping.get("herkomst", {}).get("bronindices", []),
            )
        ]
        if not verse.get("grondtekst"):
            assert not indices
            continue
        assert sorted(indices) == list(range(len(verse["grondtekst"]))) and len(indices) == len(set(indices))


@pytest.mark.parametrize("chapter", range(1, 14))
def test_2korinthiers_hoofdstukken_publiceren_ieder_tr_token_precies_eenmaal(chapter):
    data = json.loads((ROOT / "data" / "2korinthiers" / f"{chapter}.json").read_text(encoding="utf-8"))
    for verse in data["verses"]:
        indices = [
            index
            for mapping in verse.get("woordnummers", [])
            for index in mapping.get("herkomst", {}).get(
                "grondindices",
                mapping.get("herkomst", {}).get("bronindices", []),
            )
        ]
        if not verse.get("grondtekst"):
            assert not indices
            continue
        assert sorted(indices) == list(range(len(verse["grondtekst"]))) and len(indices) == len(set(indices))


@pytest.mark.parametrize("chapter", range(1, 7))
def test_galaten_hoofdstukken_publiceren_ieder_tr_token_precies_eenmaal(chapter):
    data = json.loads((ROOT / "data" / "galaten" / f"{chapter}.json").read_text(encoding="utf-8"))
    for verse in data["verses"]:
        indices = [
            i
            for mapping in verse.get("woordnummers", [])
            for i in mapping.get("herkomst", {}).get(
                "grondindices",
                mapping.get("herkomst", {}).get("bronindices", []),
            )
        ]
        if not verse.get("grondtekst"):
            assert not indices
            continue
        assert sorted(indices) == list(range(len(verse["grondtekst"]))) and len(indices) == len(set(indices))


@pytest.mark.parametrize("chapter", range(1, 7))
def test_efeziers_hoofdstukken_publiceren_ieder_tr_token_precies_eenmaal(chapter):
    data = json.loads((ROOT / "data" / "efeziers" / f"{chapter}.json").read_text(encoding="utf-8"))
    for verse in data["verses"]:
        indices = [
            i
            for mapping in verse.get("woordnummers", [])
            for i in mapping.get("herkomst", {}).get(
                "grondindices", mapping.get("herkomst", {}).get("bronindices", [])
            )
        ]
        if not verse.get("grondtekst"):
            assert not indices
            continue
        assert sorted(indices) == list(range(len(verse["grondtekst"]))) and len(indices) == len(set(indices))


@pytest.mark.parametrize("chapter", range(1, 5))
def test_filippenzen_hoofdstukken_publiceren_ieder_tr_token_precies_eenmaal(chapter):
    data = json.loads((ROOT / "data" / "filippenzen" / f"{chapter}.json").read_text(encoding="utf-8"))
    for verse in data["verses"]:
        indices = [i for mapping in verse.get("woordnummers", []) for i in mapping.get("herkomst", {}).get("bronindices", [])]
        if not verse.get("grondtekst"):
            assert not indices
            continue
        assert sorted(indices) == list(range(len(verse["grondtekst"]))) and len(indices) == len(set(indices))


def test_generieke_tr_bron_kiest_bij_johannes_5_5_de_osis_variantstroom():
    from scripts.rebuild_nt_tr_strongs import load_tr_chapter

    verses = load_tr_chapter(
        Path(r"C:\tmp\greektext-textus-receptus\parsed\JOH.UTR"),
        Path(r"C:\tmp\crosswire-kjv\kjv.osis.xml"),
        chapter=5,
        osis_book="John",
    )

    assert len(verses[5]) == 13
    assert verses[5][5]["woord"] == "τριακοντα"
    assert [token["display_strong"] for token in verses[5][5:9]] == [
        "G5144", "G2532", "G3638", "G2094",
    ]


def test_generieke_tr_bron_vult_johannes_9_21_bronvast_aan_uit_osis():
    from scripts.rebuild_nt_tr_strongs import load_tr_chapter

    verses = load_tr_chapter(
        Path(r"C:\tmp\greektext-textus-receptus\parsed\JOH.UTR"),
        Path(r"C:\tmp\crosswire-kjv\kjv.osis.xml"),
        chapter=9,
        osis_book="John",
    )

    assert len(verses[21]) == 24
    assert verses[21][22]["woord"] == "αυτου"
    assert verses[21][22]["display_strong"] == "G848"
    assert verses[21][22]["bronstatus"] == "osis_aanvulling"


def test_johannes_2_publiceert_ieder_tr_token_precies_eenmaal():
    data = json.loads((ROOT / "data" / "johannes" / "2.json").read_text(encoding="utf-8"))
    assert len(data["verses"]) == 25
    for verse in data["verses"]:
        ground = verse.get("grondtekst", [])
        mappings = verse.get("woordnummers", [])
        source_indices = [
            index for mapping in mappings
            for index in mapping.get("herkomst", {}).get("bronindices", [])
        ]
        assert ground, f"Johannes 2:{verse['number']} mist TR-grondtekst"
        assert len(source_indices) == len(ground)
        assert sorted(source_indices) == list(range(len(ground)))
        assert all(mapping.get("reviewstatus") == "handmatig_gecontroleerd" for mapping in mappings)


def test_johannes_3_publiceert_ieder_tr_token_precies_eenmaal():
    data = json.loads((ROOT / "data" / "johannes" / "3.json").read_text(encoding="utf-8"))
    assert len(data["verses"]) == 36
    assert sum(len(verse.get("grondtekst", [])) for verse in data["verses"]) == 672
    for verse in data["verses"]:
        ground = verse.get("grondtekst", [])
        mappings = verse.get("woordnummers", [])
        source_indices = [
            index for mapping in mappings
            for index in mapping.get("herkomst", {}).get("bronindices", [])
        ]
        assert sorted(source_indices) == list(range(len(ground)))
        assert len(set(source_indices)) == len(ground)
        assert all(mapping.get("reviewstatus") == "handmatig_gecontroleerd" for mapping in mappings)


def test_johannes_4_publiceert_ieder_tr_token_precies_eenmaal():
    data = json.loads((ROOT / "data" / "johannes" / "4.json").read_text(encoding="utf-8"))
    reviewed = data["verses"]
    assert sum(len(verse.get("grondtekst", [])) for verse in reviewed) == 953
    for verse in reviewed:
        ground = verse.get("grondtekst", [])
        mappings = verse.get("woordnummers", [])
        source_indices = [index for item in mappings for index in item["herkomst"]["bronindices"]]
        assert sorted(source_indices) == list(range(len(ground)))
        assert len(set(source_indices)) == len(ground)


def test_johannes_5_publiceert_ieder_tr_token_precies_eenmaal():
    data = json.loads((ROOT / "data" / "johannes" / "5.json").read_text(encoding="utf-8"))
    reviewed = data["verses"]
    assert sum(len(verse.get("grondtekst", [])) for verse in reviewed) == 832
    for verse in reviewed:
        ground = verse.get("grondtekst", [])
        mappings = verse.get("woordnummers", [])
        source_indices = [index for item in mappings for index in item["herkomst"]["bronindices"]]
        assert sorted(source_indices) == list(range(len(ground)))
        assert len(set(source_indices)) == len(ground)
        # Verzen die van een versanker naar woordniveau zijn uitgelijnd
        # (scripts/woordnummers_uitlijnen.py) dragen eerlijk de status
        # automatisch_hoog_vertrouwen tot een mens ze nakijkt.
        assert all(
            item.get("reviewstatus") == "handmatig_gecontroleerd"
            or (item.get("status") == "uitgelijnd" and item.get("reviewstatus") == "automatisch_hoog_vertrouwen")
            for item in mappings
        )


def test_johannes_6_publiceert_ieder_tr_token_precies_eenmaal():
    data = json.loads((ROOT / "data" / "johannes" / "6.json").read_text(encoding="utf-8"))
    reviewed = data["verses"]
    assert len(reviewed) == 71
    assert sum(len(verse.get("grondtekst", [])) for verse in reviewed) == 1284
    for verse in reviewed:
        ground = verse.get("grondtekst", [])
        mappings = verse.get("woordnummers", [])
        source_indices = [index for item in mappings for index in item["herkomst"]["bronindices"]]
        assert sorted(source_indices) == list(range(len(ground)))
        assert len(set(source_indices)) == len(ground)


def test_johannes_7_publiceert_ieder_tr_token_precies_eenmaal():
    data = json.loads((ROOT / "data" / "johannes" / "7.json").read_text(encoding="utf-8"))
    reviewed = data["verses"]
    assert len(reviewed) == 53
    assert sum(len(verse.get("grondtekst", [])) for verse in reviewed) == 873
    for verse in reviewed:
        ground = verse.get("grondtekst", [])
        mappings = verse.get("woordnummers", [])
        source_indices = [index for item in mappings for index in item["herkomst"]["bronindices"]]
        assert sorted(source_indices) == list(range(len(ground)))
        assert len(set(source_indices)) == len(ground)


def test_johannes_8_publiceert_tokens_met_traceerbare_versgrensafwijking():
    data = json.loads((ROOT / "data" / "johannes" / "8.json").read_text(encoding="utf-8"))
    review = json.loads((ROOT / "data" / "woordnummers-review" / "johannes-8.json").read_text(encoding="utf-8"))
    reviewed = data["verses"]
    assert len(reviewed) == 59
    assert sum(len(verse.get("grondtekst", [])) for verse in reviewed) == 1115
    assert review["verses"]["3"]["ongemapt"][0]["reden"] == "versgrens_afwijking"
    assert review["verses"]["3"]["ongemapt"][0]["bronindices"] == [13, 14, 15, 16, 17]
    for verse in reviewed:
        number = str(verse["number"])
        ground = verse.get("grondtekst", [])
        mapped = [index for item in verse.get("woordnummers", []) for index in item["herkomst"]["bronindices"]]
        excluded = [index for item in review["verses"][number]["ongemapt"] for index in item["bronindices"]]
        assert sorted(mapped + excluded) == list(range(len(ground)))
        assert len(set(mapped + excluded)) == len(ground)


def test_johannes_9_publiceert_ieder_tr_token_precies_eenmaal():
    data = json.loads((ROOT / "data" / "johannes" / "9.json").read_text(encoding="utf-8"))
    reviewed = data["verses"]
    assert len(reviewed) == 41
    assert sum(len(verse.get("grondtekst", [])) for verse in reviewed) == 698
    assert reviewed[20]["grondtekst"][22]["bronstatus"] == "osis_aanvulling"
    for verse in reviewed:
        ground = verse.get("grondtekst", [])
        mapped = [index for item in verse.get("woordnummers", []) for index in item["herkomst"]["bronindices"]]
        assert sorted(mapped) == list(range(len(ground)))
        assert len(set(mapped)) == len(ground)


def test_johannes_10_publiceert_ieder_tr_token_precies_eenmaal():
    data = json.loads((ROOT / "data" / "johannes" / "10.json").read_text(encoding="utf-8"))
    reviewed = data["verses"]
    assert len(reviewed) == 42
    assert sum(len(verse.get("grondtekst", [])) for verse in reviewed) == 711
    for verse in reviewed:
        ground = verse.get("grondtekst", [])
        mapped = [index for item in verse.get("woordnummers", []) for index in item["herkomst"]["bronindices"]]
        assert sorted(mapped) == list(range(len(ground)))
        assert len(set(mapped)) == len(ground)


def test_johannes_11_publiceert_ieder_tr_token_precies_eenmaal():
    data = json.loads((ROOT / "data" / "johannes" / "11.json").read_text(encoding="utf-8"))
    reviewed = data["verses"]
    assert len(reviewed) == 57
    assert sum(len(verse.get("grondtekst", [])) for verse in reviewed) == 958
    for verse in reviewed:
        ground = verse.get("grondtekst", [])
        mapped = [index for item in verse.get("woordnummers", []) for index in item["herkomst"]["bronindices"]]
        assert sorted(mapped) == list(range(len(ground)))
        assert len(set(mapped)) == len(ground)


def test_johannes_12_publiceert_ieder_tr_token_precies_eenmaal():
    data = json.loads((ROOT / "data" / "johannes" / "12.json").read_text(encoding="utf-8"))
    reviewed = data["verses"]
    assert len(reviewed) == 50
    assert sum(len(verse.get("grondtekst", [])) for verse in reviewed) == 891
    for verse in reviewed:
        ground = verse.get("grondtekst", [])
        mapped = [index for item in verse.get("woordnummers", []) for index in item["herkomst"]["bronindices"]]
        assert sorted(mapped) == list(range(len(ground)))
        assert len(set(mapped)) == len(ground)


def test_johannes_13_publiceert_ieder_tr_token_precies_eenmaal():
    data = json.loads((ROOT / "data" / "johannes" / "13.json").read_text(encoding="utf-8"))
    reviewed = data["verses"]
    assert len(reviewed) == 38
    assert sum(len(verse.get("grondtekst", [])) for verse in reviewed) == 669
    for verse in reviewed:
        ground = verse.get("grondtekst", [])
        mapped = [index for item in verse.get("woordnummers", []) for index in item["herkomst"]["bronindices"]]
        assert sorted(mapped) == list(range(len(ground)))
        assert len(set(mapped)) == len(ground)


def test_johannes_14_1_10_publiceert_ieder_tr_token_precies_eenmaal():
    data = json.loads((ROOT / "data" / "johannes" / "14.json").read_text(encoding="utf-8"))
    reviewed = data["verses"][:10]
    assert sum(len(verse.get("grondtekst", [])) for verse in reviewed) == 189
    for verse in reviewed:
        ground = verse.get("grondtekst", [])
        mapped = [index for item in verse.get("woordnummers", []) for index in item["herkomst"]["bronindices"]]
        assert sorted(mapped) == list(range(len(ground)))
        assert len(set(mapped)) == len(ground)

def test_audit_reports_johannes_tr_coverage_and_valid_provenance():
    report = AUDIT.audit()

    assert report["inline_eligible_verses"] > report["verses_with_inline_mappings"]
    # Johannes 1:1-5 plus de gecontroleerde Izaäk-koppeling in Gebed van
    # Manasse 1 vormen samen de huidige, handmatig gereviewde basis.
    assert report["verses_with_inline_mappings"] >= 52
    assert report["inline_review_status"].get("handmatig_gecontroleerd", 0) >= 52
    assert not [item for item in report["invalid_inline"] if item.get("book") == "johannes"]


@pytest.mark.parametrize("chapter,verse_count", [(1, 29), (2, 23), (3, 25), (4, 18)])
def test_kolossenzen_hoofdstukken_publiceren_ieder_tr_token_precies_eenmaal(chapter, verse_count):
    data = json.loads((ROOT / "data" / "kolossenzen" / f"{chapter}.json").read_text(encoding="utf-8"))
    review = json.loads((ROOT / "data" / "woordnummers-review" / f"kolossenzen-{chapter}.json").read_text(encoding="utf-8"))

    assert len(data["verses"]) == verse_count
    for verse in data["verses"]:
        number = str(verse["number"])
        ground = verse.get("grondtekst", [])
        mappings = verse.get("woordnummers", [])
        indices = [
            index
            for mapping in mappings
            for index in mapping.get("herkomst", {}).get(
                "grondindices",
                mapping.get("herkomst", {}).get("bronindices", []),
            )
        ]
        assert ground, f"Kolossenzen {chapter}:{number} mist TR-grondtekst"
        assert sorted(indices) == list(range(len(ground)))
        assert len(indices) == len(set(indices))
        assert all(mapping["tekst"] in verse["text2026"] for mapping in mappings)
        assert all(mapping.get("reviewstatus") == "handmatig_gecontroleerd" for mapping in mappings)
        if "verses" in review:
            assert review["verses"][number]["ongemapt"] == []
        else:
            records = {str(record["verse"]): record for record in review["books"][0]["verses"]}
            assert records[number].get("ongemapt", []) == []


@pytest.mark.parametrize(
    "book,chapters",
    [("1tessalonicensen", range(1, 6)), ("2tessalonicensen", range(1, 4))],
)
def test_tessalonicensen_hoofdstukken_publiceren_ieder_tr_token_precies_eenmaal(book, chapters):
    for chapter in chapters:
        data = json.loads((ROOT / "data" / book / f"{chapter}.json").read_text(encoding="utf-8"))
        review = json.loads((ROOT / "data" / "woordnummers-review" / f"{book}-{chapter}.json").read_text(encoding="utf-8"))
        for verse in data["verses"]:
            number = str(verse["number"])
            ground = verse.get("grondtekst", [])
            mappings = verse.get("woordnummers", [])
            indices = [
                index
                for mapping in mappings
                for index in mapping.get("herkomst", {}).get(
                    "grondindices",
                    mapping.get("herkomst", {}).get("bronindices", []),
                )
            ]
            assert ground
            assert sorted(indices) == list(range(len(ground)))
            assert len(indices) == len(set(indices))
            assert all(mapping["tekst"] in verse["text2026"] for mapping in mappings)
            if "verses" in review:
                assert review["verses"][number]["ongemapt"] == []
            else:
                records = {str(record["verse"]): record for record in review["books"][0]["verses"]}
                assert records[number].get("ongemapt", []) == []


@pytest.mark.parametrize(
    "book,chapters",
    [
        ("1timotheus", range(1, 7)),
        ("2timotheus", range(1, 5)),
        ("titus", range(1, 4)),
        ("filemon", range(1, 2)),
    ],
)
def test_pastorale_brieven_publiceren_ieder_tr_token_precies_eenmaal(book, chapters):
    for chapter in chapters:
        data = json.loads((ROOT / "data" / book / f"{chapter}.json").read_text(encoding="utf-8"))
        review = json.loads((ROOT / "data" / "woordnummers-review" / f"{book}-{chapter}.json").read_text(encoding="utf-8"))
        for verse in data["verses"]:
            indices = [index for mapping in verse.get("woordnummers", []) for index in mapping.get("herkomst", {}).get("bronindices", [])]
            unmapped = [index for item in review["verses"][str(verse["number"])]["ongemapt"] for index in item["bronindices"]]
            assert verse.get("grondtekst") and sorted(indices + unmapped) == list(range(len(verse["grondtekst"])))
            assert len(indices + unmapped) == len(set(indices + unmapped))
            assert all(mapping["tekst"] in verse["text2026"] for mapping in verse["woordnummers"])


def test_1timotheus_3_11_bewaart_de_bewezen_osisvariant_als_ongemapt():
    from scripts.rebuild_nt_tr_strongs import load_tr_chapter

    chapter = load_tr_chapter(
        Path(r"C:\tmp\greektext-textus-receptus\parsed\1TI.UTR"),
        Path(r"C:\tmp\crosswire-kjv\kjv.osis.xml"),
        chapter=3,
        osis_book="1Tim",
        allowed_osis_variants={(11, 5)},
    )

    assert chapter[11][5]["lemma_strong"] == "G3524"
    assert chapter[11][5]["bronstatus"] == "osis_variant_ongemapt"
    assert chapter[11][5]["osis_variant"] == {"lemma_strong": "G3542", "morfologie": "A-APM"}


@pytest.mark.parametrize(
    "book,chapters",
    [
        ("hebreeen", range(1, 14)), ("jakobus", range(1, 6)),
        ("1petrus", range(1, 6)), ("2petrus", range(1, 4)),
        ("1johannes", range(1, 6)), ("2johannes", range(1, 2)),
        ("3johannes", range(1, 2)), ("judas", range(1, 2)),
        ("openbaring", range(1, 23)),
    ],
)
def test_resterende_nt_brieven_publiceren_ieder_tr_token_of_een_variant(book, chapters):
    for chapter in chapters:
        data = json.loads((ROOT / "data" / book / f"{chapter}.json").read_text(encoding="utf-8"))
        review = json.loads((ROOT / "data" / "woordnummers-review" / f"{book}-{chapter}.json").read_text(encoding="utf-8"))
        for verse in data["verses"]:
            if not verse.get("grondtekst"):
                assert verse.get("woordnummers") == []
                assert review["verses"][str(verse["number"])]["bronafwijking"]["reden"] == "versgrens_afwijking"
                continue
            mapped = [index for mapping in verse.get("woordnummers", []) for index in mapping.get("herkomst", {}).get("bronindices", [])]
            unmapped = [index for item in review["verses"][str(verse["number"])]["ongemapt"] for index in item["bronindices"]]
            assert verse.get("grondtekst") and sorted(mapped + unmapped) == list(range(len(verse["grondtekst"])))
            assert len(mapped + unmapped) == len(set(mapped + unmapped))
            assert all(mapping["tekst"] in verse["text2026"] for mapping in verse["woordnummers"])


def test_genesis_4_review_bevat_alle_versen_en_dekt_iedere_lokale_positie():
    """Een niet-lege reviewbron bewaakt de reproduceerbare hoofdstukimport."""
    path = ROOT / "data" / "woordnummers-review" / "genesis-4.json"
    assert path.stat().st_size > 0
    review = json.loads(path.read_text(encoding="utf-8"))
    records = review["books"][0]["verses"]
    assert [record["verse"] for record in records] == list(range(1, 27))
    assert all(record["mappings"] for record in records)

    chapter = json.loads((ROOT / "data" / "genesis" / "4.json").read_text(encoding="utf-8"))
    for verse, record in zip(chapter["verses"], records):
        mapped = [
            index
            for mapping in record["mappings"]
            for index in mapping["grondindices"]
        ]
        unmapped = [
            index
            for item in record.get("ongemapt", [])
            for index in item["grondindices"]
        ]
        assert sorted(mapped + unmapped) == list(range(len(verse["grondtekst"])))
        assert len(mapped + unmapped) == len(set(mapped + unmapped))


def _proefcorpus(root, mappings):
    """Zet een corpus van één boek met één vers neer voor AUDIT.audit()."""
    (root / "books.json").write_text(
        json.dumps({"books": [{"id": "proefboek", "chaptersIncluded": [1]}]}),
        encoding="utf-8",
    )
    (root / "proefboek").mkdir()
    (root / "proefboek" / "1.json").write_text(
        json.dumps(
            {
                "verses": [
                    {
                        "number": 1,
                        "text2026": "vierhonderd jaar",
                        "grondtekst": [
                            {"woord": "אַרְבַּ֥ע", "strongs": "H702"},
                            {"woord": "מֵא֖וֹת", "strongs": "H3967"},
                        ],
                        "woordnummers": mappings,
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def _proefkoppeling(tekst, voorkomen, number="H702"):
    return {
        "tekst": tekst,
        "voorkomen": voorkomen,
        "strongs": [number],
        "confidence": 1.0,
        "reviewstatus": "handmatig_gecontroleerd",
        "herkomst": {
            "dataset": "bsb-full-strongs-usj",
            "versie": "5.6",
            "sha256": "0" * 64,
            "referentie": "PRF 1:1",
            "bronindices": [0],
        },
    }


def test_audit_meldt_anker_dat_alleen_binnen_een_groter_woord_staat(tmp_path, monkeypatch):
    """"vier" in "vierhonderd jaar" rendert niet, dus moet de audit het melden.

    De renderer matcht op woordgrenzen. Toen de audit nog met een losse
    substringtelling werkte, bleef zo'n koppeling groen terwijl het
    Strongnummer in de lezer stilzwijgend verdween.
    """
    _proefcorpus(tmp_path, [_proefkoppeling("vier", 1)])
    monkeypatch.setattr(AUDIT, "DATA", tmp_path)

    report = AUDIT.audit()

    assert [item["reason"] for item in report["invalid_inline"]] == ["stale_anchor"]
    assert report["invalid_inline"][0]["target"] == "vier"


def test_audit_accepteert_anker_op_de_hele_samenstelling(tmp_path, monkeypatch):
    """De samenstelling zelf draagt beide Strongnummers en blijft geldig."""
    _proefcorpus(
        tmp_path,
        [
            _proefkoppeling("vierhonderd", 1),
            _proefkoppeling("vierhonderd", 1, number="H3967"),
        ],
    )
    monkeypatch.setattr(AUDIT, "DATA", tmp_path)

    report = AUDIT.audit()

    assert report["invalid_inline"] == []


@pytest.mark.parametrize(
    "tekst,anker,verwacht",
    [
        ("vierhonderd jaar", "vier", 0),
        ("vierhonderd jaar", "honderd", 0),
        ("vierhonderd jaar", "vierhonderd", 1),
        ("Vierhonderd en vier jaar", "vier", 1),
        ("En Cham, Kanaäns vader", "Kanaän", 0),
        ("En Cham, Kanaäns vader", "kanaäns", 1),
        ("het ene volk en het andere volk", "volk", 2),
        ("Twee volken zijn in uw buik", "volk", 0),
    ],
)
def test_anchor_occurrences_telt_op_woordgrenzen(tekst, anker, verwacht):
    assert AUDIT.anchor_occurrences(tekst, anker) == verwacht
