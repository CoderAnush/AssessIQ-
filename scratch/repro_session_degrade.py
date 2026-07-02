"""Reproduce session degradation: many role prompts without clearing."""
import requests

BASE = "https://assessiq-kkw2.onrender.com/chat"
msgs = []
prompts = [
    "Hiring a Senior Java Backend Engineer with Spring Boot, Microservices, Kafka, Redis, Docker, Kubernetes, AWS, MySQL and REST APIs.",
    "hiring frontend developer",
    "hiring java developer",
    "Hiring AI Developer",
    "hiring backend developer",
    "hiring python engineer",
    "hiring devops engineer",
    "hiring frontend developer",
    "python",
    "need frontend",
    "devops developer",
]

for i, p in enumerate(prompts, 1):
    msgs.append({"role": "user", "content": p})
    r = requests.post(BASE, json={"messages": msgs}, timeout=120)
    d = r.json()
    msgs.append({"role": "assistant", "content": d.get("reply", "")})
    names = [x.get("name") for x in d.get("recommendations", [])[:4]]
    reply = d.get("reply", "")[:80]
    user_turns = sum(1 for m in msgs if m["role"] == "user")
    print(f"{i:02d} user_turns={user_turns} eoc={d.get('end_of_conversation')} | {reply}")
    print(f"    top4: {names}")
