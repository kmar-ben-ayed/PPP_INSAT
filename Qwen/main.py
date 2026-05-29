from fastapi import FastAPI
from pydantic import BaseModel
import httpx
import gradio as gr
import json
import os

app = FastAPI(title="Chatbot TRSYP (Approche B)")
def load_faq(path: str = "context/faq.json") -> str:
    if not os.path.exists(path):
        return "Aucun contexte FAQ chargé."
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    lines = []
    for item in data:
        lines.append(f"Q: {item['question']}\nR: {item['reference_answer']}")
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

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            "http://localhost:11434/api/chat",
            json=payload
        )
        resp.raise_for_status()
        data = resp.json()

    answer = data["message"]["content"]
    return {"question": req.question, "answer": answer}


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
