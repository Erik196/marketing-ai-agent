"""Real local retrieval and SDK execution; embedding/model responses are test fixtures."""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from agents import Model, ModelResponse, RunConfig, Runner, Usage
from openai.types.responses import ResponseFunctionToolCall, ResponseOutputMessage

from marketpilot import agent, knowledge_cli, retrieval
from marketpilot.execution import ExecutionLog


@pytest.fixture
def corpus(tmp_path):
    directory = tmp_path / "knowledge"
    directory.mkdir()
    (directory / "product.md").write_text(
        "---\ntitle: Demo app\nstatus: fictional_demo\ntags: students\n---\n"
        "# Features\nA planner helps organize coursework.\n"
        "# Price\nPrice is unknown.\n", encoding="utf-8",
    )
    return directory


def test_chunks_preserve_metadata_headings_and_source_lines(corpus):
    chunks = retrieval.collect_chunks(corpus)
    assert len(chunks) == 2
    assert chunks[0]["heading"] == "Features"
    assert chunks[0]["start_line"] == 6
    assert chunks[0]["end_line"] == 7
    assert chunks[1]["start_line"] == 8
    assert chunks[0]["metadata"]["status"] == "fictional_demo"
    assert chunks[0]["source"] == "knowledge/product.md"
    assert retrieval.collect_chunks(corpus) == chunks


def test_long_sections_overlap_without_crossing_headings():
    document = retrieval.Document("knowledge/long.md", "# First\n" + "x" * 160 + "\n# Second\nEnd.",
                                  1, {"title": "Long", "tags": "", "status": "test"})
    chunks = retrieval.chunk_document(document, chunk_size=60, overlap=10)
    first = [chunk for chunk in chunks if chunk["heading"] == "First"]
    assert len(first) > 1
    assert all(len(chunk["text"]) <= 60 for chunk in chunks)
    assert first[0]["text"][-10:] == first[1]["text"][:10]
    assert all("# Second" not in chunk["text"] for chunk in first)
    with pytest.raises(ValueError, match="overlap"):
        retrieval.chunk_document(document, chunk_size=10, overlap=10)


def test_empty_corpus_and_unclosed_metadata_are_actionable(tmp_path):
    with pytest.raises(ValueError, match="No nonempty"):
        retrieval.collect_chunks(tmp_path)
    (tmp_path / "bad.md").write_text("---\ntitle: Unclosed\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Unclosed"):
        retrieval.collect_chunks(tmp_path)


