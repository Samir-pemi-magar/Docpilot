from io import BytesIO


from app.chunking.models import Chunk
from app.normalization.models import (
    NormalizedDocument,
    NormalizedElement,
    NormalizedElementType,
)
from app.parsers.models import ExtractedDocument
from app.processing.models import ProcessingResult
from app.processing.pipeline import DocumentProcessingPipeline
from app.processing.processor import DocumentProcessor


class FakePipeline:
    def process(
        self,
        filename: str,
        file: BytesIO,
    ) -> ProcessingResult:
        assert filename == "example.txt"
        assert file.read() == b"hello"

        extracted_document = ExtractedDocument(
            source_type="txt",
        )

        normalized_document = NormalizedDocument(
            source_type="txt",
            elements=[
                NormalizedElement(
                    element_type=NormalizedElementType.PARAGRAPH,
                    text="hello",
                )
            ],
        )

        chunks = [
            Chunk(
                id="chunk-0000",
                text="hello",
                element_type=NormalizedElementType.PARAGRAPH,
                source_element_indexes=[0],
                token_count=1,
            )
        ]

        return ProcessingResult(
            extracted_document=extracted_document,
            normalized_document=normalized_document,
            chunks=chunks,
        )


def test_document_processor_delegates_to_pipeline() -> None:
    pipeline = FakePipeline()
    processor = DocumentProcessor(pipeline=pipeline)

    result = processor.process(
        "example.txt",
        BytesIO(b"hello"),
    )

    assert result.extracted_document.source_type == "txt"
    assert result.normalized_document.text == "hello"
    assert result.chunks[0].text == "hello"


def test_document_processor_uses_pipeline_result() -> None:
    pipeline = FakePipeline()
    processor = DocumentProcessor(pipeline=pipeline)

    result = processor.process(
        "example.txt",
        BytesIO(b"hello"),
    )

    assert isinstance(result, ProcessingResult)
    assert len(result.chunks) == 1
    assert result.chunks[0].id == "chunk-0000"
