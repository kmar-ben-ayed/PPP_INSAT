import { MessageSquare, Settings, BarChart3, BookOpen, Zap } from 'lucide-react'
import { APPROACH_CONFIG } from '../lib/context'

const NAV = [
  { id: 'chat',      icon: MessageSquare, label: 'Chat' },
  { id: 'admin',     icon: Settings,      label: 'Admin FAQ' },
  { id: 'benchmark', icon: BarChart3,     label: 'Benchmark' },
]

export default function Sidebar({ page, setPage, approach, setApproach, health }) {
  return (
    <aside className="w-60 shrink-0 flex flex-col bg-ink-soft border-r border-ink-muted h-screen sticky top-0">
      {/* Logo */}
      <div className="px-5 pt-6 pb-5 border-b border-ink-muted">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 bg-accent rounded-lg flex items-center justify-center">
            <Zap size={16} className="text-ink" />
          </div>
          <div>
            <p className="font-display font-bold text-sm text-cream leading-none">ChatBot</p>
            <p className="font-mono text-xs text-cream/40 mt-0.5">INSAT · SLM</p>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-1">
        {NAV.map(({ id, icon: Icon, label }) => (
          <button
            key={id}
            onClick={() => setPage(id)}
            className={`nav-item w-full text-left ${page === id ? 'nav-item-active' : 'nav-item-inactive'}`}
          >
            <Icon size={16} />
            {label}
          </button>
        ))}
      </nav>

      {/* Approach selector */}
      <div className="px-4 pb-5 border-t border-ink-muted pt-4">
        <p className="text-xs font-mono text-cream/30 uppercase tracking-widest mb-3">Approche active</p>
        <div className="space-y-1.5">
          {Object.entries(APPROACH_CONFIG).map(([key, cfg]) => {
            const isActive = approach === key
            const badgeClass = `badge-${key}`
            const dot = health[key]?.status === 'ok' ? 'bg-teal' : 'bg-coral'
            return (
              <button
                key={key}
                onClick={() => setApproach(key)}
                className={`w-full text-left rounded-xl px-3 py-2.5 border transition-all duration-200
                  ${isActive
                    ? 'bg-ink-muted border-cream/10'
                    : 'border-transparent hover:bg-ink-muted'}`}
              >
                <div className="flex items-center justify-between mb-0.5">
                  <span className={`tag ${badgeClass} text-xs`}>{key}</span>
                  <span className={`w-2 h-2 rounded-full ${dot}`} title={health[key]?.status} />
                </div>
                <p className="text-xs text-cream/50 font-body leading-snug mt-1">{cfg.desc}</p>
                {isActive && (
                  <p className="text-xs font-mono text-accent/80 mt-1">{cfg.model}</p>
                )}
              </button>
            )
          })}
        </div>
      </div>
    </aside>
  )
}
