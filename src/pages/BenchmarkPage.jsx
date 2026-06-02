import { useState, useEffect } from 'react'
import { Play, Upload, XCircle, TrendingUp, Clock, Zap, ShieldCheck } from 'lucide-react'
import { runBenchmark, getMetrics, getLatestBenchmark } from '../lib/api'
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis, ResponsiveContainer,
  BarChart, Bar, XAxis, YAxis, Tooltip, Cell, ComposedChart, Line,
  Area, CartesianGrid, Legend, ReferenceLine,
} from 'recharts'
import { APPROACH_CONFIG } from '../lib/context'
import faqData from '../data/faq.json'
import { t } from '../lib/i18n'

// ─── Dataset ──────────────────────────────────────────────────────────────────
const DEFAULT_DATASET = faqData
  .sort(() => Math.random() - 0.5)
  .slice(0, 10)
  .map(e => ({ question: e.q, reference_answer: e.a, category: e.category || 'general' }))

const METRIC_LABELS = {
  bleu: 'BLEU',
  rouge_l: 'ROUGE-L',
  contextual_relevance_rate: 'Pertinence',
  lang_accuracy: 'Langue',
  consistency_rate: 'Cohérence',
}

const APPROACH_COLORS = { A: '#2A9D8F', B: '#3D52A0', C: '#E8925A' }

// ─── Tab definitions ──────────────────────────────────────────────────────────
const TABS = [
  { id: 'overview',    label: 'Overview',    icon: TrendingUp },
  { id: 'quality',     label: 'Quality',     icon: ShieldCheck },
  { id: 'performance', label: 'Performance', icon: Zap },
  { id: 'reliability', label: 'Reliability', icon: Clock },
]

// ─── Shared small components ──────────────────────────────────────────────────
function KpiCard({ label, value, unit = '', icon: Icon, color = 'var(--indigo)', good, warn }) {
  const num = typeof value === 'number' ? value : null
  const display =
    num === null ? '—'
    : unit === '%' ? (num * 100).toFixed(1)
    : Number.isInteger(num) ? num
    : num.toFixed(1)
  const statusColor =
    num === null ? 'var(--text-3)'
    : num >= good ? 'var(--teal)'
    : num >= warn ? 'var(--amber)'
    : 'var(--coral)'

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
      {payload.map((p, i) => (
        <p key={i} style={{ fontFamily: 'Playfair Display, serif', fontSize: 16, color: p.color || 'var(--text)', margin: '2px 0 0', fontWeight: 700 }}>
          {p.name}: {typeof p.value === 'number' ? p.value.toFixed(3) : p.value}
        </p>
      ))}
    </div>
  )
}



