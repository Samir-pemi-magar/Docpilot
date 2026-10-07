from io import BytesIO

from app.chunking.models import Chunk
from app.normalization.models import (
    NormalizedDocument,
    NormalizedElement,
    NormalizedElementType,
)
from app.normalization.registry import NormalizerRegistry
from app.parsers.models import ExtractedDocument
from app.parsers.registry import ParserRegistry
from app.processing.pipeline import DocumentProcessingPipeline


class FakeParser:
    def parse(self, file: BytesIO) -> ExtractedDocument:
        assert file.read() == b"hello"
        return ExtractedDocument(
            source_type="fake",
            metadata={"parsed": True},
        )


class FakeNormalizer:
    def normalize(
        self,
        document: ExtractedDocument,
    ) -> NormalizedDocument:
        assert document.source_type == "fake"

        return NormalizedDocument(
            source_type="fake",
            elements=[
                NormalizedElement(
                    element_type=NormalizedElementType.PARAGRAPH,
                    text="normalized text",
                )
            ],
            metadata={"normalized": True},
        )


class FakeChunker:
    def chunk(self, document: NormalizedDocument) -> list[Chunk]:
        assert document.source_type == "fake"
        assert document.text == "normalized text"

        return [
            Chunk(
                id="chunk-0000",
                text=document.text,
                element_type=NormalizedElementType.PARAGRAPH,
                source_element_indexes=[0],
                token_count=2,
            )
        ]


def make_pipeline() -> DocumentProcessingPipeline:
    parser_registry = ParserRegistry(
        parsers={
            ".fake": FakeParser(),
        }
    )

    normalizer_registry = NormalizerRegistry(
        normalizers={
            "fake": FakeNormalizer(),
        }
    )

    return DocumentProcessingPipeline(
        parser_registry=parser_registry,
        normalizer_registry=normalizer_registry,
        chunker=FakeChunker(),
    )


def test_processing_pipeline_runs_all_stages() -> None:
    pipeline = make_pipeline()

    result = pipeline.process(
        "example.fake",
        BytesIO(b"hello"),
    )

    assert result.extracted_document.source_type == "fake"
    assert result.normalized_document.text == "normalized text"
    assert len(result.chunks) == 1
    assert result.chunks[0].text == "normalized text"


def test_processing_pipeline_preserves_stage_outputs() -> None:
    pipeline = make_pipeline()

    result = pipeline.process(
        "example.fake",
        BytesIO(b"hello"),
    )

    assert result.extracted_document.metadata == {
        "parsed": True,
    }

    assert result.normalized_document.metadata == {
        "normalized": True,
    }

    assert result.chunks[0].id == "chunk-0000"
    assert result.chunks[0].source_element_indexes == [0]
