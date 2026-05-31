// All calls go through /api which Vite proxies to localhost:8000

const BASE_URLS = {
  A: import.meta.env.VITE_API_A || '/api',   // Membre 1 — HF Spaces
  B: import.meta.env.VITE_API_B || '/api-b', // Membre 2 — Qwen + Ollama local
  C: import.meta.env.VITE_API_C || '/api-c',   // Membre 3 — Serverless HF
}

function getBase(approach) {
  return BASE_URLS[approach] || BASE_URLS.A
}

// Construit le prompt injecté dans chaque requête /chat.
export function buildPrompt(question, context, lang) {
  const faqText = (context.faq || [])
    .filter(item => item.q && item.a)
    .map(item => `Q: ${item.q}\nR: ${item.a}`)
    .join('\n\n')

  if (!faqText) {
    return lang === 'fr'
      ? `Question: ${question}\nRéponse:`
      : `Question: ${question}\nAnswer:`
  }

  if (lang === 'fr') {
    return `Tu es un assistant virtuel pour ${context.club_name || 'le club'}.
      Ton rôle est de répondre aux questions des étudiants en te basant UNIQUEMENT sur la FAQ fournie ci-dessous.
      Règles strictes :
      - Si la réponse est dans la FAQ, réponds de façon claire et concise.
      - Si la question est hors sujet ou absente de la FAQ, réponds exactement : "Je ne dispose pas de cette information. Veuillez contacter l'organisation directement."
      - Ne génère jamais d'informations inventées.
      - Réponds toujours en français.
      - Maximum 3 phrases.

      FAQ de ${context.club_name || 'le club'} :
      ${faqText}

      Question de l'étudiant : ${question}
      Réponse :`
  } else {
    return `You are a virtual assistant for ${context.club_name || 'the club'}.
      Your role is to answer student questions based ONLY on the FAQ provided below.
      Strict rules:
      - If the answer is in the FAQ, respond clearly and concisely.
      - If the question is off-topic or not in the FAQ, respond exactly: "I don't have this information. Please contact the organization directly."
      - Never generate invented information.
      - Always respond in English.
      - Maximum 3 sentences.

      ${context.club_name || 'Club'} FAQ:
      ${faqText}

      Student question: ${question}
      Answer:`
  }
}

// POST /chat
export async function sendChat({ question, context, model, approach, lang }) {
  const t0 = Date.now()

  // Approach B → Qwen backend (FastAPI) expects { question, context: string }
  if (approach === 'B') {
    const faqText = (context.faq || [])
      .map(item => `Q: ${item.q || item.question}\nR: ${item.a || item.reference_answer}`)
      .join('\n\n')

    const res = await fetch(`${getBase('B')}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, context: faqText }),
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json() // { question, answer }
    return { answer: data.answer, latency_ms: Date.now() - t0 }
  }

  // Approaches A & C — generic contract
  const prompt = buildPrompt(question, context, lang)
  const res = await fetch(`${getBase(approach)}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, context: { ...context, prompt }, model, approach, lang }),
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  const data = await res.json() // { answer, latency_ms }
  return { ...data, latency_ms: data.latency_ms ?? Date.now() - t0 }
}

// GET /health
export async function getHealth(approach) {
  try {
    const res = await fetch(`${getBase(approach)}/health`)
    if (!res.ok) return { status: 'degraded', approach, model: '—' }
    return res.json() // { status, approach, model }
  } catch {
    return { status: 'degraded', approach, model: '—' }
  }
}

// GET /metrics
export async function getMetrics(approach) {
  const res = await fetch(`${getBase(approach)}/metrics`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

// POST /benchmark
export async function runBenchmark({
  approach,
  dataset,
  context,
  consistency_runs = 2,
}) {
  if (approach === 'B') {
    const faqText = (context.faq || [])
      .map(item => `Q: ${item.q || item.question}\nR: ${item.a || item.reference_answer}`)
      .join('\n\n')

    const res = await fetch(`${getBase('B')}/benchmark`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ dataset, context: faqText, approach, consistency_runs }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  }

  const res = await fetch(`${getBase(approach)}/benchmark`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ dataset, context, approach, consistency_runs }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}
