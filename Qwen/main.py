from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
import gradio as gr
import json
import os
import time

app = FastAPI(title="Chatbot TRSYP (Approche B)")

# Allow the Vite dev server (port 5173) and any Cloudflare tunnel origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # tighten to your tunnel URL in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def load_faq(path: str = "context/faq.json") -> str:
    if not os.path.exists(path):
        return "Aucun contexte FAQ chargé."
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    lines = []
    for item in data:
        q = item.get('q') or item.get('question', '')
        a = item.get('a') or item.get('reference_answer', '')
        if q and a:
            lines.append(f"Q: {q}\nR: {a}")
    return "\n\n".join(lines)

FAQ_CONTEXT = load_faq()


class ChatRequest(BaseModel):
    question: str
    context: str = ""


@app.post("/chat")
async def chat(req: ChatRequest):
    context = req.context if req.context.strip() else FAQ_CONTEXT

    system_prompt = f"""Tu es un assistant virtuel pour les clubs et événements de l'INSAT.
Réponds uniquement en te basant sur le contexte fourni ci-dessous.
Si la réponse n'est pas dans le contexte, dis-le clairement et poliment.
Réponds toujours en français.

CONTEXTE FAQ :
{context}
"""

    payload = {
        "model": "qwen2.5:1.5b",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": req.question}
        ],
        "stream": False
    }

    t0 = time.time()
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            "http://localhost:11434/api/chat",
            json=payload
        )
        resp.raise_for_status()
        data = resp.json()
    latency_ms = round((time.time() - t0) * 1000)

    answer = data["message"]["content"]
    return {"question": req.question, "answer": answer, "latency_ms": latency_ms}


@app.get("/health")
def health():
    return {"status": "ok", "model": "qwen2.5:1.5b"}

# Interface Gradio
def gradio_chat(question: str, history: list | None):
    import requests as req_lib
    history = list(history or [])
    try:
        r = req_lib.post(
            "http://localhost:8000/chat",
            json={"question": question},
            timeout=60
        )
        answer = r.json()["answer"]
    except Exception as e:
        answer = f"Erreur : {e}"
    
    history.append(gr.ChatMessage(role="user", content=question))
    history.append(gr.ChatMessage(role="assistant", content=answer))
    return "", history, history

with gr.Blocks(title="Chatbot TRSYP") as demo:
    gr.Markdown("Chatbot TRSYP (Approche B)")
    gr.Markdown("Pose tes questions sur les clubs et événements de l'INSAT.")
    
    chatbot = gr.Chatbot(height=400)
    history_state = gr.State([])
    msg   = gr.Textbox(
                placeholder="Ex: Quelles sont les dates d'inscription ?",
                label="Ta question"
            )
    clear = gr.Button("🗑 Effacer la conversation")

    msg.submit(gradio_chat, [msg, history_state], [msg, chatbot, history_state])
    clear.click(lambda: ([], []), None, [chatbot, history_state])

# Monter Gradio sur FastAPI
app = gr.mount_gradio_app(app, demo, path="/")
