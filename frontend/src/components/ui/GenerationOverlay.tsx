import { useEffect, useState } from "react"
import { motion, AnimatePresence } from "framer-motion"

type Props = {
  open: boolean
  patientName: string
  label?: string
  doneLabel?: string
  onComplete: () => void
  steps?: { pct: number; msg: string }[]
}

const GENERATE_STEPS = [
  { pct: 15, msg: "Preparando datos del paciente..." },
  { pct: 30, msg: "Calculando objetivos nutricionales..." },
  { pct: 45, msg: "Analizando perfil clínico..." },
  { pct: 65, msg: "Generando plan de comidas..." },
  { pct: 80, msg: "Aplicando recomendaciones..." },
  { pct: 92, msg: "Finalizando..." },
]

export default function GenerationOverlay({ open, patientName, label, doneLabel, onComplete, steps }: Props) {
  const [stepIndex, setStepIndex] = useState(0)
  const [done, setDone] = useState(false)

  const STEP_LIST = steps || GENERATE_STEPS

  useEffect(() => {
    if (!open) {
      setStepIndex(0)
      setDone(false)
      return
    }

    const interval = setInterval(() => {
      setStepIndex((prev) => {
        if (prev >= STEP_LIST.length - 1) {
          clearInterval(interval)
          setDone(true)
          setTimeout(onComplete, 1200)
          return prev
        }
        return prev + 1
      })
    }, 2500)

    return () => clearInterval(interval)
  }, [open, onComplete, STEP_LIST])

  const current = STEP_LIST[Math.min(stepIndex, STEP_LIST.length - 1)]

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.25 }}
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm"
        >
          <motion.div
            initial={{ opacity: 0, y: 24, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 16, scale: 0.95 }}
            transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
            className="bg-white rounded-2xl p-8 shadow-xl max-w-sm w-full mx-4 text-center"
          >
            {done ? (
              <>
                <div className="mx-auto mb-4 text-emerald-500">
                  <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
                </div>
                <h3 className="text-lg font-semibold text-slate-800">{doneLabel || "¡Listo!"}</h3>
                <p className="text-sm text-slate-500 mt-1">Redirigiendo al detalle...</p>
              </>
            ) : (
              <>
                <h3 className="text-lg font-semibold text-slate-800 mb-1">
                  {label || "Generando dieta"}
                </h3>
                {patientName && (
                  <p className="text-sm text-slate-500 mb-6 truncate">
                    para {patientName}
                  </p>
                )}

                {/* Progress bar */}
                <div className="h-2 bg-slate-100 rounded-full overflow-hidden mb-4">
                  <motion.div
                    className="h-full bg-emerald-500 rounded-full"
                    initial={{ width: 0 }}
                    animate={{ width: `${current.pct}%` }}
                    transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
                  />
                </div>

                {/* Percentage + message */}
                <div className="flex items-center justify-between text-sm">
                  <span className="text-slate-600 font-medium">{current.msg}</span>
                  <span className="text-slate-400 font-mono tabular-nums">{current.pct}%</span>
                </div>
              </>
            )}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
