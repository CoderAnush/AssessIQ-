"""
Quick pipeline integration test.
Verifies that all components work together correctly.

Run this AFTER running: python scripts/build_pipeline.py
"""

import json
import numpy as np
from pathlib import Path


def test_pipeline_integration():
    """Test complete pipeline integration."""

    print("\n" + "=" * 80)
    print("PIPELINE INTEGRATION TEST")
    print("=" * 80 + "\n")

    errors = []
    warnings = []

    # Test 1: Check processed catalog exists
    print("✓ Testing: Processed catalog...")
    catalog_path = Path("data/processed/catalog_processed.json")
    if not catalog_path.exists():
        errors.append("Processed catalog not found. Run: python scripts/build_pipeline.py")
    else:
        with open(catalog_path) as f:
            catalog_data = json.load(f)
            count = len(catalog_data.get("assessments", []))
            print(f"  ✓ Found {count} assessments in catalog")

    # Test 2: Check embeddings exist
    print("✓ Testing: Embeddings...")
    embeddings_path = Path("data/processed/embeddings.npy")
    embeddings_ids_path = Path("data/processed/embeddings_ids.txt")

    if not embeddings_path.exists():
        errors.append("Embeddings not found")
    elif not embeddings_ids_path.exists():
        errors.append("Embeddings ID mapping not found")
    else:
        embeddings = np.load(embeddings_path)
        with open(embeddings_ids_path) as f:
            ids = [line.strip() for line in f]

        print(f"  ✓ Embeddings shape: {embeddings.shape}")
        print(f"  ✓ ID count: {len(ids)}")

        if embeddings.shape[0] != len(ids):
            errors.append(f"Embedding count ({embeddings.shape[0]}) != ID count ({len(ids)})")

        if embeddings.shape[1] != 384:
            warnings.append(f"Embedding dimension is {embeddings.shape[1]}, expected 384")

    # Test 3: Check FAISS index
    print("✓ Testing: FAISS index...")
    faiss_path = Path("data/processed/faiss_index.bin")
    faiss_meta_path = Path("data/processed/faiss_metadata.json")

    if not faiss_path.exists():
        errors.append("FAISS index not found")
    elif not faiss_meta_path.exists():
        errors.append("FAISS metadata not found")
    else:
        try:
            import faiss

            index = faiss.read_index(str(faiss_path))
            with open(faiss_meta_path) as f:
                meta = json.load(f)

            print(f"  ✓ FAISS vectors: {index.ntotal}")
            print(f"  ✓ FAISS dimension: {index.d}")

            if index.ntotal != meta.get("total_vectors"):
                warnings.append(
                    f"Vector count mismatch: index={index.ntotal}, metadata={meta.get('total_vectors')}"
                )

        except Exception as e:
            errors.append(f"Error reading FAISS index: {e}")

    # Test 4: Check BM25 index
    print("✓ Testing: BM25 index...")
    bm25_path = Path("data/processed/bm25_index.pkl")

    if not bm25_path.exists():
        errors.append("BM25 index not found")
    else:
        try:
            import pickle

            with open(bm25_path, "rb") as f:
                bm25_data = pickle.load(f)

            doc_count = len(bm25_data.get("documents", []))
            print(f"  ✓ BM25 documents: {doc_count}")

            if doc_count != len(catalog_data.get("assessments", [])):
                warnings.append(f"Document count ({doc_count}) != assessment count")

        except Exception as e:
            errors.append(f"Error reading BM25 index: {e}")

    # Test 5: Try a quick retrieval
    print("✓ Testing: Retrieval...")

    try:
        from app.services.vector_store import VectorStore
        from app.services.bm25_retriever import BM25Retriever

        # Load indexes
        vector_store = VectorStore.load(str(faiss_path), str(faiss_meta_path))
        bm25 = BM25Retriever.load(str(bm25_path))

        # Create a test query embedding
        if embeddings_path.exists():
            test_embedding = np.random.randn(1, 384).astype(np.float32)
            test_embedding = test_embedding / (np.linalg.norm(test_embedding) + 1e-10)

            # Test FAISS search
            faiss_results = vector_store.search(test_embedding, k=5)
            print(f"  ✓ FAISS search returned {len(faiss_results)} results")

            # Test BM25 search
            bm25_results = bm25.search("assessment", k=5)
            print(f"  ✓ BM25 search returned {len(bm25_results)} results")

    except Exception as e:
        warnings.append(f"Could not test retrieval: {e}")

    # Test 6: Check config
    print("✓ Testing: Configuration...")
    try:
        from app.config import settings

        if not Path(settings.catalog_path).exists():
            warnings.append(f"Config catalog path doesn't exist: {settings.catalog_path}")
        else:
            print(f"  ✓ Catalog path configured: {settings.catalog_path}")

        if not Path(settings.faiss_index_path).exists():
            warnings.append(f"Config FAISS path doesn't exist: {settings.faiss_index_path}")
        else:
            print(f"  ✓ FAISS path configured: {settings.faiss_index_path}")

    except Exception as e:
        warnings.append(f"Could not check config: {e}")

    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80 + "\n")

    if errors:
        print(f"❌ ERRORS ({len(errors)}):")
        for error in errors:
            print(f"   - {error}")

    if warnings:
        print(f"⚠ WARNINGS ({len(warnings)}):")
        for warning in warnings:
            print(f"   - {warning}")

    if not errors:
        print("✅ ALL TESTS PASSED!\n")
        print("Pipeline is ready to use:")
        print("  1. Start the API: python app/main.py")
        print("  2. Test retrieval: curl -X POST http://localhost:8000/chat ...")
        print("  3. Deploy: Follow PIPELINE_SETUP_GUIDE.md")
        return True
    else:
        print("\n❌ TESTS FAILED - Fix errors above before continuing\n")
        return False


def test_simple_chat():
    """Simple chat endpoint test."""

    print("\n" + "=" * 80)
    print("SIMPLE CHAT TEST")
    print("=" * 80 + "\n")

    try:
        import httpx

        # Test data
        request = {
            "messages": [
                {"role": "user", "content": "I'm hiring a Java developer"}
            ]
        }

        # Make request
        print("Sending: POST /chat")
        print(f"Data: {json.dumps(request, indent=2)}\n")

        with httpx.Client() as client:
            response = client.post(
                "http://localhost:8000/chat",
                json=request,
                timeout=10.0
            )

        if response.status_code == 200:
            result = response.json()
            print("✅ SUCCESS!\n")
            print("Response:")
            print(json.dumps(result, indent=2))
            return True
        else:
            print(f"❌ ERROR: Status {response.status_code}")
            print(response.text)
            return False

    except Exception as e:
        print(f"⚠ Could not test chat (server not running?): {e}\n")
        print("Start the server with: python app/main.py")
        return False


if __name__ == "__main__":
    import sys

    # Run integration test
    success = test_pipeline_integration()

    if not success:
        sys.exit(1)

    # Optionally test chat endpoint (requires running server)
    print("\nNote: To test the chat endpoint, run: python app/main.py")
    print("Then in another terminal, run: python tests/test_integration.py")
