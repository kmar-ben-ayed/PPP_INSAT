// the JSON object injected into every /chat call.
// Stored in localStorage so it persists across page reloads.
// Each club uploads/edits their own JSON: no server needed.

const STORAGE_KEY = 'chatbot_context'

const DEFAULT_CONTEXT = {
  club_name: 'TRYSP',
  lang: 'fr',
  faq: [
    {
      q: "Quelles sont les dates limites d'inscription ?",
      a: "Les inscriptions sont ouvertes jusqu'au 15 mai 2025. Veuillez remplir le formulaire en ligne sur notre site.",
      category: 'inscription',
    },
    {
      q: "Où se déroule l'événement ?",
      a: "L'événement se déroule à l'INSAT, Tunis. Des navettes seront disponibles depuis la station de métro.",
      category: 'logistique',
    },
    {
      q: "Comment contacter le comité organisateur ?",
      a: "Vous pouvez nous joindre par email à contact@trysp.tn ou via nos réseaux sociaux Instagram @trysp_insat.",
      category: 'contacts',
    },
  ],
}

export function loadContext() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : DEFAULT_CONTEXT
  } catch {
    return DEFAULT_CONTEXT
  }
}

export function saveContext(ctx) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(ctx, null, 2))
}

export function resetContext() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(DEFAULT_CONTEXT, null, 2))
  return DEFAULT_CONTEXT
}

export function exportContextJSON(ctx) {
  const blob = new Blob([JSON.stringify(ctx, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${ctx.club_name || 'context'}_faq.json`
  a.click()
  URL.revokeObjectURL(url)
}

export function importContextJSON(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = (e) => {
      try {
        const parsed = JSON.parse(e.target.result)
        resolve(parsed)
      } catch {
        reject(new Error('JSON invalide'))
      }
    }
    reader.readAsText(file)
  })
}

export const CATEGORIES = ['inscription', 'programme', 'logistique', 'opportunités', 'contacts']

export const APPROACH_CONFIG = {
  A: { label: 'Hugging Face Spaces', model: 'Phi-3 Mini / SmolLM2', color: 'teal', desc: 'CPU Cloud HF — zéro config serveur' },
  B: { label: 'Ollama + Cloudflare', model: 'Qwen2.5-1.5B', color: 'accent', desc: 'Machine locale — contrôle total' },
  C: { label: 'Serverless HF API', model: 'SmolLM2', color: 'coral', desc: 'REST API — setup en < 1h' },
}