// ─── Score heatmap ────────────────────────────────────────────────────────────
function ScoreHeatmap({ data, chartColor }) {
  if (!data.length) return null
  const metrics      = ['bleu', 'rouge_l', 'f1']
  const metricLabels = { bleu: 'BLEU', rouge_l: 'ROUGE-L', f1: 'F1' }

  // bigger cells so text is readable
  const cellW = 64, cellH = 58, labelW = 80, headerH = 40
  const totalW = labelW + data.length * cellW
  const totalH = headerH + metrics.length * cellH

  const maxByMetric = {}
  metrics.forEach(m => { maxByMetric[m] = Math.max(...data.map(d => d[m] || 0), 0.001) })
  const alpha = (val, max) => 0.10 + (val / max) * 0.80
  const hex   = (a) => `${chartColor}${Math.round(a * 255).toString(16).padStart(2, '0')}`

  return (
    // scrollable wrapper — card stays at fixed width, table scrolls inside
    <div style={{ overflowX: 'auto', overflowY: 'visible', paddingBottom: 4 }}>
      <svg
        width={totalW}
        height={totalH}
        style={{ display: 'block', minWidth: totalW }}
      >
        {/* column headers */}
        {data.map((d, ci) => (
          <text
            key={ci}
            x={labelW + ci * cellW + cellW / 2}
            y={headerH - 10}
            textAnchor="middle"
            fontSize={10}
            fontFamily="JetBrains Mono, monospace"
            fill="var(--text-3)"
          >
            {d.name}
          </text>
        ))}

        {metrics.map((m, ri) => (
          <g key={m}>
            {/* row label */}
            <text
              x={labelW - 10}
              y={headerH + ri * cellH + cellH / 2 + 4}
              textAnchor="end"
              fontSize={11}
              fontFamily="JetBrains Mono, monospace"
              fill="var(--text-2)"
              fontWeight="600"
            >
              {metricLabels[m]}
            </text>

            {data.map((d, ci) => {
              const val = d[m] || 0
              const a   = alpha(val, maxByMetric[m])
              const textColor = a > 0.55 ? '#fff' : 'var(--text)'
              return (
                <g key={ci}>
                  <rect
                    x={labelW + ci * cellW + 3}
                    y={headerH + ri * cellH + 3}
                    width={cellW - 6}
                    height={cellH - 6}
                    rx={7}
                    fill={hex(a)}
                  />
                  {/* value */}
                  <text
                    x={labelW + ci * cellW + cellW / 2}
                    y={headerH + ri * cellH + cellH / 2 + 4}
                    textAnchor="middle"
                    fontSize={11}
                    fontWeight="700"
                    fontFamily="JetBrains Mono, monospace"
                    fill={textColor}
                  >
                    {val.toFixed(3)}
                  </text>
                </g>
              )
            })}
          </g>
        ))}
      </svg>
    </div>
  )
}

// ─── Consistency gauge ────────────────────────────────────────────────────────
function ConsistencyGauge({ value, color }) {
  const pct    = typeof value === 'number' ? value : 0
  const r = 70, cx = 90, cy = 88
  const toRad  = deg => (deg * Math.PI) / 180
  const arc    = (s, e, radius) => {
    const ps = { x: cx + radius * Math.cos(toRad(s - 90)), y: cy + radius * Math.sin(toRad(s - 90)) }
    const pe = { x: cx + radius * Math.cos(toRad(e - 90)), y: cy + radius * Math.sin(toRad(e - 90)) }
    return `M ${ps.x} ${ps.y} A ${radius} ${radius} 0 ${e - s > 180 ? 1 : 0} 1 ${pe.x} ${pe.y}`
  }
  const fillEnd   = -50 + pct * 280
  const needleRad = toRad(fillEnd - 90)
  const nx = cx + (r - 14) * Math.cos(needleRad)
  const ny = cy + (r - 14) * Math.sin(needleRad)

  return (
    <svg width="180" height="118" style={{ display: 'block', margin: '0 auto' }}>
      <path d={arc(-50, 230, r)} fill="none" stroke="var(--border)" strokeWidth={10} strokeLinecap="round" />
      <path d={arc(-50, fillEnd, r)} fill="none" stroke={color} strokeWidth={10} strokeLinecap="round" />
      <line x1={cx} y1={cy} x2={nx} y2={ny} stroke={color} strokeWidth={3} strokeLinecap="round" />
      <circle cx={cx} cy={cy} r={5} fill={color} />
      <text x={cx} y={cy + 24} textAnchor="middle" fontSize={17} fontWeight="700"
        fontFamily="Playfair Display, serif" fill="var(--text)">{(pct * 100).toFixed(1)}%</text>
    </svg>
  )
}

