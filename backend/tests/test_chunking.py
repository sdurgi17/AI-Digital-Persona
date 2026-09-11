from app.services.ingestion import CHUNK_TARGET, chunk_text


def test_empty_text():
    assert chunk_text("") == []
    assert chunk_text("\n\n  \n") == []


def test_short_text_single_chunk():
    assert chunk_text("Hello world.") == ["Hello world."]


def test_paragraphs_grouped_up_to_target():
    paras = [f"Paragraph {i} " + "x" * 100 for i in range(30)]
    chunks = chunk_text("\n\n".join(paras))
    assert len(chunks) > 1
    assert all(len(c) <= CHUNK_TARGET + 250 for c in chunks)  # + overlap slack
    # nothing lost: every paragraph label appears somewhere
    joined = " ".join(chunks)
    assert all(f"Paragraph {i}" in joined for i in range(30))


def test_oversized_paragraph_hard_split():
    text = "y" * (CHUNK_TARGET * 3)
    chunks = chunk_text(text)
    assert len(chunks) >= 3
    assert all(len(c) <= CHUNK_TARGET for c in chunks)
