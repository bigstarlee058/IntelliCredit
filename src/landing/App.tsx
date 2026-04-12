'use client'

import { useEffect, useRef } from "react"
import { Card } from "@/components/ui/card"
import { Spotlight } from "@/components/ui/spotlight"
import { GlowingEffect } from "@/components/ui/glowing-effect"
import { FileText, Search, Sparkles } from "lucide-react"

/* ── Animated Credit Score Gauge ── */
function CreditScoreGauge() {
  const gaugeRef = useRef<SVGCircleElement>(null)
  const scoreRef = useRef<HTMLSpanElement>(null)

  useEffect(() => {
    const score = 78
    const maxDash = 565 // circumference for r=90
    const targetDash = maxDash * (score / 100)

    // Animate the gauge arc
    let start: number | null = null
    const duration = 2000
    const animate = (ts: number) => {
      if (!start) start = ts
      const progress = Math.min((ts - start) / duration, 1)
      const eased = 1 - Math.pow(1 - progress, 3) // ease-out cubic
      const current = targetDash * eased

      if (gaugeRef.current) {
        gaugeRef.current.style.strokeDashoffset = String(maxDash - current)
      }
      if (scoreRef.current) {
        scoreRef.current.textContent = String(Math.round(score * eased))
      }
      if (progress < 1) requestAnimationFrame(animate)
    }
    const timer = setTimeout(() => requestAnimationFrame(animate), 600)
    return () => clearTimeout(timer)
  }, [])

  return (
    <div className="relative flex items-center justify-center" style={{ width: 260, height: 260 }}>
      {/* Glow behind gauge */}
      <div className="absolute inset-0 rounded-full" style={{
        background: 'radial-gradient(circle, rgba(16,185,129,0.12) 0%, transparent 70%)',
        filter: 'blur(30px)',
      }} />

      <svg width="260" height="260" viewBox="0 0 200 200" className="transform -rotate-90">
        {/* Track */}
        <circle cx="100" cy="100" r="90" fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="8" />
        {/* Gauge arc */}
        <circle
          ref={gaugeRef}
          cx="100" cy="100" r="90"
          fill="none"
          stroke="url(#gaugeGrad)"
          strokeWidth="8"
          strokeLinecap="round"
          strokeDasharray="565"
          strokeDashoffset="565"
        />
        {/* Tick marks */}
        {Array.from({ length: 40 }).map((_, i) => {
          const angle = (i / 40) * 360
          const rad = (angle * Math.PI) / 180
          const r1 = 78, r2 = 82
          return (
            <line
              key={i}
              x1={100 + r1 * Math.cos(rad)} y1={100 + r1 * Math.sin(rad)}
              x2={100 + r2 * Math.cos(rad)} y2={100 + r2 * Math.sin(rad)}
              stroke="rgba(255,255,255,0.08)" strokeWidth="1"
            />
          )
        })}
        <defs>
          <linearGradient id="gaugeGrad" x1="0" y1="0" x2="200" y2="200">
            <stop offset="0%" stopColor="#10b981" />
            <stop offset="50%" stopColor="#06b6d4" />
            <stop offset="100%" stopColor="#8b5cf6" />
          </linearGradient>
        </defs>
      </svg>

      {/* Center text */}
      <div className="absolute flex flex-col items-center">
        <span ref={scoreRef} className="text-5xl font-bold text-white" style={{ fontFamily: 'JetBrains Mono, monospace' }}>0</span>
        <span className="text-xs text-neutral-500 uppercase tracking-widest mt-1">Credit Score</span>
        <span className="text-xs font-semibold text-emerald-400 mt-1">● APPROVED</span>
      </div>
    </div>
  )
}

