import { useState, useRef, useEffect } from 'react'
import { Send, Languages, AlertCircle, Sparkles } from 'lucide-react'
import { sendChat } from '../lib/api'
import { APPROACH_CONFIG } from '../lib/context'

function TypingIndicator() {
  return (
    <div style={{ display: 'flex', alignItems: 'flex-end', gap: 10 }} className="message-enter">
      <div style={{ width: 34, height: 34, borderRadius: '50%', background: 'var(--indigo-lt)', border: '2px solid rgba(61,82,160,0.2)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
        <Sparkles size={14} color="var(--indigo)" />
      </div>
      <div style={{ background: '#fff', border: '1px solid var(--border)', borderRadius: '4px 16px 16px 16px', padding: '12px 18px', display: 'flex', gap: 5, alignItems: 'center', boxShadow: 'var(--shadow-sm)' }}>
        <span className="typing-dot" /><span className="typing-dot" /><span className="typing-dot" />
      </div>
    </div>
  )
}

function Message({ msg, approach }) {
  const isBot = msg.role === 'bot'
  const cfg = APPROACH_CONFIG[approach]
  const initials = isBot ? 'AI' : 'Moi'

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: isBot ? 'flex-start' : 'flex-end', gap: 6 }} className="message-enter">
      <div style={{ display: 'flex', alignItems: 'flex-end', gap: 10, flexDirection: isBot ? 'row' : 'row-reverse' }}>
        {/* Avatar */}
        <div style={{
          width: 34, height: 34, borderRadius: '50%', flexShrink: 0,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          background: isBot ? 'var(--indigo-lt)' : 'linear-gradient(135deg, var(--indigo) 0%, var(--indigo-md) 100%)',
          border: isBot ? '2px solid rgba(61,82,160,0.2)' : 'none',
        }}>
          {isBot
            ? <Sparkles size={14} color="var(--indigo)" />
            : <span style={{ color: '#fff', fontSize: 11, fontWeight: 700, fontFamily: 'Plus Jakarta Sans, sans-serif' }}>Moi</span>
          }
        </div>

        {/* Bubble */}
        <div style={{
          maxWidth: 520,
          padding: '11px 16px',
          borderRadius: isBot ? '4px 18px 18px 18px' : '18px 4px 18px 18px',
          background: isBot ? '#fff' : 'var(--indigo)',
          border: isBot ? '1px solid var(--border)' : 'none',
          color: isBot ? 'var(--text)' : '#fff',
          fontSize: 14, lineHeight: 1.65,
          fontFamily: 'Plus Jakarta Sans, sans-serif',
          boxShadow: isBot ? 'var(--shadow-sm)' : '0 4px 14px rgba(61,82,160,0.3)',
        }}>
          {msg.content}
        </div>
      </div>

      {isBot && msg.latency_ms && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, paddingLeft: 44 }}>
          <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 10.5, color: 'var(--text-3)' }}>{msg.latency_ms}ms</span>
        </div>
      )}

      {msg.error && (
        <p style={{ fontSize: 12, color: 'var(--coral)', display: 'flex', alignItems: 'center', gap: 4, margin: 0, paddingLeft: 44 }}>
          <AlertCircle size={11} /> {msg.error}
        </p>
      )}
    </div>
  )
}

