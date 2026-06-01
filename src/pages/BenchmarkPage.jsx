import { useState, useEffect } from 'react'
import { Play, Upload, XCircle, TrendingUp, Clock, Zap, ShieldCheck } from 'lucide-react'
import { runBenchmark, getMetrics, getLatestBenchmark } from '../lib/api'
import { RadarChart, Radar, PolarGrid, PolarAngleAxis, ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, Cell } from 'recharts'
import { APPROACH_CONFIG, loadContext } from '../lib/context'
import faqData from '../data/faq.json'
import { t } from '../lib/i18n'


const DEFAULT_DATASET = faqData
.sort(() => Math.random() - 0.5)
.slice(0, 10)
.map(e => ({
  question: e.q,
  reference_answer: e.a,
  category: e.category || 'general'
}))

const METRIC_LABELS = {
  bleu: 'BLEU',
  rouge_l: 'ROUGE-L',
  contextual_relevance_rate: 'Pertinence',
  lang_accuracy: 'Langue',
  consistency_rate: 'Cohérence',
}

const APPROACH_COLORS = { A: '#2A9D8F', B: '#3D52A0', C: '#E8925A' }

function KpiCard({ label, value, unit = '', icon: Icon, color = 'var(--indigo)', good, warn }) {
  const num = typeof value === 'number' ? value : null
  const display = num === null ? '—' : unit === '%' ? (num * 100).toFixed(1) : Number.isInteger(num) ? num : num.toFixed(1)
  const statusColor = num === null ? 'var(--text-3)'
    : num >= good ? 'var(--teal)' : num >= warn ? 'var(--amber)' : 'var(--coral)'

  return (
    <div className="card" style={{ padding: '18px 20px', display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 10.5, color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '0.07em' }}>{label}</span>
        <div style={{ width: 30, height: 30, borderRadius: 8, background: `${color}18`, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <Icon size={14} color={color} />
        </div>
      </div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 4 }}>
        <span style={{ fontFamily: 'Playfair Display, serif', fontSize: 28, fontWeight: 700, color: statusColor, lineHeight: 1 }}>{display}</span>
        {unit && <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 12, color: 'var(--text-3)' }}>{unit}</span>}
      </div>
    </div>
  )
}

function SectionLabel({ children }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
      <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 10.5, color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '0.09em' }}>{children}</span>
      <div style={{ flex: 1, height: 1, background: 'var(--border)' }} />
    </div>
  )
}

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div style={{ background: '#fff', border: '1px solid var(--border)', borderRadius: 8, padding: '8px 14px', boxShadow: 'var(--shadow-md)' }}>
      <p style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 11, color: 'var(--text-2)', margin: 0 }}>{label}</p>
      <p style={{ fontFamily: 'Playfair Display, serif', fontSize: 18, color: 'var(--text)', margin: '2px 0 0', fontWeight: 700 }}>{payload[0].value}</p>
    </div>
  )
}

