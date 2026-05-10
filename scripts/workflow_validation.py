
import requests
import time

BACKEND_URL = "http://localhost:8000"

def test_workflow_isolation():
    session_id = "test_session_final"
    headers = {"X-Session-ID": session_id}
    
    print("\n--- TEST 1: Vague Prompt ---")
    resp = requests.post(f"{BACKEND_URL}/chat", json={"messages": [{"role": "user", "content": "I need a developer assessment"}]}, headers=headers).json()
    print(f"User: I need a developer assessment")
    print(f"Assistant: {resp.get('reply', '')[:100]}...")
    assert len(resp.get('recommendations', [])) == 0, "Should NOT have recommendations for vague prompt"
    # The question should ask for seniority or tech stack
    assert any(term in resp.get('reply', '').lower() for term in ["seniority", "experience", "level", "stack", "framework"]), "Should ask for clarification details"

    print("\n--- TEST 2: Specific Python Request ---")
    resp = requests.post(f"{BACKEND_URL}/chat", json={"messages": [
        {"role": "user", "content": "I need a developer assessment"},
        {"role": "assistant", "content": resp.get('reply', '')},
        {"role": "user", "content": "It's for a Senior Python Backend role."}
    ]}, headers=headers).json()
    print(f"User: It's for a Senior Python Backend role.")
    recs = [r['name'] for r in resp.get('recommendations', [])]
    print(f"Recommendations: {recs[:3]}")
    assert len(recs) > 0, "Should have recommendations for specific prompt"
    assert any("Python" in r or "Data Science" in r or "SQL" in r or "Backend" in r for r in recs), "Should have relevant recommendations"
    assert not any("Java" in r for r in recs), "Should NOT have Java contamination in Python request"

    print("\n--- TEST 3: New Request Isolation (Java) ---")
    # We send the FULL history but the backend should detect the 'Now' transition
    resp = requests.post(f"{BACKEND_URL}/chat", json={"messages": [
        {"role": "user", "content": "I need a developer assessment"},
        {"role": "assistant", "content": "..." },
        {"role": "user", "content": "It's for a Senior Python Backend role."},
        {"role": "assistant", "content": "..." },
        {"role": "user", "content": "Now I need assessments for a Java developer."}
    ]}, headers=headers).json()
    print(f"User: Now I need assessments for a Java developer.")
    recs = [r['name'] for r in resp.get('recommendations', [])]
    print(f"Recommendations: {recs[:3]}")
    # The new extraction should get "Java developer"
    assert any("Java" in r for r in recs), "Should have Java assessments"
    # Verify no Python-specific leakage
    assert not any("Data Science" in r for r in recs), "Should NOT have Python/DS contamination in new Java request"

    print("\n--- TEST 4: Refinement within same request ---")
    # Send a small history for this one
    resp = requests.post(f"{BACKEND_URL}/chat", json={"messages": [
        {"role": "user", "content": "Now I need assessments for a Java developer."},
        {"role": "assistant", "content": "..." },
        {"role": "user", "content": "Also add leadership focus."}
    ]}, headers=headers).json()
    print(f"User: Also add leadership focus.")
    recs = [r['name'] for r in resp.get('recommendations', [])]
    print(f"Recommendations: {recs[:3]}")
    assert any("Java" in r for r in recs), "Should still have Java assessments"
    
    print("\nWORKFLOW TESTS PASSED!")

if __name__ == "__main__":
    try:
        test_workflow_isolation()
    except Exception as e:
        print(f"TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
