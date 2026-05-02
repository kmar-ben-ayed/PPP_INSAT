import { useState, useRef, useEffect } from 'react'
import { Send, Bot, User, Clock, Languages, AlertCircle } from 'lucide-react'
import { sendChat } from '../lib/api'
import { APPROACH_CONFIG } from '../lib/context'

function TypingIndicator() {
  return (
    <div className="flex items-end gap-3 message-enter">
      <div className="w-8 h-8 rounded-xl bg-teal/20 border border-teal/30 flex items-center justify-center shrink-0">
        <Bot size={14} className="text-teal" />
      </div>
      <div className="card px-4 py-3 flex gap-1.5 items-center">
        <span className="typing-dot text-cream/40" />
        <span className="typing-dot text-cream/40" />
        <span className="typing-dot text-cream/40" />
      </div>
    </div>
  )
}

function Message({ msg, approach }) {
  const isBot = msg.role === 'bot'
  const cfg = APPROACH_CONFIG[approach]

  return (
    <div className={`flex items-end gap-3 message-enter ${isBot ? '' : 'flex-row-reverse'}`}>
      {/* Avatar */}
      <div className={`w-8 h-8 rounded-xl flex items-center justify-center shrink-0
        ${isBot ? 'bg-teal/20 border border-teal/30' : 'bg-accent/20 border border-accent/30'}`}>
        {isBot ? <Bot size={14} className="text-teal" /> : <User size={14} className="text-accent" />}
      </div>

      {/* Bubble */}
      <div className={`max-w-[70%] ${isBot ? '' : 'items-end flex flex-col'}`}>
        <div className={`rounded-2xl px-4 py-3 text-sm font-body leading-relaxed
          ${isBot ? 'card text-cream/90' : 'bg-accent text-ink font-medium'}`}>
          {msg.content}
        </div>

        {/* Meta */}
        {isBot && msg.latency_ms && (
          <div className="flex items-center gap-3 mt-1.5 px-1">
            <span className="flex items-center gap-1 text-xs font-mono text-cream/25">
              <Clock size={10} />
              {msg.latency_ms}ms
            </span>
            <span className={`tag badge-${approach} text-[10px]`}>{approach} · {cfg.model}</span>
          </div>
        )}

        {msg.error && (
          <p className="text-xs text-coral/80 mt-1 px-1 flex items-center gap-1">
            <AlertCircle size={10} /> {msg.error}
          </p>
        )}
      </div>
    </div>
  )
}

export default function ChatPage({ approach, context }) {
  const [messages, setMessages] = useState([
    {
      id: 0,
      role: 'bot',
      content: `Bonjour ! Je suis le chatbot de ${context.club_name || 'INSAT'}. Je peux répondre à vos questions en français et en anglais. Comment puis-je vous aider ?`,
      latency_ms: null,
    }
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [lang, setLang] = useState(context.lang || 'fr')
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  // Detect language from input
  useEffect(() => {
    if (!input) return
    const frWords = ['comment', 'quand', 'où', 'est-ce', 'puis-je', 'les', 'des', 'une', 'pour']
    const lower = input.toLowerCase()
    const isFr = frWords.some(w => lower.includes(w))
    setLang(isFr ? 'fr' : 'en')
  }, [input])

  async function handleSend() {
    if (!input.trim() || loading) return
    const q = input.trim()
    setInput('')

    const userMsg = { id: Date.now(), role: 'user', content: q }
    setMessages(prev => [...prev, userMsg])
    setLoading(true)

    try {
      const data = await sendChat({
        question: q,
        context,
        model: APPROACH_CONFIG[approach].model,
        approach,
        lang,
      })
      setMessages(prev => [...prev, {
        id: Date.now() + 1,
        role: 'bot',
        content: data.answer,
        latency_ms: data.latency_ms,
      }])
    } catch (err) {
      setMessages(prev => [...prev, {
        id: Date.now() + 1,
        role: 'bot',
        content: 'Une erreur est survenue. Veuillez vérifier que le backend est actif.',
        error: err.message,
      }])
    } finally {
      setLoading(false)
    }
  }

  function handleKey(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="flex flex-col h-screen">
      {/* Header */}
      <div className="px-8 py-5 border-b border-ink-muted flex items-center justify-between shrink-0">
        <div>
          <h1 className="font-display font-bold text-xl text-cream">{context.club_name || 'INSAT'}</h1>
          <p className="text-xs text-cream/40 font-mono mt-0.5">
            {context.faq?.length || 0} entrées FAQ · Approche {approach} active
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className={`tag badge-${approach}`}>
            {APPROACH_CONFIG[approach].label}
          </span>
          <button
            onClick={() => setLang(l => l === 'fr' ? 'en' : 'fr')}
            className="btn-ghost flex items-center gap-1.5"
          >
            <Languages size={14} />
            {lang.toUpperCase()}
          </button>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-8 py-6 space-y-5">
        {messages.map(msg => (
          <Message key={msg.id} msg={msg} approach={approach} />
        ))}
        {loading && <TypingIndicator />}
        <div ref={bottomRef} />
      </div>

      {/* Suggested questions */}
      {messages.length === 1 && context.faq?.length > 0 && (
        <div className="px-8 pb-3">
          <p className="text-xs text-cream/30 font-mono mb-2">Questions suggérées</p>
          <div className="flex flex-wrap gap-2">
            {context.faq.slice(0, 3).map((item, i) => (
              <button
                key={i}
                onClick={() => setInput(item.q)}
                className="text-xs px-3 py-1.5 rounded-lg border border-ink-muted text-cream/50
                           hover:border-accent/30 hover:text-cream transition-all duration-200"
              >
                {item.q.length > 50 ? item.q.slice(0, 50) + '…' : item.q}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Input */}
      <div className="px-8 pb-6 pt-3 border-t border-ink-muted shrink-0">
        <div className="flex gap-3 items-end">
          <textarea
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKey}
            placeholder={lang === 'fr' ? 'Posez votre question…' : 'Ask your question…'}
            rows={1}
            className="input-field resize-none flex-1 min-h-[44px] max-h-32 py-3 leading-relaxed"
            style={{ height: 'auto' }}
            onInput={e => {
              e.target.style.height = 'auto'
              e.target.style.height = Math.min(e.target.scrollHeight, 128) + 'px'
            }}
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || loading}
            className={`w-11 h-11 rounded-xl flex items-center justify-center transition-all duration-200
              ${input.trim() && !loading
                ? 'bg-accent text-ink hover:bg-accent-hover active:scale-95'
                : 'bg-ink-muted text-cream/20 cursor-not-allowed'}`}
          >
            <Send size={16} />
          </button>
        </div>
      </div>
    </div>
  )
}
