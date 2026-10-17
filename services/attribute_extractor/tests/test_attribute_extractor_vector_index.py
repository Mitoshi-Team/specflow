from attribute_extractor import vector_index


def test_lexical_vector_index_fallback():
    vi = vector_index.LexicalVectorIndex()
    vi.add("color")
    vi.add("storage")
    q = vi.embed("цвет")
    res = vi.search(q, k=2)
    assert res[0][1] >= 0.0


def test_lexical_add_twice_no_dup():
    vi = vector_index.LexicalVectorIndex()
    vi.add("ram")
    vi.add("ram")
    assert len(vi._keys) == 1