export default function ChatPage({ approach, context }) {
  const [messages, setMessages] = useState([{
    id: 0, role: 'bot',
    content: `Bonjour et bienvenue ! 👋 Je suis le chatbot de ${context.club_name || 'notre club'}. Posez-moi vos questions en français ou en anglais — je suis là pour vous aider !`,
  }])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [lang, setLang] = useState(context.lang || 'fr')
  const bottomRef = useRef(null)

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages, loading])
  useEffect(() => {
    if (!input) return
    const frWords = ['comment', 'quand', 'où', 'est-ce', 'puis-je', 'les', 'des', 'une', 'pour', 'quel']
    setLang(frWords.some(w => input.toLowerCase().includes(w)) ? 'fr' : 'en')
  }, [input])

  async function handleSend() {
    if (!input.trim() || loading) return
    const q = input.trim(); setInput('')
    setMessages(prev => [...prev, { id: Date.now(), role: 'user', content: q }])
    setLoading(true)
    try {
      const data = await sendChat({ question: q, context, model: APPROACH_CONFIG[approach].model, approach, lang })
      setMessages(prev => [...prev, { id: Date.now() + 1, role: 'bot', content: data.answer, latency_ms: data.latency_ms }])
    } catch (err) {
      setMessages(prev => [...prev, { id: Date.now() + 1, role: 'bot', content: 'Une erreur est survenue. Veuillez vérifier que le backend est actif.', error: err.message }])
    } finally { setLoading(false) }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', background: 'var(--bg)' }}>

      {/* Gradient header */}
      <div style={{
        padding: '22px 32px',
        borderBottom: '1px solid var(--border)',
        background: 'linear-gradient(135deg, #fff 60%, var(--indigo-lt) 100%)',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexShrink: 0
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          <div style={{
            width: 44, height: 44, borderRadius: 12,
            background: 'linear-gradient(135deg, var(--indigo) 0%, var(--indigo-md) 100%)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            boxShadow: '0 4px 12px rgba(61,82,160,0.28)'
          }}>
            <Sparkles size={20} color="#fff" />
          </div>
          <div>
            <h1 className="font-display font-bold text-xl" style={{ fontSize: 22, margin: 0, lineHeight: 1 }}>
              {context.club_name || 'Club FAQ'}
            </h1>
            <p style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 11, color: 'var(--text-3)', margin: '4px 0 0' }}>
              {context.faq?.length || 0} entrées · Approche <strong style={{ color: 'var(--indigo)' }}>{approach}</strong> active
            </p>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span className={`tag badge-${approach}`}>{APPROACH_CONFIG[approach].label}</span>
          <button onClick={() => setLang(l => l === 'fr' ? 'en' : 'fr')} className="btn-ghost">
            <Languages size={14} /> {lang.toUpperCase()}
          </button>
        </div>
      </div>

      {/* Messages */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '28px 32px', display: 'flex', flexDirection: 'column', gap: 18, maxWidth: 860, width: '100%', margin: '0 auto', alignSelf: 'stretch' }}>
        {messages.map(msg => <Message key={msg.id} msg={msg} approach={approach} />)}
        {loading && <TypingIndicator />}
        <div ref={bottomRef} />
      </div>

      {/* Suggested */}
      {messages.length === 1 && context.faq?.length > 0 && (
        <div style={{ padding: '0 32px 14px', maxWidth: 860, width: '100%', margin: '0 auto', alignSelf: 'stretch' }}>
          <p style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 10.5, color: 'var(--text-3)', margin: '0 0 8px', textTransform: 'uppercase', letterSpacing: '0.07em' }}>
            Questions suggérées
          </p>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 7 }}>
            {context.faq.slice(0, 4).map((item, i) => (
              <button key={i} onClick={() => setInput(item.q)}
                style={{ fontSize: 13, padding: '6px 14px', borderRadius: 20, border: '1px solid var(--border)', background: '#fff', color: 'var(--text-2)', cursor: 'pointer', fontFamily: 'Plus Jakarta Sans, sans-serif', fontWeight: 500, transition: 'all 0.15s', boxShadow: 'var(--shadow-sm)' }}
                onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--indigo-md)'; e.currentTarget.style.color = 'var(--indigo)'; e.currentTarget.style.background = 'var(--indigo-lt)' }}
                onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--border)'; e.currentTarget.style.color = 'var(--text-2)'; e.currentTarget.style.background = '#fff' }}
              >
                {item.q.length > 55 ? item.q.slice(0, 55) + '…' : item.q}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Input bar */}
      <div style={{ padding: '12px 32px 24px', flexShrink: 0, maxWidth: 860, width: '100%', margin: '0 auto', alignSelf: 'stretch' }}>
        <div style={{ display: 'flex', gap: 10, alignItems: 'flex-end', background: '#fff', borderRadius: 14, border: '1px solid var(--border)', padding: '8px 8px 8px 16px', boxShadow: '0 4px 16px rgba(0,0,0,0.07)' }}>
          <textarea value={input} onChange={e => setInput(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() } }}
            placeholder={lang === 'fr' ? 'Posez votre question…' : 'Ask your question…'}
            rows={1}
            style={{ flex: 1, resize: 'none', border: 'none', outline: 'none', background: 'transparent', fontSize: 14, fontFamily: 'Plus Jakarta Sans, sans-serif', color: 'var(--text)', lineHeight: 1.5, minHeight: 28, maxHeight: 120, paddingTop: 4 }}
            onInput={e => { e.target.style.height = 'auto'; e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px' }}
          />
          <button onClick={handleSend} disabled={!input.trim() || loading}
            style={{
              width: 38, height: 38, borderRadius: 9, border: 'none', cursor: input.trim() && !loading ? 'pointer' : 'not-allowed',
              background: input.trim() && !loading ? 'var(--indigo)' : 'var(--border)',
              color: input.trim() && !loading ? '#fff' : 'var(--text-3)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              flexShrink: 0, transition: 'all 0.18s',
              boxShadow: input.trim() && !loading ? '0 2px 8px rgba(61,82,160,0.3)' : 'none'
            }}>
            <Send size={15} />
          </button>
        </div>
      </div>
    </div>
  )
}