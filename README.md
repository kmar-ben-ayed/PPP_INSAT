<div align="center">

# UniBot

### A Free, Comparative SLM Chatbot Platform for University Clubs

*Three deployment approaches. One generic interface. Zero cost.*

</div>

---

## Table of Contents

- [Overview](#overview)
- [The Three Approaches](#the-three-approaches)
- [Repository Structure](#repository-structure)
- [Shared Web Interface](#shared-web-interface)
- [Approach A — Hugging Face Spaces](#approach-a--hugging-face-spaces)
- [Approach B — Ollama + Cloudflare Tunnel](#approach-b--ollama--cloudflare-tunnel)
- [Approach C — Serverless Inference API](#approach-c--serverless-inference-api)
- [Benchmarking](#benchmarking)
- [FAQ Context Format](#faq-context-format)
- [Configuration Reference](#configuration-reference)
- [Known Limitations](#known-limitations)
- [License](#license)

---

## Overview

University clubs need intelligent communication tools, but commercial APIs (OpenAI GPT-4, Google Gemini, Anthropic Claude) impose recurring costs incompatible with the zero-budget reality of volunteer student associations.

**UniBot** addresses this gap through a rigorous comparative study of three entirely free SLM deployment strategies, followed by a production-ready chatbot implementation for the INSAT IEEE Student Branch and its annual congress, TRSYP 3.0. The system answers student questions in French and English, grounded exclusively in a club-specific FAQ — with no hallucination, no recurring fees, and no vendor lock-in.

**Research question:** *Which free deployment approach for a Small Language Model offers the best trade-off between latency, response quality, and operational feasibility for a university FAQ chatbot?*

**Key properties across all three approaches:**

- **Zero cost** — no API subscriptions, no cloud bills, no credit cards required
- **Generic & reusable** — swap the `faq.json` file to deploy for any club, no retraining needed
- **Bilingual** — French and English supported out of the box
- **Grounded answers** — the model responds only from the injected FAQ context; out-of-scope questions receive a polite refusal
- **Unified frontend** — a single React dashboard (Vite + Tailwind) connects to all three backends simultaneously

---

## The Three Approaches

| | Approach A | Approach B | Approach C |
|---|---|---|---|
| **Model** | SmolLM2-1.7B-Instruct | Qwen2.5-1.5B (GGUF 4-bit) | llama-3.1-8b-instant |
| **Developer** | HuggingFace | Alibaba | Meta / Groq |
| **Infrastructure** | HF Spaces CPU Cloud | Local machine + Cloudflare | Groq Inference API |
| **Interface** | Gradio | FastAPI + Gradio | Python HTTP server |
| **Setup time** | ~10 min | ~30 min | ~1 hour |
| **Data privacy** | Data sent to HF | Data stays local ✅ | Data sent to Groq |
| **GPU required** | No | No (optional) | No |
| **Main constraint** | Cold start >60s | Local machine availability | Rate limits (30 req/min) |
| **Cost** | 0 € | 0 € | 0 € |

---

## Repository Structure

```
UniBot/
│
├── approach-a/                  # Approach A — HF Spaces deployment
│   ├── app.py                   # Gradio app + Mini-RAG context filtering
│   ├── main.py                  # FastAPI bridge to HF Spaces via gradio_client
│   ├── benchmark.py             # Evaluation script (BLEU, ROUGE-L, latency)
│   ├── client.py                # Interactive CLI client
│   ├── faq.json                 # TRSYP 3.0 FAQ knowledge base
│   ├── data/
│   │   └── benchmark_dataset.json
│   └── requirements.txt
│
├── Qwen/                        # Approach B — Ollama + Cloudflare Tunnel
│   ├── main.py                  # FastAPI app + Gradio interface + /benchmark endpoint
│   ├── benchmark.py             # Full benchmark: latency, BLEU, ROUGE-L, TTFT, hallucination
│   ├── benchmark_concurrent.py  # Multi-user concurrency stress test
│   ├── benchmark_gpu_vs_cpu.py  # Interactive CPU vs GPU comparison
│   ├── plot_results.py          # Visualization: latency, quality, throughput charts
│   ├── context/
│   │   └── faq.json             # FAQ knowledge base (edit for your club)
│   ├── run_server.cmd           # One-click server launcher (Windows)
│   ├── run_tunnel.cmd           # One-click tunnel launcher (Windows)
│   ├── start_chatbot_and_tunnel.cmd
│   └── requirements.txt
│
├── approach-c/                  # Approach C — Groq/HF Serverless Inference API
│   ├── run_api.py               # HTTP server entrypoint
│   ├── config.py                # Centralized configuration
│   ├── data/
│   │   └── faq.json
│   ├── src/
│   │   ├── api_server.py        # ThreadingHTTPServer: /chat /health /benchmark /metrics
│   │   ├── benchmark.py         # Quality metrics pipeline
│   │   ├── faq_context.py       # FAQ parsing and prompt construction
│   │   ├── faq_responder.py     # LLM call + deterministic FAQ matcher fallback
│   │   └── metrics_tracker.py   # Thread-safe in-memory metrics
│   ├── tests/
│   │   ├── test_api_endpoints.py
│   │   └── test_benchmark_metrics.py
│   └── requirements.txt
│
├── src/                         # Shared React frontend (Vite + Tailwind)
│   ├── App.jsx
│   ├── pages/
│   │   ├── ChatPage.jsx         # Conversational interface with approach switching
│   │   ├── AdminPage.jsx        # Inline FAQ editor with pagination
│   │   └── BenchmarkPage.jsx    # Live benchmark dashboard with Recharts
│   ├── components/
│   │   └── Sidebar.jsx          # Approach selector + live health indicators
│   ├── lib/
│   │   ├── api.js               # Unified API client for all three backends
│   │   ├── context.js           # FAQ context management + localStorage persistence
│   │   └── i18n.js              # FR/EN translation utility
│   ├── locales/
│   │   ├── fr.json
│   │   └── en.json
│   └── data/
│       └── faq.json             # Default TRSYP 3.0 FAQ (used by the frontend)
│
├── index.html
├── vite.config.js               # Proxy: /api-a→8002, /api-b→8000, /api-c→8081
├── tailwind.config.js
├── package.json
├── .env.example                 # VITE_API_A / VITE_API_B / VITE_API_C
└── .gitignore
```

---

## Shared Web Interface

The React frontend connects to all three backends simultaneously, allowing real-time approach comparison without switching tools.

### Prerequisites

- Node.js 18+
- npm or pnpm

### Installation

```powershell
npm install
# or
pnpm install
```

### Development

```powershell
npm run dev
# → http://localhost:3000
```

### Environment Variables

Copy `.env.example` to `.env` and fill in the backend URLs:

```env
# Leave empty to use Vite's local proxy (development)
VITE_API_A=                          # e.g. https://your-space.hf.space
VITE_API_B=                          # e.g. https://abc-xyz.trycloudflare.com
VITE_API_C=                          # e.g. http://localhost:8081
```

### Features

- **Chat page** — switch between approaches in one click; language auto-detected from input
- **FAQ Admin page** — inline cell editing, pagination, JSON import/export, club configuration
- **Benchmark dashboard** — live BLEU, ROUGE-L, TTFT, throughput, hallucination rate, radar chart, latency bar chart, and system reliability panel

---

## Approach A — Hugging Face Spaces

Deploys **SmolLM2-1.7B-Instruct** on HuggingFace's free CPU tier (2 vCPUs, 16 GB RAM) via Gradio. A custom **Mini-RAG** lexical filter pre-selects the top-3 most relevant FAQ entries before passing them to the model, reducing prefill latency caused by the quadratic $O(N^2)$ attention complexity on CPU.

### Deployment

Push `approach-a/` to a HuggingFace Space (SDK: Gradio). The `app.py` loads `faq.json` at startup and exposes a `/chat` API endpoint callable via `gradio_client`.

### Local FastAPI Bridge

```powershell
cd approach-a
pip install -r requirements.txt
# Set SPACE_URL in main.py or client.py, then:
uvicorn main:app --host 0.0.0.0 --port 8002
```

### Run the Benchmark

```powershell
python benchmark.py
# Results saved to benchmark_results.json
```

### Notable Design Decisions

- **Mini-RAG vs vector RAG** — the deterministic lexical filter (`O(|Q|)` hash intersection) uses zero additional RAM and handles acronyms with exact matching, unlike dense embeddings which approximate term proximity.
- **Instruction Blindness mitigation** — temperature set to `τ = 0.1` and a repetition penalty of `1.3` prevent the model from echoing the prompt instead of generating an answer.
- **Streaming interceptor** — a regex filter on the `TextIteratorStreamer` removes structural artifacts before they reach the UI.

---

## Approach B — Ollama + Cloudflare Tunnel

Runs **Qwen2.5-1.5B-Instruct** (GGUF 4-bit, ~900 MB) locally via Ollama and exposes the chatbot publicly over HTTPS through a Cloudflare Tunnel — no port forwarding, no static IP, no cloud account required.

### Prerequisites

| Component | Minimum | Recommended |
|---|---|---|
| OS | Windows 10 / macOS / Ubuntu 20.04 | Windows 11 / Ubuntu 22.04 |
| RAM | 8 GB | 16 GB |
| Storage | 5 GB free | 10 GB |
| Python | 3.9 | 3.11 |
| GPU | Not required | NVIDIA (CUDA 12+, 4 GB+ VRAM) |

### Installation

**1. Install Ollama (Windows)**

```powershell
irm https://ollama.com/install.ps1 | iex
ollama pull qwen2.5:1.5b
ollama list   # verify ~934 MB entry
```

**2. Install Cloudflare Tunnel**

```powershell
winget install Cloudflare.cloudflared
# If not recognized after install:
$env:Path += ';C:\Program Files (x86)\cloudflared\'
cloudflared --version
```

**3. Set up the Python environment**

```powershell
cd Qwen
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

**4. Configure your FAQ**

Edit `context/faq.json`:

```json
[
  {
    "q": "What are the registration dates?",
    "a": "Registration opens on March 1st, 2025.",
    "category": "registration"
  }
]
```

### Launch (three terminals)

```powershell
# Terminal 1 — Ollama (skip if already running in system tray)
ollama serve

# Terminal 2 — FastAPI + Gradio
cd Qwen
venv\Scripts\activate
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 3 — Cloudflare Tunnel
cloudflared tunnel --url http://localhost:8000
# → https://<random-id>.trycloudflare.com
```

Or use the one-click Windows launcher:

```powershell
start_chatbot_and_tunnel.cmd
```

### API Reference

| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | Gradio chat interface |
| `/chat` | POST | Answer a question from FAQ context |
| `/health` | GET | Service status and active model |
| `/benchmark` | POST | Run evaluation on a Q/A dataset |
| `/cache/stats` | GET | In-memory cache statistics |
| `/cache/clear` | DELETE | Flush the response cache |

**POST `/chat` — Request:**

```json
{
  "question": "What are the registration dates?",
  "context": ""
}
```

If `context` is empty, the server uses the FAQ loaded from `context/faq.json` at startup. Pass a custom context string to override at runtime.

**POST `/chat` — Response:**

```json
{
  "question": "What are the registration dates?",
  "answer": "Registration opens on March 1st, 2025.",
  "latency_ms": 3241.5
}
```

### Benchmarking (Approach B)

All scripts require the FastAPI server running on `localhost:8000`.

**Standard benchmark — quality + performance:**

```powershell
python benchmark.py
# → resultats_benchmark_B.json
```

Measures per-question BLEU, ROUGE-L, F1 overlap, TTFT, throughput, hallucination detection, and consistency score.

**Concurrency stress test:**

```powershell
python benchmark_concurrent.py
# → resultats_concurrent_B.json
```

Simulates 1, 3, 5, and 10 simultaneous users via Python threads. Measures latency degradation under load.

**CPU vs GPU comparison:**

```powershell
python benchmark_gpu_vs_cpu.py
```

Interactive two-phase benchmark. Forces CPU mode via `CUDA_VISIBLE_DEVICES=-1`, then restores GPU mode. Generates a side-by-side comparison table.

```powershell
# Phase 1 — Force CPU
Get-Process | Where-Object {$_.Name -like "*ollama*"} | Stop-Process -Force
$env:CUDA_VISIBLE_DEVICES = "-1"
ollama serve
# Press ENTER in the script

# Phase 2 — GPU (default)
Get-Process | Where-Object {$_.Name -like "*ollama*"} | Stop-Process -Force
$env:CUDA_VISIBLE_DEVICES = ""
ollama serve
# Press ENTER in the script
```

Results saved to `resultats_gpu_vs_cpu.json`.

**Generate benchmark charts:**

```powershell
python plot_results.py
# → benchmark_performance.png, benchmark_quality.png, benchmark_throughput.png
```

### Performance Optimizations

All environment variables must be set **before** `ollama serve`.

| Optimization | Variable / Change | Expected Gain |
|---|---|---|
| Eliminate cold start | `$env:OLLAMA_KEEP_ALIVE = "-1"` | Removes 3–9s first-request penalty |
| Flash Attention | `$env:OLLAMA_FLASH_ATTENTION = "1"` | ~20–30% faster inference |
| Parallel requests | `$env:OLLAMA_NUM_PARALLEL = "4"` | ~50% better throughput under load |
| Reduce context window | `num_ctx: 1024` in payload | ~15–25% faster per request |
| KV cache quantization | `$env:OLLAMA_KV_CACHE_TYPE = "q8_0"` | Reduces VRAM/RAM footprint |
| Response cache | Built into `main.py` (MD5, TTL=1h) | ~99% faster for repeated questions |

**Recommended startup for best performance:**

```powershell
$env:OLLAMA_KEEP_ALIVE      = "-1"
$env:OLLAMA_FLASH_ATTENTION = "1"
$env:OLLAMA_NUM_PARALLEL    = "4"
ollama serve
```

---

## Approach C — Serverless Inference API

Calls **llama-3.1-8b-instant** via the Groq free-tier API over SSE streaming, with automatic fallback to a deterministic FAQ matcher when the API is unavailable (rate limit, network error, or campus firewall).

### Prerequisites

- Python 3.9+
- A free Groq API key: https://console.groq.com

### Installation

```powershell
cd approach-c
pip install -r requirements.txt
```

Create a `.env` file:

```env
HF_API_TOKEN=your_groq_api_key_here
DEFAULT_MODEL=llama-3.1-8b-instant
BACKUP_MODEL=mixtral-8x7b-32768
LLM_TEMPERATURE=0.3
LLM_MAX_NEW_TOKENS=512
INFERENCE_TIMEOUT=30
```

### Launch

```powershell
python run_api.py --host 0.0.0.0 --port 8081
# API docs: http://localhost:8081/docs
```

### API Reference

| Endpoint | Method | Description |
|---|---|---|
| `/chat` | POST | Answer a question (FR/EN), with SSE TTFT capture |
| `/health` | GET | Service status, active approach and model |
| `/benchmark` | POST | Evaluate a Q/A dataset |
| `/metrics` | GET | Aggregated runtime metrics |
| `/docs` | GET | Swagger UI |
| `/openapi.json` | GET | OpenAPI schema |

### Notable Design Decisions

- **TTFT via SSE** — the server streams the model's response token by token; the stopwatch starts before the request and freezes on the first non-empty token, giving a real measurement of perceived latency.
- **Rate limiting** — a sliding-window counter (60 req/60s) guards the Groq API; excess requests receive HTTP 429 rather than silently queuing.
- **Deterministic fallback** — if the LLM is unavailable, a composite similarity scorer (Jaccard + SequenceMatcher + token overlap) selects the best FAQ entry. If no entry clears the threshold θ = 0.6, an out-of-scope message is returned.
- **Multi-intent handling** — the system prompt explicitly instructs the model to merge answers for compound questions into a single coherent response.
- **Migration note** — the legacy `api-inference.huggingface.co` endpoint was deprecated during development and replaced by `router.huggingface.co/v1` (OpenAI-compatible format). The final implementation uses Groq's API, which provides the same interface with better free-tier availability.

### Run Tests

```powershell
pytest approach-c/tests/ -v
```

The test suite covers: TTFT capture, BLEU/ROUGE exact-match scoring, HTTP 429 rate limiting, concurrent request counting, sliding-window reset, cold start persistence, throughput over 20 requests, high-concurrency bursts, and multi-intent FAQ matcher behavior (dominant intent, tie-breaking, dilution below threshold).

---

## Benchmarking

### Metrics

| Category | Metric | Description |
|---|---|---|
| Quality | **BLEU** | N-gram precision vs. annotated reference |
| Quality | **ROUGE-L** | Longest common subsequence recall |
| Quality | **F1 Token Overlap** | Balanced precision/recall on token sets |
| Quality | **Answer Relevance** | Keyword overlap between question and answer |
| Quality | **Hallucination Rate** | Heuristic: very low BLEU + F1 without refusal phrase |
| Quality | **Consistency Score** | F1 overlap between two independent answers to the same question |
| Performance | **TTFT** | Time to first token (streaming) |
| Performance | **End-to-end Latency** | Total response time, averaged over N requests |
| Performance | **Throughput** | Tokens generated per second post-TTFT |
| Reliability | **Rate Limit Hits** | Requests rejected by rate limiter (HTTP 429) |
| Reliability | **Cold Start** | Latency on first request after model load |
| Reliability | **Uptime** | Fraction of time the service was non-degraded |
| Reliability | **Cost** | Always 0 € |

### Comparative Results (TRSYP 3.0 Dataset, 5 Q/A pairs)

| Metric | Approach A | Approach B | Approach C |
|---|---|---|---|
| BLEU | — | 0.014 | 0.853 |
| ROUGE-L | — | 0.182 | 0.889 |
| Avg. Latency | ~48 000 ms | 4 230 ms | 279 ms |
| TTFT | — | 3 726 ms | 152 ms |
| Throughput | ~0.35 tok/s | 45.5 tok/s | 63.7 tok/s |
| Hallucination | — | 0.0 % | 0.0 % |
| Linguistic Precision | — | 100 % | 97.6 % |
| Cost | 0 € | 0 € | 0 € |

> Approach A latency reflects HF Spaces shared CPU cold start. Approach C scores reflect exact-wording instruction in the system prompt. All approaches achieve zero hallucination rate.

---

## FAQ Context Format

All three approaches share the same `faq.json` schema:

```json
[
  {
    "q": "How do I register for TRSYP 3.0?",
    "a": "Registration is not yet open. Stay tuned at https://rtc.ieee.tn/",
    "category": "registration"
  },
  {
    "q": "Where does the congress take place?",
    "a": "The venue is in Tunisia — details to be announced at https://rtc.ieee.tn/",
    "category": "logistics"
  }
]
```

To deploy UniBot for a different club, replace `faq.json` with your own data. No code changes, no retraining, no redeployment of the model — only the context file changes.

The frontend Admin page provides an inline editor with import/export, so non-technical club members can maintain the FAQ without touching any files directly.

---

## Configuration Reference

### Approach B (Ollama)

| Variable | Default | Description |
|---|---|---|
| `OLLAMA_KEEP_ALIVE` | `5m` | Time to keep model loaded after last request. Set to `-1` to disable unloading. |
| `OLLAMA_FLASH_ATTENTION` | `0` | Enable flash attention. Set to `1` on supported hardware. |
| `OLLAMA_NUM_PARALLEL` | `1` | Max concurrent inference requests. |
| `OLLAMA_KV_CACHE_TYPE` | _(none)_ | KV cache quantization: `q8_0` or `q4_0`. |
| `CUDA_VISIBLE_DEVICES` | _(auto)_ | Set to `-1` to force CPU-only mode. |

### Approach C (Groq/HF API)

| Variable | Default | Description |
|---|---|---|
| `HF_API_TOKEN` | _(required)_ | Groq or HuggingFace API key. |
| `DEFAULT_MODEL` | _(required)_ | Primary model identifier (e.g. `llama-3.1-8b-instant`). |
| `BACKUP_MODEL` | _(optional)_ | Fallback model if primary is unavailable. |
| `LLM_TEMPERATURE` | `0.3` | Sampling temperature. Lower = more deterministic. |
| `LLM_MAX_NEW_TOKENS` | `512` | Maximum tokens to generate per response. |
| `INFERENCE_TIMEOUT` | `30` | HTTP timeout in seconds for API calls. |

### Frontend (Vite)

| Variable | Description |
|---|---|
| `VITE_API_A` | Base URL for Approach A backend. Leave empty to use `/api-a` proxy. |
| `VITE_API_B` | Base URL for Approach B backend. Leave empty to use `/api-b` proxy. |
| `VITE_API_C` | Base URL for Approach C backend. Leave empty to use `/api-c` proxy. |

---

## Known Limitations

**Approach A**
- Cold start exceeds 60 seconds on HF Spaces free CPU tier after periods of inactivity.
- Shared CPU concurrency is limited; multiple simultaneous users cause significant queue buildup.
- The Mini-RAG lexical filter may miss semantically equivalent but lexically different phrasings.

**Approach B**
- The public Cloudflare URL changes on every tunnel restart in accountless mode. Use a named tunnel with a free Cloudflare account for a persistent URL.
- System availability is entirely dependent on the host machine; any sleep, shutdown, or power loss takes the chatbot offline.
- By default, Ollama processes requests sequentially on CPU. The variable `OLLAMA_KEEP_ALIVE` must be set manually to eliminate cold start penalties.
- The in-memory response cache resets on every server restart. For production use, replace the Python dict with a Redis or SQLite backend.

**Approach C**
- Depends on an active internet connection and the Groq API's availability. On campus networks where `api-inference.huggingface.co` is filtered, the system falls back to the deterministic FAQ matcher automatically.
- The free Groq tier allows approximately 30 requests per minute and 14,400 per day. Exceeding this limit triggers HTTP 429 responses until the window resets.
- The LLM's BLEU scores reflect verbatim FAQ reproduction (instructed by the system prompt); paraphrasing would yield lower BLEU but more natural responses.

---

## License

This project is licensed under the [Apache License 2.0](LICENSE).

The models used are independently licensed:
- SmolLM2-1.7B-Instruct — [Apache 2.0](https://huggingface.co/HuggingFaceTB/SmolLM2-1.7B-Instruct)
- Qwen2.5-1.5B — [Apache 2.0](https://huggingface.co/Qwen/Qwen2.5-1.5B)
- LLaMA 3.1 8B — [Meta LLaMA 3 Community License](https://llama.meta.com/llama3/license/)