// ─── Tab bar ──────────────────────────────────────────────────────────────────
function TabBar({ active, onChange, hasResults }) {
  return (
    <div style={{ display: 'flex', gap: 2, borderBottom: '1px solid var(--border)', padding: '0 32px', background: '#fff', flexShrink: 0 }}>
      {TABS.map(({ id, label, icon: Icon }) => {
        const isActive = active === id
        const disabled = !hasResults && id !== 'overview'
        return (
          <button
            key={id}
            onClick={() => !disabled && onChange(id)}
            disabled={disabled}
            style={{
              display: 'flex', alignItems: 'center', gap: 6,
              padding: '12px 18px',
              border: 'none',
              borderBottom: isActive ? '2px solid var(--indigo)' : '2px solid transparent',
              background: 'none',
              cursor: disabled ? 'not-allowed' : 'pointer',
              fontFamily: 'JetBrains Mono, monospace', fontSize: 11.5,
              color: isActive ? 'var(--indigo)' : disabled ? 'var(--text-3)' : 'var(--text-2)',
              fontWeight: isActive ? 700 : 400,
              transition: 'color 0.15s, border-color 0.15s',
              marginBottom: -1,
              opacity: disabled ? 0.45 : 1,
            }}
          >
            <Icon size={13} />
            {label}
          </button>
        )
      })}
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════════════════════
// TAB PANELS
// ═══════════════════════════════════════════════════════════════════════════════

// ── Overview ──────────────────────────────────────────────────────────────────
function OverviewTab({ results, metrics, chartColor, radarData, lang }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      {/* top KPI strip — one number per pillar */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 14 }}>
        <KpiCard label="BLEU"          value={results.bleu}                       unit="%" icon={TrendingUp} color="var(--teal)"   good={0.5}  warn={0.3} />
        <KpiCard label="Avg Latency"   value={results.avg_latency_ms}             unit="ms" icon={Clock}    color="var(--indigo)" good={2000} warn={5000} />
        <KpiCard label="Throughput"    value={results.throughput_tokens_per_sec}  unit="tok/s" icon={Zap}  color="var(--teal)"   good={20}   warn={10} />
        <KpiCard label="Hallucination" value={results.hallucination_rate}         unit="%" icon={ShieldCheck} color="var(--coral)" good={0.05} warn={0.15} />
      </div>

      {/* radar + safety snapshot */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 18 }}>
        <div className="card" style={{ padding: '20px 24px' }}>
          <SectionLabel>Radar — scores normalisés</SectionLabel>
          <p style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 10, color: 'var(--text-3)', margin: '0 0 8px' }}>
            Average normalised scores across all questions
          </p>
          <ResponsiveContainer width="100%" height={230}>
            <RadarChart data={radarData}>
              <PolarGrid stroke="var(--border)" />
              <PolarAngleAxis dataKey="metric" tick={{ fill: 'var(--text-3)', fontSize: 11, fontFamily: 'JetBrains Mono, monospace' }} />
              <Radar dataKey="value" stroke={chartColor} fill={chartColor} fillOpacity={0.15} strokeWidth={2} dot={{ r: 3, fill: chartColor }} />
            </RadarChart>
          </ResponsiveContainer>
        </div>

        <div className="card" style={{ padding: '20px 24px' }}>
          <SectionLabel>Safety & Reliability Snapshot</SectionLabel>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginTop: 8 }}>
            {[
              { label: 'Hallucination rate',   val: results.hallucination_rate,        invert: true  },
              { label: 'Contextual relevance', val: results.contextual_relevance_rate, invert: false },
              { label: 'Language accuracy',    val: results.lang_accuracy,             invert: false },
              { label: 'Consistency',          val: results.consistency_rate ?? 0,     invert: false },
            ].map(({ label, val, invert }) => {
              const isGood   = invert ? val < 0.1 : val > 0.75
              const barColor = isGood ? 'var(--teal)' : val > 0.4 ? 'var(--amber)' : 'var(--coral)'
              const barWidth = invert ? (1 - val) * 100 : val * 100
              return (
                <div key={label}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                    <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 11, color: 'var(--text-2)' }}>{label}</span>
                    <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 11, color: barColor }}>{(val * 100).toFixed(1)}%</span>
                  </div>
                  <div style={{ height: 6, background: 'var(--border)', borderRadius: 4, overflow: 'hidden' }}>
                    <div style={{ height: '100%', width: `${barWidth}%`, background: barColor, borderRadius: 4, transition: 'width 0.6s ease' }} />
                  </div>
                </div>
              )
            })}
          </div>
          <div style={{ marginTop: 20, borderTop: '1px solid var(--border)', paddingTop: 16 }}>
            <p style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 10, color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 8, textAlign: 'center' }}>
              Consistency gauge
            </p>
            <ConsistencyGauge value={results.consistency_rate ?? 0} color={chartColor} />
          </div>
        </div>
      </div>
    </div>
  )
}