/* ── Floating stat card ── */
function FloatingStat({ label, value, icon, delay, position }: {
  label: string; value: string; icon: string; delay: string;
  position: { top?: string; bottom?: string; left?: string; right?: string }
}) {
  return (
    <div
      className="absolute px-4 py-3 rounded-xl border border-neutral-800 bg-neutral-950/90 backdrop-blur-sm"
      style={{
        ...position,
        animation: `floatCard 6s ease-in-out ${delay} infinite`,
        opacity: 0,
        animationFillMode: 'forwards',
      }}
    >
      <div className="flex items-center gap-2.5">
        <span className="text-lg">{icon}</span>
        <div>
          <p className="text-[10px] text-neutral-500 uppercase tracking-wider">{label}</p>
          <p className="text-sm font-semibold text-neutral-200" style={{ fontFamily: 'JetBrains Mono, monospace' }}>{value}</p>
        </div>
      </div>
    </div>
  )
}

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-black flex flex-col">
      {/* Inject float animation keyframes */}
      <style>{`
        @keyframes floatCard {
          0% { opacity: 0; transform: translateY(20px); }
          10% { opacity: 1; transform: translateY(0); }
          50% { transform: translateY(-8px); }
          90% { opacity: 1; transform: translateY(0); }
          100% { opacity: 1; transform: translateY(0); }
        }
        @keyframes pulseRing {
          0%, 100% { transform: scale(1); opacity: 0.15; }
          50% { transform: scale(1.08); opacity: 0.08; }
        }
      `}</style>

      {/* Hero Section */}
      <Card className="w-full h-[100vh] bg-black/[0.96] relative overflow-hidden rounded-none border-0">
        <Spotlight
          className="-top-40 left-0 md:left-60 md:-top-20"
          fill="white"
        />

        <div className="flex h-full">
          {/* Left content */}
          <div className="flex-1 p-8 md:p-16 relative z-10 flex flex-col justify-center">
            {/* Badge */}
            <div className="inline-flex items-center gap-2 px-4 py-1.5 mb-8 rounded-full border border-neutral-700 bg-neutral-900/50 w-fit">
              <span className="w-2 h-2 bg-emerald-400 rounded-full animate-pulse"></span>
              <span className="text-xs text-neutral-400 font-medium tracking-wider uppercase">
                AI-Powered Credit Engine
              </span>
            </div>

            <h1 className="text-5xl md:text-7xl font-bold bg-clip-text text-transparent bg-gradient-to-b from-neutral-50 to-neutral-400 leading-tight">
              Intelli-Credit
            </h1>
            <p className="mt-2 text-xl md:text-2xl text-neutral-500 font-light">
              Credit Decisioning, Reimagined.
            </p>
            <p className="mt-6 text-neutral-400 max-w-lg leading-relaxed">
              Automate credit appraisal with AI-driven document ingestion, 
              web-scale research, and ML-powered Five Cs scoring generating 
              comprehensive Credit Appraisal Memos in seconds, not days.
            </p>

            {/* Feature pills */}
            <div className="flex flex-wrap gap-3 mt-8">
              {[
                "Document Parsing",
                "GST Cross-Verification",
                "NLP Sentiment",
                "ML Risk Scoring",
                "SHAP Explainability",
                "CAM Generation",
              ].map((feature) => (
                <span
                  key={feature}
                  className="px-3 py-1 text-xs font-medium text-neutral-300 bg-neutral-800/60 border border-neutral-700/50 rounded-full"
                >
                  {feature}
                </span>
              ))}
            </div>

            {/* CTA Buttons */}
            <div className="flex gap-4 mt-10">
              <a
                href="/dashboard"
                className="group relative inline-flex items-center gap-2 px-8 py-3.5 bg-gradient-to-r from-emerald-500 to-cyan-500 text-black font-semibold rounded-lg text-sm shadow-lg shadow-emerald-500/25 hover:shadow-emerald-500/40 transition-all duration-300 hover:-translate-y-0.5"
              >
                Launch Dashboard
                <svg className="w-4 h-4 transition-transform group-hover:translate-x-1" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6" />
                </svg>
              </a>
              <a
                href="/dashboard"
                className="inline-flex items-center gap-2 px-8 py-3.5 border border-neutral-700 text-neutral-300 font-medium rounded-lg text-sm hover:bg-neutral-800/50 hover:border-neutral-600 transition-all duration-300"
              >
                Try Demo
              </a>
            </div>

            {/* Author branding */}
            <div className="mt-12 pt-6 border-t border-neutral-800/50">
              <p className="text-xs text-neutral-600">
                Developed by{" "}
                <span className="text-neutral-500">Team SPB</span>
              </p>
            </div>
          </div>

          {/* Right content | Animated Credit Visual */}
          <div className="flex-1 relative hidden md:flex items-center justify-center">
            {/* Pulsing rings behind gauge */}
            <div className="absolute w-[340px] h-[340px] rounded-full border border-emerald-500/10"
              style={{ animation: 'pulseRing 4s ease-in-out infinite' }} />
            <div className="absolute w-[420px] h-[420px] rounded-full border border-cyan-500/5"
              style={{ animation: 'pulseRing 4s ease-in-out 1s infinite' }} />

            {/* Credit Score Gauge */}
            <CreditScoreGauge />

            {/* Floating finance stat cards */}
            <FloatingStat label="Revenue" value="₹485 Cr" icon="📊" delay="0.8s"
              position={{ top: '14%', right: '8%' }} />
            <FloatingStat label="Debt/Equity" value="0.42x" icon="⚖️" delay="1.2s"
              position={{ top: '30%', left: '4%' }} />
            <FloatingStat label="DSCR" value="2.1x" icon="🛡️" delay="1.6s"
              position={{ bottom: '28%', right: '6%' }} />
            <FloatingStat label="NLP Sentiment" value="+0.73" icon="🧠" delay="2.0s"
              position={{ bottom: '14%', left: '8%' }} />
            <FloatingStat label="Five Cs" value="82/100" icon="⭐" delay="2.4s"
              position={{ top: '58%', right: '22%' }} />
          </div>
        </div>
      </Card>

      {/* Three Pillars Section */}
      <div className="bg-black px-8 md:px-16 py-20">
        <h2 className="text-3xl md:text-4xl font-bold text-center bg-clip-text text-transparent bg-gradient-to-b from-neutral-50 to-neutral-400 mb-4">
          Three Pillars of Intelligence
        </h2>
        <p className="text-center text-neutral-500 mb-16 max-w-2xl mx-auto">
          A comprehensive AI engine built on three foundational pillars that work in harmony
        </p>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-6xl mx-auto">
          {/* Pillar 1 */}
          <li className="min-h-[14rem] list-none">
            <div className="relative h-full rounded-[1.25rem] border-[0.75px] border-neutral-800 p-2 md:rounded-[1.5rem] md:p-3">
              <GlowingEffect
                spread={40}
                glow={true}
                disabled={false}
                proximity={64}
                inactiveZone={0.01}
                borderWidth={3}
              />
              <div className="relative flex h-full flex-col justify-between gap-6 overflow-hidden rounded-xl border-[0.75px] border-neutral-800 bg-neutral-950 p-6 shadow-sm">
                <div className="relative flex flex-1 flex-col justify-between gap-3">
                  <div className="w-fit rounded-lg border-[0.75px] border-neutral-700 bg-neutral-900 p-2">
                    <FileText className="h-4 w-4 text-emerald-400" />
                  </div>
                  <div className="space-y-3">
                    <h3 className="pt-0.5 text-xl leading-[1.375rem] font-semibold tracking-[-0.04em] md:text-2xl md:leading-[1.875rem] text-neutral-100">
                      Data Ingestor
                    </h3>
                    <p className="text-sm leading-[1.125rem] md:text-base md:leading-[1.375rem] text-neutral-400">
                      Parse multi-format financial documents: PDFs, Excel, CSV. Cross-verify GST filings against bank statements.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </li>

          {/* Pillar 2 */}
          <li className="min-h-[14rem] list-none">
            <div className="relative h-full rounded-[1.25rem] border-[0.75px] border-neutral-800 p-2 md:rounded-[1.5rem] md:p-3">
              <GlowingEffect
                spread={40}
                glow={true}
                disabled={false}
                proximity={64}
                inactiveZone={0.01}
                borderWidth={3}
              />
              <div className="relative flex h-full flex-col justify-between gap-6 overflow-hidden rounded-xl border-[0.75px] border-neutral-800 bg-neutral-950 p-6 shadow-sm">
                <div className="relative flex flex-1 flex-col justify-between gap-3">
                  <div className="w-fit rounded-lg border-[0.75px] border-neutral-700 bg-neutral-900 p-2">
                    <Search className="h-4 w-4 text-cyan-400" />
                  </div>
                  <div className="space-y-3">
                    <h3 className="pt-0.5 text-xl leading-[1.375rem] font-semibold tracking-[-0.04em] md:text-2xl md:leading-[1.875rem] text-neutral-100">
                      Research Agent
                    </h3>
                    <p className="text-sm leading-[1.125rem] md:text-base md:leading-[1.375rem] text-neutral-400">
                      Automated web-scale intelligence: news sentiment, MCA filings, legal disputes, and NLP risk analysis.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </li>

          {/* Pillar 3 */}
          <li className="min-h-[14rem] list-none">
            <div className="relative h-full rounded-[1.25rem] border-[0.75px] border-neutral-800 p-2 md:rounded-[1.5rem] md:p-3">
              <GlowingEffect
                spread={40}
                glow={true}
                disabled={false}
                proximity={64}
                inactiveZone={0.01}
                borderWidth={3}
              />
              <div className="relative flex h-full flex-col justify-between gap-6 overflow-hidden rounded-xl border-[0.75px] border-neutral-800 bg-neutral-950 p-6 shadow-sm">
                <div className="relative flex flex-1 flex-col justify-between gap-3">
                  <div className="w-fit rounded-lg border-[0.75px] border-neutral-700 bg-neutral-900 p-2">
                    <Sparkles className="h-4 w-4 text-violet-400" />
                  </div>
                  <div className="space-y-3">
                    <h3 className="pt-0.5 text-xl leading-[1.375rem] font-semibold tracking-[-0.04em] md:text-2xl md:leading-[1.875rem] text-neutral-100">
                      Recommendation Engine
                    </h3>
                    <p className="text-sm leading-[1.125rem] md:text-base md:leading-[1.375rem] text-neutral-400">
                      Five Cs scoring with XGBoost ML prediction, SHAP explainability, and automated CAM generation.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </li>
        </div>
      </div>

      {/* Footer */}
      <footer className="bg-black border-t border-neutral-900 px-8 py-6 text-center">
        <p className="text-xs text-neutral-600">
          Intelli-Credit AI Engine | Developed by Team SPB
        </p>
      </footer>
    </div>
  )
}
