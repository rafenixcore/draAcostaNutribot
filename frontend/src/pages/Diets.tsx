import { FormEvent, useCallback, useEffect, useRef, useState } from "react"
import { Link, useNavigate, useSearchParams } from "react-router-dom"
import { BowlFood, MagnifyingGlass, Plus, Trash, X, Spinner } from "@phosphor-icons/react"
import GenerationOverlay from "../components/ui/GenerationOverlay"
import { generateDiet, getDiets, getPatients, getPlanDurationPresets, softDeleteDiet } from "../services/api"
import type { Diet, PaginatedDiets } from "../types"
import type { DietStrategyMode, MealsPerDay } from "../types"
import { DurationPresetButtons } from "../components/DurationPresetButtons"
import { Avatar } from "../components/ui/Avatar"
import { SkeletonRow } from "../components/ui/Skeleton"
import { EmptyState } from "../components/ui/EmptyState"
import { useToast } from "../context/ToastContext"
import { usePatientSearch } from "../hooks/usePatientSearch"
import {
  clampDurationDays,
  durationAdjustHint,
  FALLBACK_PLAN_DURATION_PRESETS,
} from "../utils/duration"
import { buildDietStrategyBody } from "../utils/dietStrategyBody"

const NEXT_FEATURES = { batchDiets: false, advancedStrategies: false }

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString("es-VE", {
    day: "numeric",
    month: "short",
    year: "numeric",
  })
}

