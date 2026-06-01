import gradio as gr
import json
import os
import re
import torch
from threading import Thread
from transformers import AutoModelForCausalLM, AutoTokenizer, TextIteratorStreamer

# Load model and tokenizer
tokenizer = AutoTokenizer.from_pretrained("HuggingFaceTB/SmolLM2-1.7B-Instruct")
model = AutoModelForCausalLM.from_pretrained("HuggingFaceTB/SmolLM2-1.7B-Instruct")
model.generation_config.max_length = None

# ---------------------------------------------------------------------------
# Load FAQ context from faq.json at startup
# ---------------------------------------------------------------------------
def load_faq_from_json(path: str = "faq.json") -> str:
    """Read faq.json and return a plain Q&A text block the chatbot can use."""
    if not os.path.exists(path):
        print(f"[WARNING] FAQ file not found at '{path}'. Context will be empty.")
        return ""
    with open(path, "r", encoding="utf-8") as f:
        items = json.load(f)
    lines = []
    for item in items:
        q = item.get("q", "").strip()
        a = item.get("a", "").strip()
        if q and a:
            lines.append(f"Question: {q}\nAnswer: {a}")
    return "\n\n".join(lines)

FAQ_CONTEXT: str = load_faq_from_json("faq.json")
print(f"[INFO] Loaded {FAQ_CONTEXT.count('Question:')} FAQ entries from faq.json")

CSS = """
.chatbot-container { border-radius: 12px !important; border: 0.5px solid #e0e0e0 !important; }
.user-message { background: #534AB7 !important; color: white !important; border-radius: 18px 18px 4px 18px !important; padding: 10px 16px !important; max-width: 80% !important; margin-left: auto !important; }
.bot-message { background: #F1EFE8 !important; color: #2C2C2A !important; border-radius: 18px 18px 18px 4px !important; padding: 10px 16px !important; max-width: 80% !important; }
footer { display: none !important; }
"""

# Common English filler words to ignore during matching
ENGLISH_STOP_WORDS = {
    "the", "a", "an", "and", "or", "but", "is", "are", "was", "were", "am", "be", "been", "being",
    "to", "of", "in", "on", "at", "by", "for", "with", "about", "against", "between", "into",
    "through", "during", "before", "after", "above", "below", "from", "up", "down", "out", "off", "over", "under",
    "this", "that", "these", "those", "am", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "having", "do", "does", "did", "doing", "can", "will", "should", "would",
    "i", "you", "he", "she", "it", "we", "they", "what", "which", "who", "whom", "how", "why", "where", "when"
}

def get_top_k_context(query, context_text, k=3):
    """
    Upgraded Mini-RAG: Strips out English stop words to ensure accurate matching,
    and splits blocks dynamically using 'Question:' tags.
    """
    if not context_text.strip():
        return ""

    blocks = re.split(r'\n+(?=Question:|Q:|Question\s*\d+:)', context_text, flags=re.IGNORECASE)
    blocks = [b.strip() for b in blocks if b.strip()]

    if len(blocks) <= k:
        return context_text

    raw_query_words = set(re.findall(r'\w+', query.lower()))
    query_words = raw_query_words - ENGLISH_STOP_WORDS

    if not query_words:
        query_words = raw_query_words

    scored_blocks = []
    for block in blocks:
        block_words = set(re.findall(r'\w+', block.lower())) - ENGLISH_STOP_WORDS
        score = len(block_words.intersection(query_words))
        scored_blocks.append((score, block))

    scored_blocks.sort(key=lambda x: x[0], reverse=True)
    selected_blocks = [block for score, block in scored_blocks[:k]]

    print(f"\n[DEBUG] Question: '{query}' -> Selected top block:\n{selected_blocks[0] if selected_blocks else 'None'}\n")

    return "\n\n".join(selected_blocks)

