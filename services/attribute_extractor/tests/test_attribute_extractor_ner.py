from attribute_extractor.extractors import ner


def test_ner_span_pairing():
    spans = [
        ner.NERSpan(text="Цвет", label="CHARACTERISTIC", start=0, end=4, score=0.9),
        ner.NERSpan(text="черный", label="PROPERTY", start=5, end=11, score=0.9),
    ]
    pairs = ner.NERExtractor().extract_pairs(spans)
    assert pairs
    assert pairs[0].characteristic == "Цвет"
    assert pairs[0].property == "черный"
    assert pairs[0].ner_score > 0.0