// ── Quality ───────────────────────────────────────────────────────────────────
function QualityTab({ results, perQ, chartColor, lang }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 14 }}>
        <KpiCard label={t('benchmark.metric_bleu', lang)}      value={results.bleu}                      unit="%" icon={TrendingUp} color="var(--teal)"   good={0.5} warn={0.3} />
        <KpiCard label={t('benchmark.metric_rouge', lang)}     value={results.rouge_l}                   unit="%" icon={TrendingUp} color="var(--indigo)" good={0.5} warn={0.3} />
        <KpiCard label={t('benchmark.metric_relevance', lang)} value={results.contextual_relevance_rate} unit="%" icon={ShieldCheck} color="var(--amber)" good={0.8} warn={0.5} />
        <KpiCard label={t('benchmark.metric_lang', lang)}      value={results.lang_accuracy}             unit="%" icon={ShieldCheck} color="var(--teal)"  good={0.9} warn={0.7} />
      </div>

      {perQ.length > 0 && (
        <div style={{ display: 'grid',  flexDirection: 'column', gap: 18 }}>
          <div className="card" style={{ padding: '20px 24px' }}>
            <SectionLabel>Quality Scores per Question</SectionLabel>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={perQ} barGap={2} barCategoryGap="25%">
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                <XAxis dataKey="name" tick={{ fill: 'var(--text-3)', fontSize: 11, fontFamily: 'JetBrains Mono, monospace' }} axisLine={false} tickLine={false} />
                <YAxis domain={[0, 'auto']} tick={{ fill: 'var(--text-3)', fontSize: 10, fontFamily: 'JetBrains Mono, monospace' }} axisLine={false} tickLine={false} />
                <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(61,82,160,0.03)' }} />
                <Legend wrapperStyle={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 11 }} />
                <Bar dataKey="bleu"    name="BLEU"       fill="#2A9D8F" radius={[4, 4, 0, 0]} />
                <Bar dataKey="rouge_l" name="ROUGE-L"    fill="#E8925A" radius={[4, 4, 0, 0]} />
                <Bar dataKey="f1"      name="F1 Overlap" fill="#E76F51" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="card" style={{ padding: '20px 24px' }}>
            <SectionLabel>Score Heatmap — Darker = higher score</SectionLabel>
            <div style={{ marginTop: 16, marginLeft: -8, marginRight: -8 }}>
              <ScoreHeatmap data={perQ} chartColor={chartColor} />
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Performance ───────────────────────────────────────────────────────────────
function PerformanceTab({ results, perQ, chartColor, lang }) {
  const latencyData = [
    { name: 'TTFT', value: results.ttft_ms },
    { name: 'End-to-end', value: results.avg_latency_ms },
  ]
  const latencyStackData = perQ.map(d => ({
    name:  d.name,
    ttft:  +(d.ttft_ms / 1000).toFixed(2),
    gen:   +((d.total_latency - d.ttft_ms) / 1000).toFixed(2),
    total: +(d.total_latency / 1000).toFixed(2),
  }))
  const throughputMax = perQ.length ? Math.max(...perQ.map(d => d.throughput)) : 0
  const throughputMin = perQ.length ? Math.min(...perQ.map(d => d.throughput)) : 0

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 14 }}>
        <KpiCard label={t('benchmark.metric_ttft', lang)}          value={results.ttft_ms}                   unit="ms"    icon={Clock}       color="var(--indigo)" good={1000} warn={3000} />
        <KpiCard label={t('benchmark.metric_latency', lang)}       value={results.avg_latency_ms}            unit="ms"    icon={Clock}       color="var(--amber)"  good={2000} warn={5000} />
        <KpiCard label={t('benchmark.metric_throughput', lang)}    value={results.throughput_tokens_per_sec} unit="tok/s" icon={Zap}         color="var(--teal)"   good={20}   warn={10} />
        <KpiCard label={t('benchmark.metric_hallucination', lang)} value={results.hallucination_rate}        unit="%"     icon={ShieldCheck} color="var(--coral)"  good={0.05} warn={0.15} />
      </div>

      {/* TTFT summary + Throughput */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: 18 }}>
        <div className="card" style={{ padding: '20px 24px' }}>
          <SectionLabel>Latency Summary</SectionLabel>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={latencyData} barSize={48}>
              <XAxis dataKey="name" tick={{ fill: 'var(--text-3)', fontSize: 11, fontFamily: 'JetBrains Mono, monospace' }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: 'var(--text-3)', fontSize: 10, fontFamily: 'JetBrains Mono, monospace' }} axisLine={false} tickLine={false} />
              <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(61,82,160,0.04)' }} />
              <Bar dataKey="value" name="ms" radius={[8, 8, 0, 0]}>
                {latencyData.map((_, i) => <Cell key={i} fill={chartColor} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        {perQ.length > 0 && (
          <div className="card" style={{ padding: '20px 24px' }}>
            <SectionLabel>Generation Throughput — tokens / second after first token</SectionLabel>
            <ResponsiveContainer width="100%" height={220}>
              <ComposedChart data={perQ}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                <XAxis dataKey="name" tick={{ fill: 'var(--text-3)', fontSize: 11, fontFamily: 'JetBrains Mono, monospace' }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: 'var(--text-3)', fontSize: 10, fontFamily: 'JetBrains Mono, monospace' }} axisLine={false} tickLine={false}
                  label={{ value: 'Tokens / second', angle: -90, position: 'insideLeft', fill: 'var(--text-3)', fontSize: 10 }} />
                <Tooltip content={<CustomTooltip />} />
                <ReferenceLine y={throughputMax} stroke="#2A9D8F" strokeDasharray="4 3"
                  label={{ value: `max ${throughputMax}`, position: 'right', fill: '#2A9D8F', fontSize: 10 }} />
                <ReferenceLine y={throughputMin} stroke="#E76F51" strokeDasharray="4 3"
                  label={{ value: `min ${throughputMin}`, position: 'right', fill: '#E76F51', fontSize: 10 }} />
                <Bar  dataKey="throughput" name="Throughput" fill={`${chartColor}33`} radius={[6, 6, 0, 0]} />
                <Line dataKey="throughput" name="Throughput" stroke={chartColor} strokeWidth={2.5}
                  dot={{ r: 5, fill: '#fff', stroke: chartColor, strokeWidth: 2 }} type="monotone" />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {/* Per-Q breakdown + Latency vs TTFT */}
      {perQ.length > 0 && (
        <div style={{ display: 'grid',gridTemplateColumns: '1fr 1fr', gap: 18 }}>
          <div className="card" style={{ padding: '20px 24px' }}>
            <SectionLabel>Latency Breakdown — TTFT + Generation Time</SectionLabel>
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={latencyStackData} barSize={48}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                <XAxis dataKey="name" tick={{ fill: 'var(--text-3)', fontSize: 11, fontFamily: 'JetBrains Mono, monospace' }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: 'var(--text-3)', fontSize: 10, fontFamily: 'JetBrains Mono, monospace' }} axisLine={false} tickLine={false}
                  label={{ value: 'Time (seconds)', angle: -90, position: 'insideLeft', fill: 'var(--text-3)', fontSize: 10 }} />
                <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(61,82,160,0.03)' }} />
                <Legend wrapperStyle={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 11 }} />
                <Bar dataKey="ttft" name="TTFT" stackId="a" fill="#7B6FD4" radius={[0, 0, 0, 0]}
                  label={{ position: 'top', formatter: (_, __, idx) => latencyStackData[idx] ? `${latencyStackData[idx].total}s` : '', fontSize: 11, fill: 'var(--text-2)', fontFamily: 'JetBrains Mono, monospace' }} />
                <Bar dataKey="gen" name="Generation Time" stackId="a" fill="#7EC8E3" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="card" style={{ padding: '20px 24px' }}>
            <SectionLabel>Latency vs TTFT — per question trend</SectionLabel>
            <ResponsiveContainer width="100%" height={240}>
              <ComposedChart data={latencyStackData}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                <XAxis dataKey="name" tick={{ fill: 'var(--text-3)', fontSize: 11, fontFamily: 'JetBrains Mono, monospace' }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: 'var(--text-3)', fontSize: 10, fontFamily: 'JetBrains Mono, monospace' }} axisLine={false} tickLine={false}
                  label={{ value: 'Time (seconds)', angle: -90, position: 'insideLeft', fill: 'var(--text-3)', fontSize: 10 }} />
                <Tooltip content={<CustomTooltip />} />
                <Legend wrapperStyle={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 11 }} />
                <Area  dataKey="gen"   name="Gen window"    fill="#7EC8E322" stroke="none" stackId="b" />
                <Line  dataKey="total" name="Total Latency" stroke={chartColor} strokeWidth={2.5} dot={{ r: 5, fill: chartColor }} type="monotone" />
                <Line  dataKey="ttft"  name="TTFT"          stroke="#9B8FE0" strokeWidth={2} strokeDasharray="6 3"
                  dot={{ r: 4, fill: '#fff', stroke: '#9B8FE0', strokeWidth: 2 }} type="monotone" />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Reliability ───────────────────────────────────────────────────────────────
function ReliabilityTab({ results, metrics, chartColor, lang }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      {metrics && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 14 }}>
          <KpiCard label={t('benchmark.metric_uptime', lang)}      value={metrics.uptime_percent / 100}        unit="%" icon={ShieldCheck} color="var(--teal)"   good={0.99} warn={0.95} />
          <KpiCard label={t('benchmark.metric_ratelimit', lang)}   value={metrics.rate_limit_hits}             unit=""  icon={Zap}         color="var(--amber)"  good={0}    warn={5} />
          <KpiCard label={t('benchmark.metric_coldstart', lang)}   value={metrics.cold_start_ms}              unit="ms" icon={Clock}       color="var(--indigo)" good={5000} warn={30000} />
          <KpiCard label={t('benchmark.metric_concurrency', lang)} value={metrics.concurrent_requests_handled} unit=""  icon={TrendingUp}  color="var(--teal)"   good={5}    warn={2} />
          <KpiCard label={t('benchmark.metric_cost', lang)}        value={metrics.cost_eur}                   unit="€" icon={Zap}         color="var(--amber)"  good={0}    warn={0} />
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 18 }}>
        <div className="card" style={{ padding: '24px', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
          <SectionLabel>Consistency Score</SectionLabel>
          <ConsistencyGauge value={results.consistency_rate ?? 0} color={chartColor} />
          <p style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 10.5, color: 'var(--text-3)', marginTop: 10, textAlign: 'center' }}>
            Token-overlap between two identical prompts
          </p>
        </div>

        <div className="card" style={{ padding: '20px 24px' }}>
          <SectionLabel>Reliability Snapshot</SectionLabel>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14, marginTop: 8 }}>
            {[
              { label: 'Consistency rate',     val: results.consistency_rate ?? 0,     invert: false },
              { label: 'Hallucination rate',   val: results.hallucination_rate,        invert: true  },
              { label: 'Language accuracy',    val: results.lang_accuracy,             invert: false },
              { label: 'Contextual relevance', val: results.contextual_relevance_rate, invert: false },
              ...(metrics ? [{ label: 'Uptime', val: metrics.uptime_percent / 100, invert: false }] : []),
            ].map(({ label, val, invert }) => {
              const isGood   = invert ? val < 0.1 : val > 0.75
              const barColor = isGood ? 'var(--teal)' : val > 0.4 ? 'var(--amber)' : 'var(--coral)'
              const barWidth = invert ? (1 - val) * 100 : val * 100
              return (
                <div key={label}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                    <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 11, color: 'var(--text-2)' }}>{label}</span>
                    <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 11, color: barColor }}>{(val * 100).toFixed(1)}%</span>
                  </div>
                  <div style={{ height: 6, background: 'var(--border)', borderRadius: 4, overflow: 'hidden' }}>
                    <div style={{ height: '100%', width: `${barWidth}%`, background: barColor, borderRadius: 4, transition: 'width 0.6s ease' }} />
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </div>
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════════════════════
// PAGE
// ═══════════════════════════════════════════════════════════════════════════════
export default function BenchmarkPage({ approach, lang }) {
  const [results,   setResults]   = useState(null)
  const [metrics,   setMetrics]   = useState(null)
  const [loading,   setLoading]   = useState(false)
  const [error,     setError]     = useState('')
  const [dataset,   setDataset]   = useState(DEFAULT_DATASET)
  const [perQ,      setPerQ]      = useState([])
  const [activeTab, setActiveTab] = useState('overview')

  useEffect(() => {
    let active = true
    async function loadLatest() {
      setLoading(true); setError(''); setResults(null); setMetrics(null); setPerQ([])
      try {
        const [latest, met] = await Promise.all([
          getLatestBenchmark(approach),
          getMetrics(approach).catch(() => null),
        ])
        if (active && latest) {
          setResults(latest)
          setMetrics(met)
          setPerQ(latest.per_question || [])
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
      setPerQ(bench.per_question || [])
      setActiveTab('overview')
    } catch (err) { setError(err.message) }
    finally { setLoading(false) }
  }

  async function handleImport(e) {
    const file = e.target.files?.[0]; if (!file) return
    try { setDataset(JSON.parse(await file.text())) } catch { setError('JSON invalide') }
    e.target.value = ''
  }

  const chartColor = APPROACH_COLORS[approach] || 'var(--indigo)'
  const radarData  = results
    ? Object.entries(METRIC_LABELS).map(([k, name]) => ({ metric: name, value: +(results[k] * 100).toFixed(1) }))
    : []

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', background: 'var(--bg)' }}>

      {/* Header */}
      <div style={{ padding: '22px 32px', borderBottom: '1px solid var(--border)', background: 'linear-gradient(135deg, #fff 60%, var(--indigo-lt) 100%)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexShrink: 0 }}>
        <div>
          <h1 className="font-display font-bold text-xl" style={{ fontSize: 24, margin: 0, lineHeight: 1 }}>
            {t('benchmark.title', lang)}
          </h1>
          <p style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 11, color: 'var(--text-3)', margin: '5px 0 0' }}>
            {t('benchmark.approach', lang)} <strong style={{ color: 'var(--indigo)' }}>{approach}</strong>
            {' · '}{dataset.length} {t('benchmark.pairs', lang)}
            {' · '}{APPROACH_CONFIG[approach]?.model}
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

      {/* Tab bar — always visible */}
      <TabBar active={activeTab} onChange={setActiveTab} hasResults={!!results} />

      {/* Body */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '28px 32px', display: 'flex', flexDirection: 'column', gap: 24 }}>

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
            <p style={{ fontSize: 14, color: 'var(--text-2)', margin: 0 }}>{t('benchmark.computing', lang)}</p>
          </div>
        )}

        {results && (
          <>
            {activeTab === 'overview'    && <OverviewTab    results={results} metrics={metrics} chartColor={chartColor} radarData={radarData} lang={lang} />}
            {activeTab === 'quality'     && <QualityTab     results={results} perQ={perQ}       chartColor={chartColor} lang={lang} />}
            {activeTab === 'performance' && <PerformanceTab results={results} perQ={perQ}       chartColor={chartColor} lang={lang} />}
            {activeTab === 'reliability' && <ReliabilityTab results={results} metrics={metrics} chartColor={chartColor} lang={lang} />}
          </>
        )}
      </div>
    </div>
  )
}