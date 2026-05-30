// the JSON object injected into every /chat call.
// Stored in localStorage so it persists across page reloads.
// Each club uploads/edits their own JSON: no server needed.

const STORAGE_KEY = 'chatbot_context'

const DEFAULT_CONTEXT = {
  club_name: 'TRYSP',
  lang: 'en',
  faq: [
    {
      "q": "How do I register for TRSYP 3.0?",
      "a": "Registration is not yet open. Stay tuned at https://rtc.ieee.tn/ for the registration link once it goes live.",
      "category": "registration"
    },
    {
      "q": "When does registration open?",
      "a": "Registration is coming soon. Visit https://rtc.ieee.tn/ to stay updated on the opening date.",
      "category": "registration"
    },
    {
      "q": "Is there a registration fee?",
      "a": "To be determined — stay tuned at https://rtc.ieee.tn/",
      "category": "registration"
    },
    {
      "q": "Do I need to be an IEEE member to participate?",
      "a": "To be determined — stay tuned at https://rtc.ieee.tn/",
      "category": "registration"
    },
    {
      "q": "Is registration open to participants from outside Tunisia?",
      "a": "TRSYP 3.0 brings together participants from across Tunisia and beyond, so international participants are welcome. For registration details, stay tuned at https://rtc.ieee.tn/",
      "category": "registration"
    },
    {
      "q": "How many spots are available?",
      "a": "The congress is expected to host 350+ participants. Seats are limited — register early once registration opens.",
      "category": "registration"
    },
    {
      "q": "Can I register as part of a team?",
      "a": "To be determined — stay tuned at https://rtc.ieee.tn/",
      "category": "registration"
    },
    {
      "q": "Is there a separate participant form after registering?",
      "a": "Yes. During the pre-conference phase, participants will be asked to complete registration and participant forms to secure their spot and customize their experience.",
      "category": "registration"
    },
    {
      "q": "What is the registration deadline?",
      "a": "To be determined — stay tuned at https://rtc.ieee.tn/",
      "category": "registration"
    },
    {
      "q": "Can I cancel or transfer my registration?",
      "a": "To be determined — stay tuned at https://rtc.ieee.tn/",
      "category": "registration"
    },

    {
      "q": "What are the dates of TRSYP 3.0?",
      "a": "17-18 October 2026.",
      "category": "program"
    },
    {
      "q": "What is the theme of TRSYP 3.0?",
      "a": "The theme is Human-Robot Symbiosis, exploring the co-design of human-centered solutions that integrate robotic capabilities — perception, autonomy, and precision — with human strengths such as decision-making, ethics, and adaptability.",
      "category": "program"
    },
    {
      "q": "What is the Robotic Human Library?",
      "a": "It is a pre-conference activity running in September 2026, serving as a preview of the congress experience. Further details have not yet been announced — stay tuned at https://rtc.ieee.tn/",
      "category": "program"
    },
    {
      "q": "How many workshops are there and can I choose?",
      "a": "On Day 2, there are 4 workshops running in parallel at 09:00. Participants choose the track that fits their passion and skill level.",
      "category": "program"
    },
    {
      "q": "What topics will the workshops cover?",
      "a": "Workshop topics have not been announced yet — stay tuned at https://rtc.ieee.tn/",
      "category": "program"
    },
    {
      "q": "What is the Technical Challenge?",
      "a": "The Technical Challenge is launched on Day 1 at 14:00 alongside a workshop/round table. It involves robotics challenges evaluated on technical performance, societal impact, inclusive design, and ethical compliance. Specific details have not been announced — stay tuned at https://rtc.ieee.tn/",
      "category": "program"
    },
    {
      "q": "What is the Non-Technical Challenge?",
      "a": "The Non-Technical Challenge is a section-specific challenge launched on Day 1 at 14:00. Further details have not been announced — stay tuned at https://rtc.ieee.tn/",
      "category": "program"
    },
    {
      "q": "Is there a poster session?",
      "a": "Yes. On Day 1 at 10:30, there is a Poster Session where participants present research posters alongside the robotics exposition.",
      "category": "program"
    },
    {
      "q": "What is the Enterprise Exhibition?",
      "a": "The Enterprise Exhibition runs throughout both days, featuring company exhibits showcasing cutting-edge robotics and AI solutions.",
      "category": "program"
    },
    {
      "q": "Is there a gala dinner?",
      "a": "Yes. On Day 1 at 19:00, there is a gala dinner described as a taste of Tunisia with fellow innovators.",
      "category": "program"
    },
    {
      "q": "What happens at the Opening Ceremony?",
      "a": "The Opening Ceremony takes place on Day 1 at 09:00 and includes keynote addresses and an expert panel on Human-Robot Symbiosis, lasting up to one hour.",
      "category": "program"
    },
    {
      "q": "What is the Leadership Meeting?",
      "a": "The Leadership Meeting is a section-specific leadership roundtable on Day 2 at 11:00, aimed at shaping the future of IEEE RAS in Tunisia.",
      "category": "program"
    },
    {
      "q": "What is the pre-conference phase?",
      "a": "The pre-conference phase takes place in September 2026 and includes completing participant forms, distributing official invitations, and a special collaboration preview with ALECSO and INSAT.",
      "category": "program"
    },
    {
      "q": "Who are the speakers?",
      "a": "Speakers have not been announced yet — stay tuned at https://rtc.ieee.tn/",
      "category": "program"
    },
    {
      "q": "Is there a DJ night or social activities?",
      "a": "Yes. On the evening of Day 1, after competition rounds, there is a live DJ set followed by curated social team activities at 22:30.",
      "category": "program"
    },

    {
      "q": "Where does TRSYP 3.0 take place?",
      "a": "The venue is in Tunisia but has not been announced yet — stay tuned at https://rtc.ieee.tn/",
      "category": "logistics"
    },
    {
      "q": "Is accommodation included or provided?",
      "a": "To be determined — stay tuned at https://rtc.ieee.tn/",
      "category": "logistics"
    },
    {
      "q": "Are meals included in the congress?",
      "a": "The program includes a gala dinner on Day 1 evening and a buffet lunch on Day 2. Participants can have also Breakfast, Lunch and dinner as hotel residents",
      "category": "logistics"
    },
    {
      "q": "Is transportation to the venue organized?",
      "a": "To be determined — stay tuned at https://rtc.ieee.tn/",
      "category": "logistics"
    },
    {
      "q": "Is there a dress code?",
      "a": "To be determined — stay tuned at https://rtc.ieee.tn/",
      "category": "logistics"
    },
    {
      "q": "What language will the congress be in?",
      "a": "English is used for professional communication and Arabic is used for casual communication",
      "category": "logistics"
    },
    {
      "q": "Is there WiFi available on-site?",
      "a": "YES!",
      "category": "logistics"
    },
    {
      "q": "Can I bring my own robotics hardware or equipment?",
      "a": "To be determined — stay tuned at https://rtc.ieee.tn/",
      "category": "logistics"
    },
    {
      "q": "What should I prepare before arriving?",
      "a": "During the pre-conference phase, you will be asked to complete registration and participant forms. Further preparation guidelines have not been announced — stay tuned at https://rtc.ieee.tn/",
      "category": "logistics"
    },
    {
      "q": "How many days does the congress last?",
      "a": "TRSYP 3.0 spans 2 full days, with a pre-conference phase in September 2026.",
      "category": "logistics"
    },

    {
      "q": "Will participants receive a certificate?",
      "a": "To be determined — stay tuned at https://rtc.ieee.tn/",
      "category": "opportunities"
    },
    {
      "q": "Are there prizes for competition winners?",
      "a": "Yes. The Closing Ceremony includes awards for Technical Challenge winners, Non-Technical Challenge winners, and Competition winners. Prize details have not been announced — stay tuned at https://rtc.ieee.tn/",
      "category": "opportunities"
    },
    {
      "q": "What is the Best Ambassador & Coordinator award?",
      "a": "It is an award given at the Closing Ceremony. Eligibility and selection criteria have not been announced — stay tuned at https://rtc.ieee.tn/",
      "category": "opportunities"
    },
    {
      "q": "Can companies or sponsors exhibit at the congress?",
      "a": "Yes. The congress features a 2-day Enterprise Exhibition. For sponsorship and exhibition details, visit https://rtc.ieee.tn/",
      "category": "opportunities"
    },
    {
      "q": "Can I submit a research poster?",
      "a": "The program includes a Poster Session on Day 1. Submission details and deadlines have not been announced — stay tuned at https://rtc.ieee.tn/",
      "category": "opportunities"
    },
    {
      "q": "Are Young Professionals (YPs) welcome?",
      "a": "Yes. TRSYP is explicitly the IEEE Tunisian RAS Student & Young Professional Congress — YPs are a core target audience.",
      "category": "opportunities"
    },
    {
      "q": "Is this a good networking opportunity?",
      "a": "Yes. The congress brings together 350+ engineers, students, and Young Professionals from Tunisia and beyond, with dedicated networking time during the Exhibition, Poster Session, dinner, and social activities.",
      "category": "opportunities"
    },
    {
      "q": "How does TRSYP 3.0 differ from previous editions?",
      "a": "TRSYP 3.0 is the third edition. It introduces Human-Robot Symbiosis as its central theme, with evaluation criteria that go beyond technical performance to include societal impact, inclusive design, and ethical compliance.",
      "category": "opportunities"
    },
    {
      "q": "Who organizes TRSYP 3.0?",
      "a": "TRSYP 3.0 is organized by the IEEE INSAT Student Branch in collaboration with the IEEE RAS Tunisia Section.",
      "category": "contacts"
    },
    {
      "q": "How can I contact the organizing team?",
      "a": "You can contact the organizing committee through TRSYP social media channels. Links are available at https://rtc.ieee.tn/",
      "category": "contacts"
    },
    {
      "q": "How can I become a sponsor or partner?",
      "a": "You can contact the Chairwoman Rayhane Sahli (rayhanesahli56@gmail.com)",
      "category": "contacts"
    },
    {
      "q": "Where can I follow TRSYP 3.0 updates?",
      "a": "follow TRSYP 3.0 on their official social media channels. Links are available at https://rtc.ieee.tn/",
      "category": "contacts"
    }
  ]
  ,
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
  A: {
    label: "Hugging Face Spaces",
    model: "Phi-3 Mini / SmolLM2",
    color: "teal",
    desc: "CPU Cloud HF — zéro config serveur",
  },
  B: {
    label: "Ollama + Cloudflare",
    model: "Qwen2.5-1.5B",
    color: "accent",
    desc: "Machine locale — contrôle total",
  },
  C: {
    label: "Serverless HF API",
    model: "zephyr-7b-beta",
    color: "coral",
    desc: "REST API — setup en < 1h",
  },
};
