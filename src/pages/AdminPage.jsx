import { useState } from 'react'
import { Plus, Trash2, Download, Upload, Save, RefreshCw, Pencil, Check, X  } from 'lucide-react'
import { saveContext, exportContextJSON, importContextJSON, resetContext } from '../lib/context'

function EditableCell({ value, onChange, multiline = false, placeholder = '' }) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(value)

  function commit() {
    onChange(draft)
    setEditing(false)
  }

  function cancel() {
    setDraft(value)
    setEditing(false)
  }

  if (!editing) {
    return (
      <div
        onClick={() => { setDraft(value); setEditing(true) }}
        className="group flex items-start gap-2 cursor-pointer min-h-[32px] rounded-lg px-2 py-1.5
                   hover:bg-ink-muted transition-colors"
      >
        <span className={`flex-1 text-sm font-body leading-relaxed ${value ? 'text-cream/80' : 'text-cream/20 italic'}`}>
          {value || placeholder}
        </span>
        <Pencil size={12} className="text-cream/0 group-hover:text-cream/30 mt-0.5 shrink-0 transition-colors" />
      </div>
    )
  }

  return (
    <div className="flex items-start gap-1.5">
      {multiline ? (
        <textarea
          autoFocus
          value={draft}
          onChange={e => setDraft(e.target.value)}
          onKeyDown={e => { if (e.key === 'Escape') cancel() }}
          className="input-field resize-none text-sm flex-1 min-h-[72px]"
          rows={3}
        />
      ) : (
        <input
          autoFocus
          type="text"
          value={draft}
          onChange={e => setDraft(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') commit(); if (e.key === 'Escape') cancel() }}
          className="input-field text-sm flex-1 py-1.5"
          placeholder={placeholder}
        />
      )}
      <div className="flex flex-col gap-1 mt-0.5">
        <button onClick={commit} className="p-1.5 rounded-lg bg-teal/10 text-teal hover:bg-teal/20 transition-colors">
          <Check size={12} />
        </button>
        <button onClick={cancel} className="p-1.5 rounded-lg bg-ink-muted text-cream/30 hover:text-cream/60 transition-colors">
          <X size={12} />
        </button>
      </div>
    </div>
  )
}

export default function AdminPage({ context, setContext }) {
  const [saved, setSaved] = useState(false)
  const [importError, setImportError] = useState('')

  function handleSave() {
    saveContext(context)
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  function handleClubName(e) {
    setContext(c => ({ ...c, club_name: e.target.value }))
  }

  function handleLang(e) {
    setContext(c => ({ ...c, lang: e.target.value }))
  }

  function handleAddRow() {
    setContext(c => ({
      ...c,
      faq: [...(c.faq || []), { q: '', a: '', category: '' }]
    }))
  }

  function handleChangeCell(index, field, value) {
    setContext(c => {
      const faq = [...c.faq]
      faq[index] = { ...faq[index], [field]: value }
      return { ...c, faq }
    })
  }

  function handleDeleteRow(index) {
    setContext(c => ({ ...c, faq: c.faq.filter((_, i) => i !== index) }))
  }

  async function handleImport(e) {
    const file = e.target.files?.[0]
    if (!file) return
    try {
      const parsed = await importContextJSON(file)
      setContext(parsed)
      saveContext(parsed)
      setImportError('')
    } catch (err) {
      setImportError(err.message)
    }
    e.target.value = ''
  }

  function handleReset() {
    if (!confirm('Réinitialiser le contexte avec les données TRYSP par défaut ?')) return
    const def = resetContext()
    setContext(def)
  }

  const faq = context.faq || []

  return (
    <div className="flex flex-col h-screen">
      {/* Header */}
      <div className="px-8 py-5 border-b border-ink-muted flex items-center justify-between shrink-0">
        <div>
          <h1 className="font-display font-bold text-xl text-cream">Admin FAQ</h1>
        </div>
        <div className="flex items-center gap-2">
          <label className="btn-ghost flex items-center gap-1.5 cursor-pointer">
            <Upload size={14} />
            Importer JSON
            <input type="file" accept=".json" onChange={handleImport} className="hidden" />
          </label>
          <button onClick={() => exportContextJSON(context)} className="btn-ghost flex items-center gap-1.5">
            <Download size={14} />
            Exporter
          </button>
          <button onClick={handleReset} className="btn-ghost flex items-center gap-1.5">
            <RefreshCw size={14} />
            Reset
          </button>
          <button onClick={handleSave} className="btn-primary flex items-center gap-2">
            <Save size={14} />
            {saved ? 'Sauvegarde terminée' : 'Sauvegarder'}
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-8 py-6 space-y-6">
        {importError && (
          <div className="bg-coral/10 border border-coral/30 rounded-xl px-4 py-3 text-coral text-sm">
            {importError}
          </div>
        )}

        {/* Club config */}
        <div className="card p-5">
          <h2 className="font-display font-semibold text-sm text-cream/70 uppercase tracking-wider mb-4">
            Configuration du club
          </h2>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-xs font-mono text-cream/40 mb-1.5 block">Nom du club</label>
              <input
                value={context.club_name || ''}
                onChange={handleClubName}
                className="input-field"
                placeholder="ex: TRYSP, IEEE INSAT…"
              />
            </div>
            <div>
              <label className="text-xs font-mono text-cream/40 mb-1.5 block">Langue par défaut</label>
              <select value={context.lang || 'fr'} onChange={handleLang} className="input-field">
                <option value="fr">Français</option>
                <option value="en">English</option>
              </select>
            </div>
          </div>
        </div>

        {/* Table */}
        <div className="card overflow-hidden">
          {/* Table header */}
          <div className="grid grid-cols-[2rem_1fr_1.4fr_10rem_2.5rem] gap-0 border-b border-ink-muted">
            <div className="px-4 py-3 text-xs font-mono text-cream/30">#</div>
            <div className="px-4 py-3 text-xs font-mono text-cream/40 uppercase tracking-wider border-l border-ink-muted">Question</div>
            <div className="px-4 py-3 text-xs font-mono text-cream/40 uppercase tracking-wider border-l border-ink-muted">Reponse</div>
            <div className="px-4 py-3 text-xs font-mono text-cream/40 uppercase tracking-wider border-l border-ink-muted">Categorie</div>
            <div className="px-4 py-3 border-l border-ink-muted" />
          </div>
        
          {/* Rows */}
          {faq.length === 0 ? (
            <div className="py-16 text-center text-cream/20 text-sm font-body">
              Aucune entree. Cliquez sur "Ajouter une ligne".
            </div>
          ) : (
            faq.map((item, i) => (
            <div
              key={i}
              className="grid grid-cols-[2rem_1fr_1.4fr_10rem_2.5rem] gap-0 border-b border-ink-muted/40
              last:border-0 hover:bg-ink-muted/10 transition-colors group"
            >
              {/* Index */}
              <div className="px-3 py-3 flex items-start pt-4">
                <span className="font-mono text-xs text-cream/20">{i + 1}</span>
              </div>
          
              {/* Question */}
              <div className="px-3 py-2 border-l border-ink-muted/40">
                <EditableCell
                  value={item.q}
                  onChange={v => handleChangeCell(i, 'q', v)}
                  multiline
                  placeholder="Ecrire la question..."
                />
              </div>
          
              {/* Reponse */}
              <div className="px-3 py-2 border-l border-ink-muted/40">
              <EditableCell
                value={item.a}
                onChange={v => handleChangeCell(i, 'a', v)}
                multiline
                placeholder="Ecrire la reponse..."
              />
              </div>
          
              {/* Category */}
              <div className="px-3 py-2 border-l border-ink-muted/40">
              <EditableCell
                value={item.category}
                onChange={v => handleChangeCell(i, 'category', v)}
                placeholder="inscription..."
              />
              </div>
          
              {/* Delete */}
              <div className="px-2 py-3 border-l border-ink-muted/40 flex items-start justify-center pt-4">
                <button
                onClick={() => handleDeleteRow(i)}
                  className="p-1.5 rounded-lg text-cream/0 group-hover:text-cream/20
                  hover:!text-coral hover:bg-coral/10 transition-all"
                >
                  <Trash2 size={13} />
                </button>
              </div>
            </div>
            ))
          )}
        
          {/* Add row */}
          <div className="px-4 py-3 border-t border-ink-muted/40">
            <button
              onClick={handleAddRow}
              className="flex items-center gap-2 text-sm text-cream/30 hover:text-accent
              font-body transition-colors"
            >
              <Plus size={14} />
                Ajouter une ligne
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