def build_messages(history, context, new_message):
    """Builds the messages list for the chat template (streaming UI path)."""
    system_prompt = f"""You are a helpful FAQ assistant for a university club.
Answer the question in English using ONLY the provided FAQ context below.
Be direct, clear, and concise. If the information is not present in the context, simply reply: "This information is not available in the FAQ."

RELEVANT FAQ CONTEXT:
{context}"""

    messages = [{"role": "system", "content": system_prompt}]
    for turn in history:
        messages.append({"role": "user",      "content": turn["content"] if isinstance(turn, dict) else turn[0]})
        messages.append({"role": "assistant", "content": turn["content"] if isinstance(turn, dict) else turn[1]})
    messages.append({"role": "user", "content": new_message})
    return messages

def user_step(message, history):
    if not message.strip():
        return "", history, history
    history = history + [{"role": "user", "content": message}]
    return "", history, history

def bot_step(history):
    if not history:
        yield history, history
        return

    last_user = next((m["content"] for m in reversed(history) if m["role"] == "user"), None)
    if not last_user:
        yield history, history
        return

    if not FAQ_CONTEXT.strip():
        history = history + [{"role": "assistant", "content": "FAQ data could not be loaded. Please make sure faq.json is present next to app.py."}]
        yield history, history
        return

    try:
        filtered_context = get_top_k_context(last_user, FAQ_CONTEXT, k=3)
        messages = build_messages(history[:-1], filtered_context, last_user)

        tokenized_output = tokenizer.apply_chat_template(
            messages,
            tokenize=True,
            add_generation_prompt=True,
            return_tensors="pt"
        )

        if isinstance(tokenized_output, torch.Tensor):
            generation_kwargs = dict(
                input_ids=tokenized_output.to(model.device),
                max_new_tokens=200,
                pad_token_id=tokenizer.eos_token_id
            )
        else:
            model_inputs = {k: v.to(model.device) for k, v in tokenized_output.items()}
            generation_kwargs = dict(
                **model_inputs,
                max_new_tokens=200,
                pad_token_id=tokenizer.eos_token_id
            )

        streamer = TextIteratorStreamer(tokenizer, skip_prompt=True, skip_special_tokens=True)
        generation_kwargs["streamer"] = streamer

        thread = Thread(target=model.generate, kwargs=generation_kwargs)
        thread.start()

        history = history + [{"role": "assistant", "content": ""}]

        reply = ""
        for new_text in streamer:
            reply += new_text
            history[-1]["content"] = reply
            yield history, history

    except Exception as e:
        history = history + [{"role": "assistant", "content": f"Error: {str(e)}"}]
        yield history, history


# ===========================================================================
# API ENDPOINT  — non-streaming version called by client.py / benchmark.py
# ===========================================================================

