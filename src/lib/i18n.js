import fr from '../locales/fr.json'
import en from '../locales/en.json'

const locales = { fr, en }

export function t(key, lang = 'fr', vars = {}) {
  const locale = locales[lang] ?? locales['fr']
  const keys = key.split('.')
  let val = locale
  for (const k of keys) {
    val = val?.[k]
    if (val === undefined) break
  }
  // Fallback to French if key missing in target lang
  if (val === undefined) {
    val = keys.reduce((o, k) => o?.[k], locales['fr'])
  }
  if (typeof val !== 'string') return key
  // Replace {{var}} placeholders
  return val.replace(/\{\{(\w+)\}\}/g, (_, name) => vars[name] ?? `{{${name}}}`)
}