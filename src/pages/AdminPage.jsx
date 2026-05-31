import { useState } from 'react'
import { Plus, Trash2, Download, Upload, Save, RefreshCw, Pencil, Check, X, ChevronLeft, ChevronRight } from 'lucide-react'
import { saveContext, exportContextJSON, importContextJSON, resetContext } from '../lib/context'

const PAGE_SIZE = 5

function CategoryBadge({ value }) {
  if (!value) return null
  const colors = [
    { bg: 'var(--indigo-lt)', color: 'var(--indigo)', border: 'rgba(61,82,160,0.2)' },
    { bg: 'var(--teal-lt)', color: 'var(--teal)', border: 'rgba(42,157,143,0.2)' },
    { bg: 'var(--amber-lt)', color: 'var(--amber)', border: 'rgba(232,146,90,0.25)' },
  ]
  const idx = value.charCodeAt(0) % 3
  const c = colors[idx]
  return (
    <span style={{ ...c, border: `1px solid ${c.border}`, fontSize: 11, fontFamily: 'JetBrains Mono, monospace', padding: '2px 9px', borderRadius: 20, whiteSpace: 'nowrap' }}>
      {value}
    </span>
  )
}

function EditableCell({ value, onChange, multiline = false, placeholder = '' }) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(value)

  function commit() { onChange(draft); setEditing(false) }
  function cancel() { setDraft(value); setEditing(false) }

  if (!editing) return (
    <div
      onClick={() => { setDraft(value); setEditing(true) }}
      style={{ display: 'flex', alignItems: 'flex-start', gap: 6, cursor: 'text', minHeight: 32, padding: '4px 6px', borderRadius: 6, transition: 'background 0.12s' }}
      onMouseEnter={e => e.currentTarget.style.background = '#F0F1F9'}
      onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
    >
      <span style={{ flex: 1, fontSize: 13, lineHeight: 1.55, color: value ? 'var(--text)' : 'var(--text-3)', fontStyle: value ? 'normal' : 'italic' }}>
        {value || placeholder}
      </span>
      <Pencil size={11} style={{ color: 'var(--text-3)', marginTop: 3, flexShrink: 0 }} />
    </div>
  )

  return (
    <div style={{ display: 'flex', alignItems: 'flex-start', gap: 6 }}>
      {multiline
        ? <textarea autoFocus value={draft} onChange={e => setDraft(e.target.value)} onKeyDown={e => e.key === 'Escape' && cancel()}
            className="input-field" rows={3} style={{ resize: 'none', fontSize: 13, flex: 1 }} />
        : <input autoFocus type="text" value={draft} onChange={e => setDraft(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') commit(); if (e.key === 'Escape') cancel() }}
            className="input-field" placeholder={placeholder} style={{ fontSize: 13, flex: 1 }} />
      }
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginTop: 1 }}>
        <button onClick={commit} style={{ width: 26, height: 26, borderRadius: 6, background: 'var(--indigo)', border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <Check size={12} color="#fff" />
        </button>
        <button onClick={cancel} style={{ width: 26, height: 26, borderRadius: 6, background: 'var(--bg)', border: '1px solid var(--border)', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <X size={12} color="var(--text-2)" />
        </button>
      </div>
    </div>
  )
}

export default function AdminPage({ context, setContext }) {
  const [saved, setSaved] = useState(false)
  const [importError, setImportError] = useState('')
  const [currentPage, setCurrentPage] = useState(1)

  const faq = context.faq || []
  const totalPages = Math.max(1, Math.ceil(faq.length / PAGE_SIZE))
  const pageFaq = faq.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE)

  function handleSave() { saveContext(context); setSaved(true); setTimeout(() => setSaved(false), 2000) }
  function handleAddRow() {
    setContext(c => ({ ...c, faq: [...(c.faq || []), { q: '', a: '', category: '' }] }))
    setCurrentPage(Math.ceil((faq.length + 1) / PAGE_SIZE))
  }
  function handleChangeCell(globalIdx, field, value) {
    setContext(c => { const f = [...c.faq]; f[globalIdx] = { ...f[globalIdx], [field]: value }; return { ...c, faq: f } })
  }
  function handleDeleteRow(globalIdx) {
    setContext(c => ({ ...c, faq: c.faq.filter((_, i) => i !== globalIdx) }))
    if (pageFaq.length === 1 && currentPage > 1) setCurrentPage(p => p - 1)
  }
  async function handleImport(e) {
    const file = e.target.files?.[0]; if (!file) return
    try { const parsed = await importContextJSON(file); setContext(parsed); saveContext(parsed); setImportError(''); setCurrentPage(1) }
    catch (err) { setImportError(err.message) }
    e.target.value = ''
  }
  function handleReset() {
    if (!confirm('Réinitialiser ?')) return
    const def = resetContext(); setContext(def); setCurrentPage(1)
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', background: 'var(--bg)' }}>

      {/* Header */}
      <div style={{ padding: '22px 32px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexShrink: 0, background: '#fff' }}>
        <div>
          <h1 className="font-display font-bold text-xl" style={{ fontSize: 24, margin: 0, lineHeight: 1 }}>Gestion de la FAQ</h1>
          <p style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 11, color: 'var(--text-3)', margin: '5px 0 0' }}>
            {faq.length} entrée{faq.length !== 1 ? 's' : ''} · Page {currentPage}/{totalPages}
          </p>
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <label className="btn-ghost" style={{ cursor: 'pointer' }}>
            <Upload size={14} /> Importer
            <input type="file" accept=".json" onChange={handleImport} style={{ display: 'none' }} />
          </label>
          <button onClick={() => exportContextJSON(context)} className="btn-ghost"><Download size={14} /> Exporter</button>
          <button onClick={handleReset} className="btn-ghost"><RefreshCw size={14} /></button>
          <button onClick={handleSave} className="btn-primary">
            <Save size={14} /> {saved ? '✓ Sauvegardé' : 'Sauvegarder'}
          </button>
        </div>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: '24px 32px', display: 'flex', flexDirection: 'column', gap: 20 }}>
        {importError && (
          <div style={{ background: 'var(--coral-lt)', border: '1px solid #F5BABA', borderRadius: 8, padding: '10px 16px', color: 'var(--coral)', fontSize: 13 }}>
            {importError}
          </div>
        )}

        {/* Config card */}
        <div className="card" style={{ padding: '15px 24px' }}>
          <p style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 10.5, color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '0.08em', margin: '0 0 16px' }}>
            Configuration du club
          </p>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
            <div>
              <label style={{ fontSize: 12, color: 'var(--text-2)', display: 'block', marginBottom: 3, fontWeight: 500 }}>Nom du club</label>
              <input value={context.club_name || ''} onChange={e => setContext(c => ({ ...c, club_name: e.target.value }))}
                className="input-field" placeholder="ex: IEEE INSAT, TRYSP…" />
            </div>
            <div>
              <label style={{ fontSize: 12, color: 'var(--text-2)', display: 'block', marginBottom: 3, fontWeight: 500 }}>Langue par défaut</label>
              <select value={context.lang || 'fr'} onChange={e => setContext(c => ({ ...c, lang: e.target.value }))} className="input-field">
                <option value="fr">Français</option>
                <option value="en">English</option>
              </select>
            </div>
          </div>
        </div>

        {/* Table card */}
        <div className="card" style={{ overflow: 'hidden', display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          {/* Header row */}
          <div style={{ display: 'grid', gridTemplateColumns: '44px 1fr 1.4fr 140px 44px', background: 'var(--indigo-lt)', borderBottom: '1px solid rgba(61,82,160,0.15)' }}>
            {['#', 'Question', 'Réponse', 'Catégorie', ''].map((h, i) => (
              <div key={i} style={{ padding: '10px 14px', fontFamily: 'JetBrains Mono, monospace', fontSize: 10.5, color: 'var(--indigo)', textTransform: 'uppercase', letterSpacing: '0.07em', borderLeft: i > 0 ? '1px solid rgba(61,82,160,0.12)' : 'none' }}>
                {h}
              </div>
            ))}
          </div>

          <div style={{ flex: 1, minHeight: 0, overflowY: 'auto' }}>
            {pageFaq.length === 0 ? (
              <div style={{ padding: '56px 0', textAlign: 'center' }}>
                <p style={{ color: 'var(--text-3)', fontSize: 14, margin: 0 }}>Aucune entrée.</p>
                <p style={{ color: 'var(--text-3)', fontSize: 12, margin: '6px 0 0' }}>Cliquez sur « Ajouter une ligne » pour commencer.</p>
              </div>
            ) : pageFaq.map((item, localIdx) => {
              const globalIdx = (currentPage - 1) * PAGE_SIZE + localIdx
              return (
                <div
                  key={globalIdx}
                  style={{
                    display: 'grid', gridTemplateColumns: '44px 1fr 1.4fr 140px 44px',
                    borderBottom: localIdx < pageFaq.length - 1 ? '1px solid var(--border)' : 'none',
                    background: localIdx % 2 === 0 ? '#fff' : '#FAFAF9',
                    transition: 'background 0.12s',
                  }}
                  onMouseEnter={e => e.currentTarget.style.background = '#F2F3FB'}
                  onMouseLeave={e => e.currentTarget.style.background = localIdx % 2 === 0 ? '#fff' : '#FAFAF9'}
                >
                  <div style={{ padding: '14px 10px 14px 16px', fontFamily: 'JetBrains Mono, monospace', fontSize: 11, color: 'var(--text-3)' }}>
                    {globalIdx + 1}
                  </div>
                  <div style={{ padding: '8px 12px', borderLeft: '1px solid var(--border)' }}>
                    <EditableCell value={item.q} onChange={v => handleChangeCell(globalIdx, 'q', v)} multiline placeholder="Saisissez la question…" />
                  </div>
                  <div style={{ padding: '8px 12px', borderLeft: '1px solid var(--border)' }}>
                    <EditableCell value={item.a} onChange={v => handleChangeCell(globalIdx, 'a', v)} multiline placeholder="Saisissez la réponse…" />
                  </div>
                  <div style={{ padding: '10px 12px', borderLeft: '1px solid var(--border)', display: 'flex', alignItems: 'flex-start', paddingTop: 13 }}>
                    {item.category
                      ? <CategoryBadge value={item.category} />
                      : <EditableCell value={item.category} onChange={v => handleChangeCell(globalIdx, 'category', v)} placeholder="Catégorie…" />
                    }
                  </div>
                  <div style={{ borderLeft: '1px solid var(--border)', display: 'flex', alignItems: 'flex-start', justifyContent: 'center', paddingTop: 13 }}>
                    <button
                      onClick={() => handleDeleteRow(globalIdx)}
                      style={{ width: 28, height: 28, borderRadius: 6, border: 'none', background: 'transparent', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-3)', transition: 'all 0.15s' }}
                      onMouseEnter={e => { e.currentTarget.style.background = 'var(--coral-lt)'; e.currentTarget.style.color = 'var(--coral)' }}
                      onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = 'var(--text-3)' }}
                    >
                      <Trash2 size={13} />
                    </button>
                  </div>
                </div>
              )
            })}
          </div>

          {/* Footer: add + pagination */}
          <div style={{ padding: '12px 16px', borderTop: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10, flexWrap: 'wrap', background: 'var(--bg)', flexShrink: 0 }}>
            <button
              onClick={handleAddRow}
              style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, color: 'var(--indigo)', background: 'none', border: 'none', cursor: 'pointer', fontWeight: 500, fontFamily: 'Plus Jakarta Sans, sans-serif', padding: '4px 6px', borderRadius: 6, transition: 'background 0.15s' }}
              onMouseEnter={e => e.currentTarget.style.background = 'var(--indigo-lt)'}
              onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
            >
              <Plus size={14} /> Ajouter une ligne
            </button>

            {/* Pagination */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap', justifyContent: 'flex-end' }}>
              <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 11, color: 'var(--text-3)' }}>
                {pageFaq.length} / {PAGE_SIZE} visibles
              </span>
              {totalPages > 1 && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <button
                    onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                    disabled={currentPage === 1}
                    style={{ width: 30, height: 30, borderRadius: 7, border: '1px solid var(--border)', background: '#fff', cursor: currentPage === 1 ? 'not-allowed' : 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', color: currentPage === 1 ? 'var(--text-3)' : 'var(--text)' }}
                  >
                    <ChevronLeft size={14} />
                  </button>

                  {Array.from({ length: totalPages }, (_, i) => i + 1)
        .filter(p => p === 1 || p === totalPages || Math.abs(p - currentPage) <= 1)
        .reduce((acc, p, idx, arr) => {
          if (idx > 0 && p - arr[idx - 1] > 1) acc.push('...')
          acc.push(p)
          return acc
        }, [])
        .map((p, i) =>
          p === '...'
            ? <span key={`ellipsis-${i}`} style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 12, color: 'var(--text-3)', padding: '0 2px' }}>…</span>
            : <button
                key={p}
                onClick={() => setCurrentPage(p)}
                style={{
                  width: 30, height: 30, borderRadius: 7, border: '1px solid',
                  borderColor: p === currentPage ? 'var(--indigo)' : 'var(--border)',
                  background: p === currentPage ? 'var(--indigo)' : '#fff',
                  color: p === currentPage ? '#fff' : 'var(--text-2)',
                  fontFamily: 'JetBrains Mono, monospace', fontSize: 12,
                  cursor: 'pointer', fontWeight: 500, transition: 'all 0.15s',
                }}
              >
                {p}
              </button>
        )
      }

                  <button
                    onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                    disabled={currentPage === totalPages}
                    style={{ width: 30, height: 30, borderRadius: 7, border: '1px solid var(--border)', background: '#fff', cursor: currentPage === totalPages ? 'not-allowed' : 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', color: currentPage === totalPages ? 'var(--text-3)' : 'var(--text)' }}
                  >
                    <ChevronRight size={14} />
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}