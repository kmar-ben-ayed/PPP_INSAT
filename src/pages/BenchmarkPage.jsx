import { useState } from 'react'
import { Play, Upload, CheckCircle, XCircle, AlertTriangle } from 'lucide-react'
import { runBenchmark, getMetrics } from '../lib/api'
import { RadarChart, Radar, PolarGrid, PolarAngleAxis, ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, Cell } from 'recharts'
import { APPROACH_CONFIG } from '../lib/context'

const DEFAULT_DATASET = [
  { question: "Quelles sont les dates limites d'inscription ?", 
    reference_answer: "Les inscriptions sont ouvertes jusqu'au 15 mai 2025.", 
    category: "inscription" 
  },
  { question: "Où se déroule l'événement ?", 
    reference_answer: "L'événement se déroule à l'INSAT, Tunis.", 
    category: "logistique" 
  },
]

const METRIC_LABELS = {
  bleu: 'BLEU',
  rouge_l: 'ROUGE-L',
  contextual_relevance_rate: 'Pertinence',
  lang_accuracy: 'Langue',
  consistency_rate: 'Cohérence',
}

const COLORS = { A: '#2DD4BF', B: '#E8F03C', C: '#FF6B5B' }

export default function BenchmarkPage({ approach }) {
  const [results, setResults] = useState(null)
  const [metrics, setMetrics] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [dataset, setDataset] = useState(DEFAULT_DATASET)

  async function handleRun() {
    setLoading(true)
    setError('')
    try {
      const [bench, met] = await Promise.all([
        runBenchmark({ approach, dataset }),
        getMetrics(approach),
      ])
      setResults(bench)
      setMetrics(met)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  async function handleImport(e) {
    const file = e.target.files?.[0]
    if (!file) return
    const text = await file.text()
    try { setDataset(JSON.parse(text)) } catch { setError('JSON invalide') }
    e.target.value = ''
  }

  const radarData = results
    ? Object.entries(METRIC_LABELS).map(([k, name]) => ({
        metric: name,
        value: +(results[k] * 100).toFixed(1),
      }))
    : []

  const latencyData = results
    ? [
        { name: 'TTFT', value: results.ttft_ms },
        { name: 'End-to-end', value: results.avg_latency_ms },
      ]
    : []

  function MetricCard({ label, value, unit = '', good, warn }) {
    const pct = typeof value === 'number' ? value : 0
    const color = pct >= good ? 'text-teal' : pct >= warn ? 'text-accent' : 'text-coral'
    return (
      <div className="card p-4">
        <p className="text-xs font-mono text-cream/30 mb-1">{label}</p>
        <p className={`font-display font-bold text-2xl ${color}`}>
          {typeof value === 'number' ? (unit === '%' ? (value * 100).toFixed(1) : value.toFixed(1)) : '—'}
          <span className="text-sm font-body ml-1">{unit}</span>
        </p>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-screen">
      <div className="px-8 py-5 border-b border-ink-muted flex items-center justify-between shrink-0">
        <div>
          <h1 className="font-display font-bold text-xl text-cream">Benchmark</h1>
          <p className="text-xs text-cream/40 font-mono mt-0.5">
            Approche {approach} · {dataset.length} paires Q/R
          </p>
        </div>
        <div className="flex items-center gap-2">
          <label className="btn-ghost flex items-center gap-1.5 cursor-pointer text-sm">
            <Upload size={14} />
            Dataset JSON
            <input type="file" accept=".json" onChange={handleImport} className="hidden" />
          </label>
          <button onClick={handleRun} disabled={loading} className="btn-primary flex items-center gap-2">
            <Play size={14} />
            {loading ? 'En cours…' : 'Lancer le benchmark'}
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-8 py-6 space-y-6">
        {error && (
          <div className="bg-coral/10 border border-coral/30 rounded-xl px-4 py-3 text-coral text-sm flex items-center gap-2">
            <XCircle size={16} /> {error}
          </div>
        )}

        {!results && !loading && (
          <div className="card p-10 text-center">
            <p className="text-cream/20 font-body text-sm mb-2">
              Lancez le benchmark pour voir les résultats comparatifs.
            </p>
            <p className="text-xs font-mono text-cream/10">
              Dataset actuel: {dataset.length} paires · Approche: {approach}
            </p>
          </div>
        )}

        {loading && (
          <div className="card p-10 text-center space-y-3">
            <div className="flex justify-center gap-2">
              <span className="typing-dot text-accent" />
              <span className="typing-dot text-accent" />
              <span className="typing-dot text-accent" />
            </div>
            <p className="text-cream/30 text-sm font-body">Évaluation BLEU/ROUGE en cours…</p>
          </div>
        )}

        {results && (
          <>
            {/* Quality metrics */}
            <div>
              <h2 className="font-display font-semibold text-sm text-cream/50 uppercase tracking-wider mb-3">
                Qualité des réponses
              </h2>
              <div className="grid grid-cols-4 gap-3">
                <MetricCard label="BLEU" value={results.bleu} unit="%" good={0.5} warn={0.3} />
                <MetricCard label="ROUGE-L" value={results.rouge_l} unit="%" good={0.5} warn={0.3} />
                <MetricCard label="Pertinence contextuelle" value={results.contextual_relevance_rate} unit="%" good={0.8} warn={0.5} />
                <MetricCard label="Précision langue" value={results.lang_accuracy} unit="%" good={0.9} warn={0.7} />
              </div>
            </div>

            {/* Performance */}
            <div>
              <h2 className="font-display font-semibold text-sm text-cream/50 uppercase tracking-wider mb-3">
                Performance
              </h2>
              <div className="grid grid-cols-4 gap-3">
                <MetricCard label="TTFT" value={results.ttft_ms} unit="ms" good={1000} warn={3000} />
                <MetricCard label="Latence moy." value={results.avg_latency_ms} unit="ms" good={2000} warn={5000} />
                <MetricCard label="Throughput" value={results.throughput_tokens_per_sec} unit="tok/s" good={20} warn={10} />
                <MetricCard label="Hallucination" value={results.hallucination_rate} unit="%" good={0.05} warn={0.15} />
              </div>
            </div>

            {/* Charts */}
            <div className="grid grid-cols-2 gap-4">
              <div className="card p-5">
                <h3 className="text-xs font-mono text-cream/40 mb-4">Radar qualité</h3>
                <ResponsiveContainer width="100%" height={220}>
                  <RadarChart data={radarData}>
                    <PolarGrid stroke="#252830" />
                    <PolarAngleAxis dataKey="metric" tick={{ fill: '#9CA3AF', fontSize: 11, fontFamily: 'JetBrains Mono' }} />
                    <Radar dataKey="value" stroke={COLORS[approach]} fill={COLORS[approach]} fillOpacity={0.2} />
                  </RadarChart>
                </ResponsiveContainer>
              </div>
              <div className="card p-5">
                <h3 className="text-xs font-mono text-cream/40 mb-4">Latence (ms)</h3>
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={latencyData} barSize={40}>
                    <XAxis dataKey="name" tick={{ fill: '#9CA3AF', fontSize: 11 }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fill: '#9CA3AF', fontSize: 11 }} axisLine={false} tickLine={false} />
                    <Tooltip contentStyle={{ background: '#1A1D24', border: '1px solid #252830', borderRadius: 8, fontFamily: 'JetBrains Mono', fontSize: 12 }} />
                    <Bar dataKey="value" radius={[6, 6, 0, 0]}>
                      {latencyData.map((_, i) => <Cell key={i} fill={COLORS[approach]} />)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Reliability */}
            {metrics && (
              <div>
                <h2 className="font-display font-semibold text-sm text-cream/50 uppercase tracking-wider mb-3">
                  Fiabilité système
                </h2>
                <div className="grid grid-cols-5 gap-3">
                  <MetricCard label="Uptime" value={metrics.uptime_percent} unit="%" good={99} warn={95} />
                  <MetricCard label="Rate limit hits" value={metrics.rate_limit_hits} unit="" good={0} warn={5} />
                  <MetricCard label="Cold start" value={metrics.cold_start_ms} unit="ms" good={5000} warn={30000} />
                  <MetricCard label="Concurrence" value={metrics.concurrent_requests_handled} unit="" good={5} warn={2} />
                  <MetricCard label="Coût total" value={metrics.cost_eur} unit="€" good={0} warn={0} />
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