export default function Diets() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const patientFromUrl = searchParams.get("patient")

  /* ---------- data state ---------- */
  const [data, setData] = useState<PaginatedDiets | null>(null)
  const [page, setPage] = useState(1)
  const [error, setError] = useState<string | null>(null)

  /* ---------- patient filter ---------- */
  const [patientIdFilter, setPatientIdFilter] = useState<number | undefined>(
    patientFromUrl ? Number(patientFromUrl) : undefined,
  )
  const [selectedPatientName, setSelectedPatientName] = useState<string | null>(null)
  const [filterOpen, setFilterOpen] = useState(false)
  const [allPatients, setAllPatients] = useState<{ id: number; first_name: string; last_name: string; city?: string | null }[]>([])
  const filterRef = useRef<HTMLDivElement>(null)

  // Load all patients when dropdown opens
  useEffect(() => {
    if (filterOpen && allPatients.length === 0) {
      getPatients({ page: 1, page_size: 100 }).then(res => {
        setAllPatients(res.items.map(p => ({ id: p.id, first_name: p.first_name, last_name: p.last_name, city: p.city })))
      }).catch(() => {})
    }
  }, [filterOpen, allPatients.length])

  /* ---------- patient name map (table display) ---------- */
  const [patientNameMap, setPatientNameMap] = useState<
    Record<number, { firstName: string; lastName: string; city?: string | null }>
  >({})
  const [patientsCount, setPatientsCount] = useState(0)

  /* ---------- form state ---------- */
  const [formOpen, setFormOpen] = useState(false)
  const [genPatientId, setGenPatientId] = useState<number | null>(
    patientFromUrl ? Number(patientFromUrl) : null,
  )
  const [genInstr, setGenInstr] = useState("")
  const [genDuration, setGenDuration] = useState("7")
  const [mealsPerDay, setMealsPerDay] = useState<MealsPerDay>(4)
  const [strategyMode, setStrategyMode] = useState<DietStrategyMode>("auto")
  const [dietStyle, setDietStyle] = useState("")
  const [macroProtein, setMacroProtein] = useState("")
  const [macroCarbs, setMacroCarbs] = useState("")
  const [macroFat, setMacroFat] = useState("")
  const [manualKcal, setManualKcal] = useState("")
  const [manualProteinG, setManualProteinG] = useState("")
  const [manualCarbsG, setManualCarbsG] = useState("")
  const [manualFatG, setManualFatG] = useState("")
  const [genMsg, setGenMsg] = useState<string | null>(null)
  const [generating, setGenerating] = useState(false)
  const [generatingFor, setGeneratingFor] = useState("")
  const [durationPresets, setDurationPresets] = useState<number[]>(() => [
    ...FALLBACK_PLAN_DURATION_PRESETS,
  ])
  const { addToast } = useToast()

  const handleDeleteDiet = async (e: React.MouseEvent, dietId: number, patientName: string) => {
    e.preventDefault()
    e.stopPropagation()
    if (!window.confirm(`¿Eliminar la dieta de ${patientName}? Se moverá a la papelera.`)) return
    try {
      await softDeleteDiet(dietId)
      addToast("Dieta movida a la papelera", "success")
      load()
    } catch {
      addToast("Error al eliminar dieta", "error")
    }
  }

  /* ---------- patient search hooks ---------- */
  const {
    query: filterQuery,
    setQuery: setFilterQuery,
  } = usePatientSearch()
  const {
    query: formQuery,
    setQuery: setFormQuery,
    results: formResults,
    loading: formLoading,
  } = usePatientSearch()

  // Filter patients client-side based on query
  const displayedPatients = filterQuery.trim().length >= 2
    ? allPatients.filter(p =>
        `${p.first_name} ${p.last_name}`.toLowerCase().includes(filterQuery.toLowerCase())
      )
    : allPatients

  /* ---------- effects ---------- */
  useEffect(() => {
    const p = searchParams.get("patient")
    if (p) {
      const pid = Number(p)
      setPatientIdFilter(pid)
      setGenPatientId(pid)
    }
  }, [searchParams])

  useEffect(() => {
    getPlanDurationPresets()
      .then(setDurationPresets)
      .catch(() => {})
  }, [])

  useEffect(() => {
    getPatients({ page: 1, page_size: 100 })
      .then((res) => {
        const map: Record<number, { firstName: string; lastName: string; city?: string | null }> = {}
        for (const p of res.items) {
          map[p.id] = { firstName: p.first_name, lastName: p.last_name, city: p.city }
        }
        setPatientNameMap(map)
        setPatientsCount(res.total)
      })
      .catch(() => {})
  }, [])

  const load = useCallback(() => {
    setError(null)
    return getDiets({
      patient_id: patientIdFilter,
      page,
      page_size: 20,
    })
      .then(setData)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Error"))
  }, [page, patientIdFilter])

  useEffect(() => {
    load()
  }, [load])

  /* ---------- handlers ---------- */
  function handleFilterSelect(patientId: number, firstName: string, lastName: string) {
    setPatientIdFilter(patientId)
    setGenPatientId(patientId)
    setSelectedPatientName(`${firstName} ${lastName}`)
    setFilterQuery("")
    setPage(1)
  }

  function clearFilter() {
    setPatientIdFilter(undefined)
    setGenPatientId(null)
    setSelectedPatientName(null)
    setFilterQuery("")
    setPage(1)
  }

  function handleFormSelect(patientId: number, firstName: string, lastName: string) {
    setPatientIdFilter(patientId)
    setGenPatientId(patientId)
    setSelectedPatientName(`${firstName} ${lastName}`)
    setFormQuery("")
    setPage(1)
  }

  async function onGenerate(e: FormEvent) {
    e.preventDefault()
    if (!genPatientId) {
      setError("Selecciona un paciente primero")
      return
    }
    setError(null)
    setGenMsg(null)
    setGeneratingFor(selectedPatientName || "Paciente")
    setGenerating(true)
    try {
      const clamped = clampDurationDays(genDuration)
      const strategy = buildDietStrategyBody({
        mealsPerDay,
        strategyMode,
        dietStyle,
        macroProtein,
        macroCarbs,
        macroFat,
        manualKcal,
        manualProteinG,
        manualCarbsG,
        manualFatG,
      })
      const d = await generateDiet({
        patient_id: genPatientId,
        doctor_instruction: genInstr.trim() || null,
        duration_days: clamped,
        ...strategy,
      })
      navigate(`/diets/${d.id}`)
    } catch (err) {
      setGenerating(false)
      setError(err instanceof Error ? err.message : "Error al generar")
    }
  }

  const genDurationAdjustHint = durationAdjustHint(genDuration)

  /* ---------- helpers ---------- */
  function getPatientName(diet: Diet): { firstName: string; lastName: string } | null {
    const p = patientNameMap[diet.patient_id]
    if (p) return { firstName: p.firstName, lastName: p.lastName }
    return null
  }

  /* ========== render ========== */
  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      {/* header */}
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-900">Dietas</h1>
        <button
          type="button"
          disabled={patientsCount === 0}
          onClick={() => setFormOpen(!formOpen)}
          className={`inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold text-white shadow-sm transition-colors ${
            patientsCount === 0
              ? "bg-slate-400 cursor-not-allowed"
              : "bg-emerald-600 hover:bg-emerald-500"
          }`}
          title={patientsCount === 0 ? "Debe registrar al menos un paciente para crear una dieta" : undefined}
        >
          <Plus size={18} weight="bold" />
          {formOpen ? "Cerrar" : "Nueva Dieta"}
        </button>
      </div>

      {/* collapsible generation form */}
      {formOpen && (
        <form
          onSubmit={onGenerate}
          className="mb-8 rounded-xl border border-slate-200 bg-white p-6 shadow-sm"
        >
          {/* patient search */}
          <div className="mb-4">
            <label className="mb-1.5 block text-sm font-medium text-slate-700">Paciente</label>
            <div className="relative">
              <MagnifyingGlass
                size={16}
                className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
              />
              <input
                type="text"
                value={formQuery}
                onChange={(e) => setFormQuery(e.target.value)}
                placeholder="Buscar paciente por nombre..."
                className="w-full rounded-lg border border-slate-300 py-2 pl-10 pr-3 text-sm placeholder-slate-400 focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
              />
              {formLoading && (
                <Spinner
                  size={16}
                  className="absolute right-3 top-1/2 -translate-y-1/2 animate-spin text-slate-400"
                />
              )}
            </div>
            {formResults.length > 0 && (
              <ul className="mt-1 max-h-48 overflow-y-auto rounded-lg border border-slate-200 bg-white shadow-lg">
                {formResults.map((p) => (
                  <li key={p.id}>
                    <button
                      type="button"
                      onClick={() => handleFormSelect(p.id, p.first_name, p.last_name)}
                      className="flex w-full items-center gap-3 px-3 py-2 text-left text-sm hover:bg-slate-50"
                    >
                      <Avatar firstName={p.first_name} lastName={p.last_name} size="sm" />
                      <div>
                        <span className="font-medium text-slate-900">
                          {p.first_name} {p.last_name}
                        </span>
                        {p.city && <span className="ml-2 text-xs text-slate-500">{p.city}</span>}
                      </div>
                    </button>
                  </li>
                ))}
              </ul>
            )}
            {genPatientId != null && selectedPatientName && (
              <div className="mt-2 flex items-center gap-2">
                <span className="inline-flex items-center gap-2 rounded-full bg-emerald-50 px-3 py-1 text-sm text-emerald-700">
                  {selectedPatientName}
                  <button
                    type="button"
                    onClick={() => {
                      setGenPatientId(null)
                      setSelectedPatientName(null)
                    }}
                  >
                    <X size={14} className="text-emerald-500 hover:text-emerald-700" />
                  </button>
                </span>
              </div>
            )}
          </div>

          {/* duration */}
          <div className="mb-4">
            <label className="mb-1.5 block text-sm font-medium text-slate-700">
              Duraci&oacute;n (d&iacute;as, m&uacute;ltiplo de 7)
            </label>
            <DurationPresetButtons
              presets={durationPresets}
              value={Number(genDuration) || undefined}
              onSelect={(d) => setGenDuration(String(d))}
            />
            <input
              type="number"
              min={7}
              step={7}
              value={genDuration}
              onChange={(e) => setGenDuration(e.target.value)}
              className="mt-2 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
            />
            {genDurationAdjustHint && (
              <p className="mt-1 text-xs text-slate-500">{genDurationAdjustHint}</p>
            )}
          </div>

          {/* meals per day */}
          <div className="mb-4">
            <label className="mb-1.5 block text-sm font-medium text-slate-700">
              Comidas por d&iacute;a
            </label>
            <select
              value={String(mealsPerDay)}
              onChange={(e) => setMealsPerDay(Number(e.target.value) as MealsPerDay)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
            >
              <option value="2">2 comidas: desayuno + cena</option>
              <option value="3">3 comidas: desayuno + almuerzo + cena</option>
              <option value="4">4 comidas: desayuno + almuerzo + merienda + cena</option>
              <option value="5">
                5 comidas: desayuno + media ma&ntilde;ana + almuerzo + merienda + cena
              </option>
            </select>
          </div>

          {NEXT_FEATURES.advancedStrategies && (<>
          {/* strategy mode */}
          <div className="mb-4">
            <label className="mb-1.5 block text-sm font-medium text-slate-700">
              Modo de objetivos nutricionales
            </label>
            <select
              value={strategyMode}
              onChange={(e) => setStrategyMode(e.target.value as DietStrategyMode)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
            >
              <option value="auto">Autom&aacute;tico (motor actual)</option>
              <option value="guided">Guiado (estilo y preferencias de macros)</option>
              <option value="manual">Manual (calor&iacute;as / macros; advertencias si aplica)</option>
            </select>
            {(strategyMode === "guided" || strategyMode === "manual") && (
              <p className="mt-1 text-xs text-slate-500">
                {strategyMode === "manual"
                  ? "Modo manual: el sistema puede emitir advertencias clínicas sin bloquear la generación."
                  : "Modo guiado: ajusta el reparto respecto al cálculo base del motor según estilo y preferencias."}
              </p>
            )}
          </div>

          {/* diet style (guided / manual) */}
          {(strategyMode === "guided" || strategyMode === "manual") && (
            <div className="mb-4">
              <label className="mb-1.5 block text-sm font-medium text-slate-700">
                Estilo de dieta (opcional)
              </label>
              <select
                value={dietStyle}
                onChange={(e) => setDietStyle(e.target.value)}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
              >
                <option value="">— Sin estilo espec&iacute;fico —</option>
                <option value="balanced">Equilibrada</option>
                <option value="low_carb">Baja en carbohidratos</option>
                <option value="high_carb">Alta en carbohidratos</option>
                <option value="high_protein">Alta en prote&iacute;na</option>
                <option value="mediterranean">Mediterr&aacute;nea (orientaci&oacute;n)</option>
              </select>
            </div>
          )}

          {/* guided macros */}
          {strategyMode === "guided" && (
            <div className="mb-4 grid grid-cols-3 gap-3">
              <div>
                <label className="mb-1.5 block text-sm font-medium text-slate-700">Prote&iacute;na</label>
                <select
                  value={macroProtein}
                  onChange={(e) => setMacroProtein(e.target.value)}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
                >
                  <option value="">Normal</option>
                  <option value="low">Baja</option>
                  <option value="normal">Normal</option>
                  <option value="high">Alta</option>
                </select>
              </div>
              <div>
                <label className="mb-1.5 block text-sm font-medium text-slate-700">
                  Carbohidratos
                </label>
                <select
                  value={macroCarbs}
                  onChange={(e) => setMacroCarbs(e.target.value)}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
                >
                  <option value="">Normal</option>
                  <option value="low">Baja</option>
                  <option value="normal">Normal</option>
                  <option value="high">Alta</option>
                </select>
              </div>
              <div>
                <label className="mb-1.5 block text-sm font-medium text-slate-700">Grasas</label>
                <select
                  value={macroFat}
                  onChange={(e) => setMacroFat(e.target.value)}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
                >
                  <option value="">Normal</option>
                  <option value="low">Baja</option>
                  <option value="normal">Normal</option>
                  <option value="high">Alta</option>
                </select>
              </div>
            </div>
          )}

          {/* manual targets */}
          {strategyMode === "manual" && (
            <div className="mb-4 grid grid-cols-2 gap-3">
              <div>
                <label className="mb-1.5 block text-sm font-medium text-slate-700">
                  Calor&iacute;as / d&iacute;a (opcional)
                </label>
                <input
                  type="number"
                  min={1}
                  value={manualKcal}
                  onChange={(e) => setManualKcal(e.target.value)}
                  placeholder="ej. 1800"
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm placeholder-slate-400 focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
                />
              </div>
              <div>
                <label className="mb-1.5 block text-sm font-medium text-slate-700">
                  Prote&iacute;na (g/d&iacute;a, opcional)
                </label>
                <input
                  type="number"
                  min={1}
                  step={0.1}
                  value={manualProteinG}
                  onChange={(e) => setManualProteinG(e.target.value)}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
                />
              </div>
              <div>
                <label className="mb-1.5 block text-sm font-medium text-slate-700">
                  Carbohidratos (g/d&iacute;a, opcional)
                </label>
                <input
                  type="number"
                  min={1}
                  step={0.1}
                  value={manualCarbsG}
                  onChange={(e) => setManualCarbsG(e.target.value)}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
                />
              </div>
              <div>
                <label className="mb-1.5 block text-sm font-medium text-slate-700">
                  Grasas (g/d&iacute;a, opcional)
                </label>
                <input
                  type="number"
                  min={1}
                  step={0.1}
                  value={manualFatG}
                  onChange={(e) => setManualFatG(e.target.value)}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
                />
              </div>
            </div>
          )}
          </>)}

          {/* instructions */}
          <div className="mb-4">
            <label className="mb-1.5 block text-sm font-medium text-slate-700">
              Instrucciones para el modelo (opcional)
            </label>
            <textarea
              value={genInstr}
              onChange={(e) => setGenInstr(e.target.value)}
              rows={3}
              placeholder="ej. evitar lácteos, económico"
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm placeholder-slate-400 focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
            />
          </div>

          <button
            type="submit"
            className="inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-emerald-500"
          >
            Generar Dieta
          </button>
        </form>
      )}

      {/* status messages */}
      {genMsg && (
        <div className="mb-4 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
          {genMsg}
        </div>
      )}
      {error && (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Patient filter — search input with dropdown */}
      <div className="mb-6 relative" ref={filterRef}>
        <div className="relative">
          <MagnifyingGlass
            size={16}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
          />
          <input
            type="text"
            value={patientIdFilter != null && selectedPatientName ? selectedPatientName : filterQuery}
            onChange={(e) => {
              setFilterQuery(e.target.value)
              if (patientIdFilter != null) clearFilter()
              setFilterOpen(true)
            }}
            onFocus={() => setFilterOpen(true)}
            placeholder="Buscar paciente por nombre..."
            className="w-full max-w-sm rounded-xl border border-slate-300 py-2.5 pl-10 pr-10 text-sm placeholder-slate-400 focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/20 transition-colors"
          />
          {patientIdFilter != null && selectedPatientName && (
            <button
              type="button"
              onClick={clearFilter}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
            >
              <X size={16} />
            </button>
          )}
        </div>

        {/* Dropdown */}
        {filterOpen && allPatients.length > 0 && (
          <>
            <div className="fixed inset-0 z-10" onClick={() => setFilterOpen(false)} />
            <div className="absolute z-20 mt-1 w-full max-w-sm rounded-xl border border-slate-200 bg-white shadow-xl max-h-64 overflow-y-auto">
              {displayedPatients.length > 0 ? (
                displayedPatients.map((p) => (
                  <button
                    key={p.id}
                    type="button"
                    onClick={() => { handleFilterSelect(p.id, p.first_name, p.last_name); setFilterOpen(false) }}
                    className="flex w-full items-center gap-3 px-4 py-2.5 text-left text-sm transition-colors hover:bg-slate-50"
                  >
                    <Avatar firstName={p.first_name} lastName={p.last_name} size="sm" />
                    <div>
                      <span className="font-medium text-slate-800">{p.first_name} {p.last_name}</span>
                      {p.city && <span className="ml-1.5 text-xs text-slate-400">{p.city}</span>}
                    </div>
                  </button>
                ))
              ) : (
                <p className="px-4 py-6 text-center text-sm text-slate-400">No se encontraron pacientes</p>
              )}
            </div>
          </>
        )}
      </div>

      {/* active filter info */}
      {patientIdFilter != null && selectedPatientName && (
        <p className="mb-4 text-sm text-slate-500">
          Mostrando dietas de <span className="font-medium text-slate-700">{selectedPatientName}</span>
          {data ? ` · ${data.total} encontradas` : ""}
        </p>
      )}

      {/* loading state */}
      {!data ? (
        <div className="divide-y divide-slate-100 rounded-xl border border-slate-200 bg-white">
          {Array.from({ length: 5 }).map((_, i) => (
            <SkeletonRow key={i} />
          ))}
        </div>
      ) : data.items.length === 0 ? (
        <EmptyState
          icon={<BowlFood size={48} weight="thin" />}
          title="Sin dietas"
          description={
            patientsCount === 0
              ? "Debe registrar al menos un paciente antes de crear una dieta."
              : patientIdFilter != null
                ? "Este paciente no tiene dietas generadas aún."
                : "No hay dietas generadas aún. Crea una nueva usando el formulario."
          }
          action={
            !formOpen ? (
              <button
                type="button"
                disabled={patientsCount === 0}
                onClick={() => setFormOpen(true)}
                className={`rounded-lg px-4 py-2 text-sm font-semibold text-white transition-colors ${
                  patientsCount === 0
                    ? "bg-slate-400 cursor-not-allowed"
                    : "bg-emerald-600 hover:bg-emerald-500"
                }`}
                title={patientsCount === 0 ? "Debe registrar al menos un paciente para crear una dieta" : undefined}
              >
                Nueva Dieta
              </button>
            ) : undefined
          }
        />
      ) : (
        <>
          {/* table */}
          <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
            {data.items.map((d: Diet) => {
              const name = getPatientName(d)
              const plan = d.structured_plan_json as Record<string, unknown> | undefined
              const days = (plan?.plan_duration_days as number) ?? 7
              return (
                <Link
                  key={d.id}
                  to={`/diets/${d.id}`}
                  className="flex items-center gap-4 px-5 py-3.5 border-b border-slate-100 last:border-b-0 transition-colors hover:bg-slate-50 cursor-pointer group"
                >
                  {name ? (
                    <Avatar firstName={name.firstName} lastName={name.lastName} size="md" />
                  ) : (
                    <div className="flex h-10 w-10 items-center justify-center rounded-full bg-slate-100 text-xs font-semibold text-slate-500 shrink-0">
                      ?
                    </div>
                  )}
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-slate-800 truncate">
                      {name ? `${name.firstName} ${name.lastName}` : `Paciente #${d.patient_id}`}
                    </p>
                    <p className="text-xs text-slate-500 mt-0.5">
                      {formatDate(d.created_at)} · {days} días
                    </p>
                  </div>
                  <button
                    onClick={(e) => handleDeleteDiet(e, d.id, name ? `${name.firstName} ${name.lastName}` : `#${d.patient_id}`)}
                    className="p-1.5 rounded-lg text-slate-300 hover:text-red-500 hover:bg-red-50 transition-all shrink-0 opacity-0 group-hover:opacity-100"
                    title="Eliminar dieta"
                  >
                    <Trash size={16} />
                  </button>
                  <span className="text-slate-300 group-hover:text-emerald-500 transition-colors shrink-0">
                    &rarr;
                  </span>
                </Link>
              )
            })}
          </div>

          {/* pagination */}
          <div className="mt-4 flex items-center justify-between">
            <span className="text-sm text-slate-500">
              P&aacute;gina {page} &middot; {data.total} total
            </span>
            <div className="flex items-center gap-2">
              <button
                type="button"
                disabled={page <= 1}
                onClick={() => setPage((p) => p - 1)}
                className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-600 transition-colors hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
              >
                Anterior
              </button>
              <button
                type="button"
                disabled={page * data.page_size >= data.total}
                onClick={() => setPage((p) => p + 1)}
                className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-600 transition-colors hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
              >
                Siguiente
              </button>
            </div>
          </div>
        </>
      )}
      <GenerationOverlay
        open={generating}
        patientName={generatingFor}
        onComplete={() => {}}
      />
    </div>
  )
}
