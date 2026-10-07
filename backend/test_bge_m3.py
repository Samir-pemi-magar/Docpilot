from app.embeddings.local_bge_m3 import LocalBGEEmbeddingProvider


provider = LocalBGEEmbeddingProvider(
    max_length=1024,
)

query = "What qualification is required for BCA admission?"

result = provider.embed_query(query)

print()
print("Model:", result.model)
print("Dimension:", result.dimension)
print("Vector length:", len(result.vector))
print("First 10 values:", result.vector[:10])

documents = provider.embed_documents(
    [
        "Students applying for BCA must have completed higher secondary education.",
        "The library is open from 7 AM to 8 PM.",
    ]
)

print()
print("Documents:", len(documents.embeddings))
print("Document dimension:", documents.dimension)
print("First document first 10 values:")
print(documents.embeddings[0].vector[:10])

print()
print("BGE-M3 smoke test passed.")
