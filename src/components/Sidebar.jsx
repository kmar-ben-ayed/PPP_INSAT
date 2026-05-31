import { MessageSquare, Settings, BarChart3 } from 'lucide-react'
import { APPROACH_CONFIG } from '../lib/context'
import { t } from '../lib/i18n'


const NAV = [
  { id: 'chat',      icon: MessageSquare,labelKey: 'sidebar.nav_chat' },
  { id: 'admin',     icon: Settings,     labelKey: 'sidebar.nav_admin' },
  { id: 'benchmark', icon: BarChart3,     labelKey: 'sidebar.nav_benchmark' },
]

export default function Sidebar({ page, setPage, approach, setApproach, health, lang  }) {
  return (
    <aside style={{
      width: 236, flexShrink: 0,
      display: 'flex', flexDirection: 'column',
      background: '#fff',
      borderRight: '1px solid var(--border)',
      height: '100vh', position: 'sticky', top: 0,
      boxShadow: '2px 0 12px rgba(0,0,0,0.04)',
    }}>

      {/* Identity */}
      <div style={{ padding: '28px 20px 15px', borderBottom: '1px solid var(--border)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8, flexDirection: 'row', justifyContent: 'center' }}>
        <div style={{
          width: 60, height: 40, borderRadius: 10,
          background: 'linear-gradient(135deg, var(--indigo) 0%, var(--indigo-md) 100%)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          marginBottom: 12, boxShadow: '0 4px 10px rgba(61,82,160,0.3)'
        }}>
          <span style={{ color: '#fff', fontFamily: 'DM Serif Display, serif', fontSize: 12, fontStyle: 'italic', fontWeight: 700, lineHeight: 1 }}>
            TRYSP
            </span>
        </div>
                <div style={{ display: 'flex', alignItems: 'center', marginBottom: 4, flexDirection: 'column', justifyContent: 'center' }}>
        <p className="font-display font-bold text-xl" style={{ fontSize: 17, fontWeight: 600, color: 'var(--text)', margin: 0, lineHeight: 1.2 }}>
          Club IEEE INSAT
        </p>
        <p style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 10.5, color: 'var(--text-3)', margin: 0, lineHeight: 1.4 }}>
          {t('sidebar.slogan', lang)}
        </p>
        </div>
          </div>
      
      </div>

      {/* Nav */}
      <nav style={{ flex: 1, padding: '14px 10px', display: 'flex', flexDirection: 'column', gap: 3 }}>
        {NAV.map(({ id, icon: Icon, labelKey }) => (
          <button
            key={id}
            onClick={() => setPage(id)}
            className={`nav-item ${page === id ? 'nav-item-active' : 'nav-item-inactive'}`}
          >
            <Icon size={16} />
            {t(labelKey, lang)}
          </button>
        ))}
      </nav>

      {/* Approach selector */}
      <div style={{ padding: '12px 10px 22px', borderTop: '1px solid var(--border)' }}>
        <p style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '10px', color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '0.09em', margin: '0 4px 10px' }}>
          {t('sidebar.approach_label', lang)}
        </p>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
          {Object.entries(APPROACH_CONFIG).map(([key, cfg]) => {
            const isActive = approach === key
            const statusOk = health[key]?.status === 'ok'
            return (
              <button
                key={key}
                onClick={() => setApproach(key)}
                style={{
                  width: '100%', textAlign: 'left',
                  borderRadius: 8, padding: '9px 12px',
                  background: isActive ? 'var(--indigo-lt)' : 'transparent',
                  border: isActive ? '1px solid rgba(61,82,160,0.2)' : '1px solid transparent',
                  cursor: 'pointer', transition: 'all 0.15s',
                }}
                onMouseEnter={e => { if (!isActive) e.currentTarget.style.background = 'var(--bg)' }}
                onMouseLeave={e => { if (!isActive) e.currentTarget.style.background = 'transparent' }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
                  <span className={`tag badge-${key}`}>{key}</span>
                  <span style={{
                    width: 7, height: 7, borderRadius: '50%',
                    background: statusOk ? 'var(--teal)' : 'var(--coral)',
                    display: 'inline-block', flexShrink: 0
                  }} title={health[key]?.status} />
                </div>
                <p style={{ fontFamily: 'Plus Jakarta Sans, sans-serif', fontSize: 11.5, color: 'var(--text-2)', margin: 0, lineHeight: 1.4 }}>{cfg.desc}</p>
                {isActive && (
                  <p style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 10.5, color: 'var(--indigo)', margin: '4px 0 0' }}>{cfg.model}</p>
                )}
              </button>
            )
          })}
        </div>
      </div>
    </aside>
  )
}