from attribute_extractor import fields, vector_index


def test_field_resolver_new_field_when_below_threshold(tmp_path):
    vi = vector_index.LexicalVectorIndex()
    vi.add("color")
    r = fields.FieldResolver(
        vector_index=vi,
        match_threshold=0.9,
        store=__import__("attribute_extractor.catalog_store", fromlist=[""]).CatalogStore(
            catalog_path=tmp_path / "cat.json", blocklist_path=tmp_path / "bl.txt"
        ),
    )
    m = r.resolve("объём памяти")
    assert m.is_new_field is True
    assert m.matched_code is not None


def test_field_resolver_blocklist(tmp_path):
    r = fields.FieldResolver(
        blocklist=fields.FieldBlocklist(["запчасть"]),
        store=__import__("attribute_extractor.catalog_store", fromlist=[""]).CatalogStore(
            catalog_path=tmp_path / "cat.json", blocklist_path=tmp_path / "bl.txt"
        ),
    )
    m = r.resolve("Запчасть")
    assert m.blocked is True
