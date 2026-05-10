import requests
import json

BASE_URL = "http://localhost:8000"

def test_multi_turn_flow():
    messages = [
        {"role": "user", "content": "need java developer"}
    ]
    
    print("Turn 1: 'need java developer'")
    try:
        # Turn 1
        response = requests.post(f"{BASE_URL}/chat", json={"messages": messages})
        print(f"Status: {response.status_code}")
        if response.status_code != 200:
            print(f"Error: {response.text}")
            return
            
        data = response.json()
        print(f"Assistant: {data['reply']}")
        messages.append({"role": "assistant", "content": data["reply"]})
        
        # Turn 2
        print("\nTurn 2: 'junior'")
        messages.append({"role": "user", "content": "junior"})
        response = requests.post(f"{BASE_URL}/chat", json={"messages": messages})
        print(f"Status: {response.status_code}")
        if response.status_code != 200:
            print(f"Error: {response.text}")
            return
            
        data = response.json()
        print(f"Assistant: {data['reply']}")
        print(f"Recommendations: {len(data['recommendations'])}")
        for i, rec in enumerate(data['recommendations']):
            print(f"  {i+1}. {rec['name']} ({rec['match_label']})")
            
    except Exception as e:
        print(f"Test failed: {e}")

if __name__ == "__main__":
    # Ensure server is running or mock it
    # For now, this is a placeholder to show the test logic
    # In a real scenario, I would start the server and run this
    test_multi_turn_flow()
