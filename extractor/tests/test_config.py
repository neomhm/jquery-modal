"""config.py: the fixed lists have the right sizes, and the label list
is exactly what decode.label_names() builds (Appendix E)."""
import config
import decode


def test_label_list():
    assert len(config.TYPES) == 25
    assert config.LABELS == decode.label_names(config.TYPES)
    assert len(config.LABELS) == 51
    assert config.LABELS[0] == "O"
    # B-type = 2k - 1 and I-type = 2k for type number k (1-based)
    for k, t in enumerate(config.TYPES, start=1):
        assert config.LABEL_ID["B-" + t] == 2 * k - 1
        assert config.LABEL_ID["I-" + t] == 2 * k


def test_fixed_orders():
    assert config.DOC_TYPES == ["invoice", "quote", "brochure",
                                "registration", "financials", "price_list",
                                "staff_list", "contract", "letter", "terms",
                                "other"]
    assert config.LANGS == ["ar", "zh", "en", "fr", "ru", "es", "it", "hi",
                            "ja", "ko"]
