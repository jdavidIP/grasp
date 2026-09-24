from app.ingestion.slips import agreed_slips, parse_slips

TRANSCRIPT = "Georgia and Ukraine were talking about joining NATO, that part of the reason the Soviet Union invaded Ukraine."


def test_parse_slips_keeps_only_quotes_found_in_the_transcript():
    result = {
        "slips": [
            {"reason": "r", "said": "the soviet union  invaded", "meant": "Russia invaded"},
            {"reason": "r", "said": "China invaded Taiwan", "meant": "x"},  # not in the text
            {"reason": "r", "said": "The Soviet Union invaded", "meant": "Russia invaded"},  # dup
            {"reason": "r", "said": "joining NATO", "meant": "Joining NATO"},  # not a change
            {"reason": "r", "said": "NATO"},  # no meant
            "junk",
        ]
    }

    slips = parse_slips(result, TRANSCRIPT)

    assert slips == [
        {"said": "the soviet union  invaded", "meant": "Russia invaded", "reason": "r"}
    ]


def test_parse_slips_tolerates_a_missing_or_malformed_list():
    assert parse_slips({}, TRANSCRIPT) == []
    assert parse_slips({"slips": "none"}, TRANSCRIPT) == []


def _slip(said, meant):
    return {"said": said, "meant": meant, "reason": "r"}


def test_agreed_slips_keeps_only_what_both_passes_found_with_the_same_correction():
    first = [
        _slip("accept block", "except block"),
        _slip("the accept block", "the except block"),  # the same slip again: reported once
        _slip("Georgia and Ukraine were", "Georgia and Moldova were"),  # corrections differ
        _slip("discovered by hubble in 1929", "discovered by hubble in 1924"),  # one pass only
    ]
    second = [
        _slip("the accept block", "the except block"),
        _slip("Georgia and Ukraine were", "Georgia and others were"),
    ]

    assert agreed_slips(first, second) == [_slip("accept block", "except block")]
