import asyncio
import json
from app.routes.chat import chat
from app.models.response import ChatRequest, Message

async def test_chat_locally():
    print("Testing multi-turn chat locally...")
    
    # Turn 1
    messages = [Message(role="user", content="need java developer")]
    request = ChatRequest(messages=messages)
    
    try:
        response = await chat(request)
        print(f"\nTurn 1 Status: Success")
        print(f"Assistant: {response.reply}")
        messages.append(Message(role="assistant", content=response.reply))
        
        # Turn 2
        print("\nTurn 2: 'senior'")
        messages.append(Message(role="user", content="senior"))
        request = ChatRequest(messages=messages)
        response = await chat(request)
        
        print(f"Turn 2 Status: Success")
        print(f"Assistant: {response.reply}")
        print(f"Recommendations: {len(response.recommendations)}")
        for i, rec in enumerate(response.recommendations):
            print(f"  {i+1}. {rec.name} ({rec.score:.2f})")
            
    except Exception as e:
        print(f"\nTest failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    import os
    # Mock environment variables for testing
    os.environ["GEMINI_API_KEY"] = "mock_key"
    asyncio.run(test_chat_locally())
