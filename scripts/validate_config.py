#!/usr/bin/env python3
"""Quick configuration validation script."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

print("=" * 70)
print("ASSESSIQ CONFIGURATION VALIDATION")
print("=" * 70)

try:
    # Import and validate config
    from app.config import settings, validate_config

    print("\n✓ Configuration loaded successfully")
    print("\nLLM Configuration:")
    print(f"  • Model: {settings.gemini_model}")
    print(f"  • Timeout: {settings.gemini_timeout_seconds}s")
    print(f"  • Max Tokens: {settings.gemini_max_tokens}")
    print(f"  • Temperature: {settings.gemini_temperature}")
    print(f"  • Top P: {settings.gemini_top_p}")

    print("\nAPI Configuration:")
    print(f"  • Host: {settings.api_host}:{settings.api_port}")
    print(f"  • Environment: {settings.environment}")
    print(f"  • Debug: {settings.debug}")

    print("\nRetrieval Configuration:")
    print(f"  • Semantic Weight: {settings.semantic_search_weight}")
    print(f"  • BM25 Weight: {settings.bm25_search_weight}")
    print(f"  • Top K: {settings.top_k_retrieval}")
    print(f"  • Max Recommendations: {settings.max_recommendations}")

    print("\nValidating configuration...")
    validate_config()
    print("✓ Configuration validation passed")

    print("\n" + "=" * 70)
    print("✓ READY FOR DEPLOYMENT")
    print("=" * 70)

except ValueError as e:
    print(f"\n✗ Configuration error: {e}")
    sys.exit(1)
except Exception as e:
    print(f"\n✗ Unexpected error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