def test_keyword_search_works_without_index_or_api_key(corpus, tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    embed = AsyncMock()
    monkeypatch.setattr(retrieval, "embed_texts", embed)
    result = asyncio.run(retrieval.retrieve_knowledge("planner coursework", "keyword", 1, corpus,
                                                     tmp_path / "missing.json"))
    assert result["matches"][0]["heading"] == "Features"
    assert result["matches"][0]["citation"] == "[knowledge/product.md:6]"
    assert result["matches"][0]["semantic_score"] is None
    missing = asyncio.run(retrieval.retrieve_knowledge("zebra", "keyword", 1, corpus))
    assert missing["matches"] == []
    embed.assert_not_called()


def test_cosine_similarity_checks_dimensions_and_zero_vectors():
    assert retrieval.cosine_similarity([1, 0], [1, 0]) == 1
    assert retrieval.cosine_similarity([1, 0], [0, 1]) == 0
    with pytest.raises(ValueError, match="dimensions"):
        retrieval.cosine_similarity([1], [1, 0])
    with pytest.raises(ValueError, match="zero"):
        retrieval.cosine_similarity([0, 0], [1, 0])


def test_index_reuse_and_stale_source_detection(corpus, tmp_path, monkeypatch):
    index = tmp_path / "index.json"
    embed = AsyncMock(return_value=[[1, 0], [0, 1]])
    monkeypatch.setattr(retrieval, "embed_texts", embed)
    assert asyncio.run(retrieval.build_index(corpus, index))["status"] == "built"
    assert asyncio.run(retrieval.build_index(corpus, index))["status"] == "reused"
    assert embed.await_count == 1
    source = corpus / "product.md"
    source.write_text(source.read_text().replace("Price is unknown", "Price remains unspecified"))
    with pytest.raises(ValueError, match="stale"):
        asyncio.run(retrieval.retrieve_knowledge("price", "semantic", 1, corpus, index))
    assert embed.await_count == 1  # Do not spend query credits on a stale index.
    assert asyncio.run(retrieval.build_index(corpus, index))["status"] == "built"
    assert embed.await_count == 2
    assert asyncio.run(retrieval.build_index(corpus, index, force=True))["status"] == "built"
    assert embed.await_count == 3


def test_semantic_and_hybrid_ranking_with_explicit_test_vectors(corpus, tmp_path, monkeypatch):
    index = tmp_path / "index.json"
    # Fixtures deliberately make Features closer semantically, but Price an exact keyword match.
    embed = AsyncMock(side_effect=[[[1, 0], [0.8, 0.6]], [[1, 0]], [[1, 0]]])
    monkeypatch.setattr(retrieval, "embed_texts", embed)
    asyncio.run(retrieval.build_index(corpus, index))
    semantic = asyncio.run(retrieval.retrieve_knowledge("price", "semantic", 1, corpus, index))
    hybrid = asyncio.run(retrieval.retrieve_knowledge("price", "hybrid", 1, corpus, index))
    assert semantic["matches"][0]["heading"] == "Features"
    assert hybrid["matches"][0]["heading"] == "Price"
    assert "embedding" not in hybrid["matches"][0]  # Send evidence text, not huge vectors, to the LLM.
    assert hybrid["embedding_model"] == retrieval.EMBEDDING_MODEL


@pytest.mark.parametrize("vectors", [[[1, 0], [1]], [[0, 0], [1, 0]], [[float("nan"), 1], [1, 0]]])
def test_invalid_vectors_do_not_overwrite_index(corpus, tmp_path, monkeypatch, vectors):
    index = tmp_path / "index.json"
    index.write_text("existing file")
    monkeypatch.setattr(retrieval, "embed_texts", AsyncMock(return_value=vectors))
    with pytest.raises(ValueError, match="invalid embedding"):
        asyncio.run(retrieval.build_index(corpus, index, force=True))
    assert index.read_text() == "existing file"


def test_missing_index_and_invalid_search_parameters(corpus, tmp_path, monkeypatch):
    embed = AsyncMock()
    monkeypatch.setattr(retrieval, "embed_texts", embed)
    with pytest.raises(ValueError, match="index is missing"):
        asyncio.run(retrieval.retrieve_knowledge("planner", "hybrid", 1, corpus, tmp_path / "missing.json"))
    for query, mode, top_k in [("", "keyword", 1), ("x", "bad", 1), ("x", "keyword", 6)]:
        with pytest.raises(ValueError):
            asyncio.run(retrieval.retrieve_knowledge(query, mode, top_k, corpus))
    embed.assert_not_called()


def test_embedding_batch_order_matches_requested_inputs(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "offline-placeholder")

    async def fake_create(**kwargs):
        # Simulate API items arriving out of order; do not use these as real embeddings.
        return SimpleNamespace(data=[SimpleNamespace(index=i, embedding=[float(text), 1.0])
                                     for i, text in reversed(list(enumerate(kwargs["input"])))])

    create = AsyncMock(side_effect=fake_create)
    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=SimpleNamespace(embeddings=SimpleNamespace(create=create)))
    client.__aexit__ = AsyncMock(return_value=False)
    monkeypatch.setattr(retrieval, "AsyncOpenAI", MagicMock(return_value=client))
    vectors = asyncio.run(retrieval.embed_texts([str(i) for i in range(65)]))
    assert create.await_count == 2
    assert vectors == [[float(i), 1.0] for i in range(65)]
    assert create.call_args.kwargs["model"] == "text-embedding-3-small"


def test_embedding_credentials_and_cli_errors(monkeypatch, capsys):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        asyncio.run(retrieval.embed_texts(["test"]))
    monkeypatch.setattr(knowledge_cli, "build_index", AsyncMock(side_effect=ValueError("test missing key")))
    assert knowledge_cli.main(["index"]) == 2
    assert "test missing key" in capsys.readouterr().err


class RetrievalModel(Model):
    """Test-only model: retrieve local evidence, then check the SDK supplies it back."""
    def __init__(self):
        self.calls = 0
        self.received_evidence = False

    async def get_response(self, *args, **kwargs):
        self.calls += 1
        if self.calls == 1:
            output = [ResponseFunctionToolCall(
                type="function_call", name="search_knowledge", call_id="retrieval-test-1",
                arguments=json.dumps({"query": "supported features", "mode": "keyword", "top_k": 1}),
            )]
        else:
            history = kwargs.get("input", args[1] if len(args) > 1 else [])
            self.received_evidence = any(
                item.get("type") == "function_call_output" and "knowledge/product.md" in str(item.get("output"))
                and "fictional_demo" in str(item.get("output")) for item in history
            )
            output = [ResponseOutputMessage.model_validate({
                "id": "retrieval-answer", "type": "message", "role": "assistant", "status": "completed",
                "content": [{"type": "output_text", "text": "Test answer based on retrieved evidence.", "annotations": []}],
            })]
        return ModelResponse(output=output, usage=Usage(), response_id=None)

    async def stream_response(self, *args, **kwargs):
        raise NotImplementedError("Nonstreaming test only")
        yield


def test_sdk_retrieval_loop_logs_actual_local_passages(tmp_path):
    # The retrieval engine and shipped Markdown are real; only the model is scripted.
    model = RetrievalModel()
    marketing_agent = agent.create_marketing_agent()
    marketing_agent.model = model
    log = ExecutionLog("offline retrieval test", "scripted-model", directory=tmp_path)
    result = asyncio.run(Runner.run(marketing_agent, "Read the product features", context=log,
                                    run_config=RunConfig(tracing_disabled=True)))
    log.finish(output=result.final_output)
    assert model.calls == 2
    assert model.received_evidence
    step = json.loads(log.path.read_text())["steps"][0]
    assert step["tool"] == "search_knowledge"
    assert step["status"] == "completed"
    assert "focus timer" in step["outputs"]["matches"][0]["text"]