export default function BenchmarkPage({ approach, lang  }) {
  const [results, setResults] = useState(null)
  const [metrics, setMetrics] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [dataset, setDataset] = useState(DEFAULT_DATASET)

  useEffect(() => {
    let active = true;
    async function loadLatest() {
      setLoading(true); setError(''); setResults(null); setMetrics(null);
      try {
        const [latest, met] = await Promise.all([
          getLatestBenchmark(approach),
          getMetrics(approach).catch(() => null)
        ])
        if (active && latest) {
          setResults(latest)
          setMetrics(met)
        }
      } catch (err) {
        console.error(err)
      } finally {
        if (active) setLoading(false)
      }
    }
    loadLatest()
    return () => { active = false }
  }, [approach])

  async function handleRun() {
    setLoading(true); setError('')
    try {
      const [bench, met] = await Promise.all([runBenchmark({ approach, dataset }), getMetrics(approach)])
      setResults(bench); setMetrics(met)
    } catch (err) { setError(err.message) }
    finally { setLoading(false) }
  }

  async function handleImport(e) {
    const file = e.target.files?.[0]; if (!file) return
    try { setDataset(JSON.parse(await file.text())) } catch { setError('JSON invalide') }
    e.target.value = ''
  }

  const radarData = results ? Object.entries(METRIC_LABELS).map(([k, name]) => ({ metric: name, value: +(results[k] * 100).toFixed(1) })) : []
  const latencyData = results ? [{ name: 'TTFT', value: results.ttft_ms }, { name: 'End-to-end', value: results.avg_latency_ms }] : []
  const chartColor = APPROACH_COLORS[approach] || 'var(--indigo)'

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', background: 'var(--bg)' }}>

      {/* Header */}
      <div style={{ padding: '22px 32px', borderBottom: '1px solid var(--border)', background: 'linear-gradient(135deg, #fff 60%, var(--indigo-lt) 100%)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexShrink: 0 }}>
        <div>
          <h1 className="font-display font-bold text-xl" style={{ fontSize: 24, margin: 0, lineHeight: 1 }}>
            {t('benchmark.title', lang)}
            </h1>
          <p style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 11, color: 'var(--text-3)', margin: '5px 0 0' }}>
             {t('benchmark.approach', lang)} <strong style={{ color: 'var(--indigo)' }}>{approach}</strong> · {dataset.length} {t('benchmark.pairs', lang)} · {APPROACH_CONFIG[approach]?.model}
          </p>
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <label className="btn-ghost" style={{ cursor: 'pointer' }}>
            <Upload size={14} /> Dataset JSON
            <input type="file" accept=".json" onChange={handleImport} style={{ display: 'none' }} />
          </label>
          <button onClick={handleRun} disabled={loading} className="btn-primary">
            <Play size={14} /> {loading ? t('benchmark.running', lang) : t('benchmark.run', lang)}
          </button>
        </div>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: '28px 32px', display: 'flex', flexDirection: 'column', gap: 28 }}>
        {error && (
          <div style={{ background: 'var(--coral-lt)', border: '1px solid #F5BABA', borderRadius: 8, padding: '10px 16px', color: 'var(--coral)', fontSize: 13, display: 'flex', alignItems: 'center', gap: 8 }}>
            <XCircle size={14} /> {error}
          </div>
        )}

        {!results && !loading && (
          <div className="card" style={{ padding: '64px 0', textAlign: 'center' }}>
            <div style={{ width: 52, height: 52, borderRadius: 16, background: 'var(--indigo-lt)', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 16px' }}>
              <TrendingUp size={24} color="var(--indigo)" />
            </div>
            <p style={{ fontSize: 16, fontWeight: 600, color: 'var(--text)', margin: 0 }}>{t('benchmark.ready_title', lang)}</p>
            <p style={{ fontSize: 13, color: 'var(--text-3)', margin: '6px 0 0' }}>
              {dataset.length} {t('benchmark.ready_sub', lang)} {approach} 
            </p>
          </div>
        )}

        {loading && (
          <div className="card" style={{ padding: '64px 0', textAlign: 'center' }}>
            <div style={{ display: 'flex', justifyContent: 'center', gap: 6, marginBottom: 14 }}>
              <span className="typing-dot" /><span className="typing-dot" /><span className="typing-dot" />
            </div>
            <p style={{ fontSize: 14, color: 'var(--text-2)', margin: 0 }}>
              {t('benchmark.computing', lang)}
            </p>
          </div>
        )}

        {results && (
          <>
            {/* Quality KPIs */}
            <div>
              <SectionLabel>{t('benchmark.section_quality', lang)}</SectionLabel>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 14 }}>
                <KpiCard label={t('benchmark.metric_bleu', lang)} value={results.bleu} unit="%" icon={TrendingUp} color="var(--teal)" good={0.5} warn={0.3} />
                <KpiCard label={t('benchmark.metric_rouge', lang)} value={results.rouge_l} unit="%" icon={TrendingUp} color="var(--indigo)" good={0.5} warn={0.3} />
                <KpiCard label={t('benchmark.metric_relevance', lang)} value={results.contextual_relevance_rate} unit="%" icon={ShieldCheck} color="var(--amber)" good={0.8} warn={0.5} />
                <KpiCard label={t('benchmark.metric_lang', lang)} value={results.lang_accuracy} unit="%" icon={ShieldCheck} color="var(--teal)" good={0.9} warn={0.7} />
              </div>
            </div>

            {/* Performance KPIs */}
            <div>
              <SectionLabel>{t('benchmark.section_perf', lang)}</SectionLabel>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 14 }}>
                <KpiCard label={t('benchmark.metric_ttft', lang)} value={results.ttft_ms} unit="ms" icon={Clock} color="var(--indigo)" good={1000} warn={3000} />
                <KpiCard label={t('benchmark.metric_latency', lang)} value={results.avg_latency_ms} unit="ms" icon={Clock} color="var(--amber)" good={2000} warn={5000} />
                <KpiCard label={t('benchmark.metric_throughput', lang)} value={results.throughput_tokens_per_sec} unit="tok/s" icon={Zap} color="var(--teal)" good={20} warn={10} />
                <KpiCard label={t('benchmark.metric_hallucination', lang)} value={results.hallucination_rate} unit="%" icon={ShieldCheck} color="var(--coral)" good={0.05} warn={0.15} />
              </div>
            </div>

            {/* Charts */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 18 }}>
              <div className="card" style={{ padding: '20px 24px' }}>
                <SectionLabel>{t('benchmark.section_radar', lang)}</SectionLabel>
                <ResponsiveContainer width="100%" height={220}>
                  <RadarChart data={radarData}>
                    <PolarGrid stroke="var(--border)" />
                    <PolarAngleAxis dataKey="metric" tick={{ fill: 'var(--text-3)', fontSize: 11, fontFamily: 'JetBrains Mono, monospace' }} />
                    <Radar dataKey="value" stroke={chartColor} fill={chartColor} fillOpacity={0.15} strokeWidth={2} dot={{ r: 3, fill: chartColor }} />
                  </RadarChart>
                </ResponsiveContainer>
              </div>
              <div className="card" style={{ padding: '20px 24px' }}>
                <SectionLabel>{t('benchmark.section_latency', lang)}</SectionLabel>
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={latencyData} barSize={48}>
                    <XAxis dataKey="name" tick={{ fill: 'var(--text-3)', fontSize: 12, fontFamily: 'Plus Jakarta Sans, sans-serif' }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fill: 'var(--text-3)', fontSize: 11, fontFamily: 'JetBrains Mono, monospace' }} axisLine={false} tickLine={false} />
                    <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(61,82,160,0.04)' }} />
                    <Bar dataKey="value" radius={[8, 8, 0, 0]}>
                      {latencyData.map((_, i) => <Cell key={i} fill={chartColor} />)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Reliability */}
            {metrics && (
              <div>
                <SectionLabel>{t('benchmark.section_reliability', lang)}</SectionLabel>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 14 }}>
                  <KpiCard label={t('benchmark.metric_uptime', lang)} value={metrics.uptime_percent/100} unit="%" icon={ShieldCheck} color="var(--teal)" good={99} warn={95} />
                  <KpiCard label={t('benchmark.metric_ratelimit', lang)} value={metrics.rate_limit_hits} unit="" icon={Zap} color="var(--amber)" good={0} warn={5} />
                  <KpiCard label={t('benchmark.metric_coldstart', lang)} value={metrics.cold_start_ms} unit="ms" icon={Clock} color="var(--indigo)" good={5000} warn={30000} />
                  <KpiCard label={t('benchmark.metric_concurrency', lang)} value={metrics.concurrent_requests_handled} unit="" icon={TrendingUp} color="var(--teal)" good={5} warn={2} />
                  <KpiCard label={t('benchmark.metric_cost', lang)} value={metrics.cost_eur} unit="€" icon={Zap} color="var(--amber)" good={0} warn={0} />
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}