def chat_api(message: str, history_json: str = "[]") -> str:
    """
    Non-streaming chat function exposed as a Gradio API endpoint.

    Called by gradio_client on your PC:
        client.predict(message, history_json, api_name="/chat")

    Args:
        message:      The user's question (plain string).
        history_json: Conversation history as a JSON string.
                      Format: '[{"role":"user","content":"..."},
                                {"role":"assistant","content":"..."}]'
                      Pass "[]" for a fresh conversation.

    Returns:
        The assistant's answer as a plain string.
    """
    if not message.strip():
        return "Please provide a non-empty message."

    if not FAQ_CONTEXT.strip():
        return "FAQ data could not be loaded. Make sure faq.json is present."

    # Parse history safely
    try:
        history: list = json.loads(history_json)
        if not isinstance(history, list):
            history = []
    except Exception:
        history = []

    try:
        filtered_context = get_top_k_context(message, FAQ_CONTEXT, k=3)

        # Build the messages list properly (handles dict-format history)
        system_prompt = (
            "You are a helpful FAQ assistant for a university club.\n"
            "Answer the question in English using ONLY the provided FAQ context below.\n"
            "Be direct, clear, and concise. "
            "If the information is not present in the context, simply reply: "
            "\"This information is not available in the FAQ.\"\n\n"
            f"RELEVANT FAQ CONTEXT:\n{filtered_context}"
        )

        messages = [{"role": "system", "content": system_prompt}]

        for msg in history:
            # Only accept well-formed role/content dicts
            if isinstance(msg, dict) and msg.get("role") in ("user", "assistant") and "content" in msg:
                messages.append({"role": msg["role"], "content": msg["content"]})

        messages.append({"role": "user", "content": message})

        # Tokenise
        tokenized = tokenizer.apply_chat_template(
            messages,
            tokenize=True,
            add_generation_prompt=True,
            return_tensors="pt",
        )

        input_ids = (
            tokenized.to(model.device)
            if isinstance(tokenized, torch.Tensor)
            else tokenized["input_ids"].to(model.device)
        )

        # Greedy decode — deterministic, good for benchmarking
        with torch.no_grad():
            output = model.generate(
                input_ids=input_ids,
                max_new_tokens=200,
                pad_token_id=tokenizer.eos_token_id,
                do_sample=False,
            )

        # Decode only the newly generated tokens
        new_tokens = output[0][input_ids.shape[-1]:]
        return tokenizer.decode(new_tokens, skip_special_tokens=True).strip()

    except Exception as exc:
        return f"Server error: {exc}"


# ===========================================================================
# UI
# ===========================================================================

with gr.Blocks(title="INSAT Club FAQ Chatbot", css=CSS) as demo:
    gr.HTML("""
    <div style="padding: 20px 0 8px 0;">
      <div style="display:flex; align-items:center; gap:12px; margin-bottom:4px;">
        <div style="width:36px;height:36px;border-radius:50%;background:#534AB7;display:flex;align-items:center;justify-content:center;">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
        </div>
        <div>
          <div style="font-size:16px;font-weight:500;">FAQ Chatbot — INSAT</div>
          <div style="font-size:12px;color:#888;">Powered by SmolLM2 · Free · Open-source</div>
        </div>
      </div>
    </div>
    """)

    history_state = gr.State([])
    chatbot_ui = gr.Chatbot(
        height=420,
        show_label=False,
        container=False,
        elem_classes=["chatbot-container"],
        placeholder="<div style='text-align:center;color:#aaa;padding:40px 0'>Ask me anything about TRSYP 3.0!</div>",
    )
    with gr.Row():
        msg_box = gr.Textbox(
            placeholder="Ask a question...",
            show_label=False,
            container=False,
            scale=5,
        )
        send_btn = gr.Button("Send",  scale=1, variant="primary")
        clear_btn = gr.Button("Clear", scale=1)

    msg_box.submit(user_step, inputs=[msg_box, history_state], outputs=[msg_box, chatbot_ui, history_state], queue=False).then(
        bot_step, inputs=[history_state], outputs=[chatbot_ui, history_state]
    )
    send_btn.click(user_step, inputs=[msg_box, history_state], outputs=[msg_box, chatbot_ui, history_state], queue=False).then(
        bot_step, inputs=[history_state], outputs=[chatbot_ui, history_state]
    )
    clear_btn.click(lambda: ([], [], ""), outputs=[history_state, chatbot_ui, msg_box])

    # -----------------------------------------------------------------------
    # Hidden API endpoint — invisible in the browser, callable via
    # gradio_client from any machine.
    #
    # Discover all endpoints:  https://YOUR-SPACE.hf.space/?view=api
    # -----------------------------------------------------------------------
    with gr.Row(visible=False):
        _api_in_msg  = gr.Textbox(label="message")
        _api_in_hist = gr.Textbox(label="history_json", value="[]")
        _api_out     = gr.Textbox(label="response")
        _api_btn     = gr.Button("call")

    _api_btn.click(
        fn=chat_api,
        inputs=[_api_in_msg, _api_in_hist],
        outputs=_api_out,
        api_name="chat",        # → endpoint is  /chat
    )

demo.queue().launch()
