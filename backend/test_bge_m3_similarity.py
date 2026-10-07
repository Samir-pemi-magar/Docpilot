import math

from app.embeddings.local_bge_m3 import LocalBGEEmbeddingProvider


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))

    if norm_a == 0 or norm_b == 0:
        raise ValueError("Cannot calculate similarity for a zero vector.")

    return dot / (norm_a * norm_b)


provider = LocalBGEEmbeddingProvider(
    device="cuda",
    use_fp16=True,
    max_length=1024,
)

query = "What qualification is required for BCA admission?"

documents = [
    "Students applying for BCA must have completed higher secondary education.",
    "The library is open from 7 AM to 8 PM.",
]

query_embedding = provider.embed_query(query)

document_embeddings = provider.embed_documents(documents)

similarities = [
    cosine_similarity(
        query_embedding.vector,
        document_embedding.vector,
    )
    for document_embedding in document_embeddings.embeddings
]

print()
print("Query:")
print(query)

print()
for index, (document, similarity) in enumerate(
    zip(documents, similarities),
    start=1,
):
    print(f"Document {index}:")
    print(document)
    print(f"Cosine similarity: {similarity:.6f}")
    print()

if similarities[0] <= similarities[1]:
    raise AssertionError(
        "Expected the BCA qualification document to be more similar "
        "to the query than the library-hours document."
    )

print("Semantic similarity test passed.")
