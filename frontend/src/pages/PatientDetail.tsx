import { FormEvent, useCallback, useEffect, useState } from "react"
import { Link, useParams } from "react-router-dom"
import {
  addMetric,
  getMetrics,
  getPatient,
  getPatientSummary,
  getProfile,
  patchPatient,
  patchProfile,
} from "../services/api"
import { SkeletonCard } from "../components/ui/Skeleton"
import { useToast } from "../context/ToastContext"
import type { Patient, PatientMetric, PatientProfile, PatientSummary } from "../types"
import DatePicker from "../components/ui/DatePicker"
import OptionalField from "../components/ui/OptionalField"
import WeightInput from "../components/ui/WeightInput"
import HeightInput from "../components/ui/HeightInput"
import { OBJECTIVE_OPTIONS } from "../constants/objectives"
import ConfirmModal from "../components/ui/ConfirmModal"
import type { ChangeItem } from "../components/ui/ConfirmModal"
import LocationSelector from "../components/LocationSelector"

// ── Opciones predefinidas ───────────────────────────────────────────────────

const DISEASE_OPTIONS = [
  "Diabetes",
  "Hipertensión",
  "Problemas renales",
  "Dislipidemia",
]

const ALLERGY_OPTIONS = [
  "Gluten",
  "Lactosa",
  "Mariscos",
  "Nueces/frutos secos",
  "Huevo",
  "Soja",
]

const DIETARY_STYLE_OPTIONS = [
  "Equilibrada",
  "Baja en carbohidratos",
  "Alta en carbohidratos",
  "Alta en proteína",
  "Mediterránea",
]

const EXERCISE_TYPE_OPTIONS = [
  "Fuerza",
  "Cardio",
  "Fuerza + Cardio",
  "Yoga/Pilates",
  "Natación",
  "Caminata",
  "Deporte de equipo",
]

const FOODS_AVOIDED_OPTIONS = [
  "Carnes rojas",
  "Cerdo",
  "Azúcar procesada",
  "Frituras",
]

const FOOD_PREFERENCES_OPTIONS = [
  "Pollo", "Pescado", "Verduras", "Frutas", "Arroz",
  "Pasta", "Pan", "Legumbres", "Huevos", "Lácteos",
  "Frutos secos", "Dulces",
]

// ── Helpers ─────────────────────────────────────────────────────────────────

const INPUT_CLASSES =
  "w-full px-3.5 py-2.5 text-sm border border-slate-200 rounded-xl bg-white text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 transition-colors"

const SELECT_CLASSES =
  "w-full px-3.5 py-2.5 text-sm border border-slate-200 rounded-xl bg-white text-slate-800 focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 transition-colors"

function parseMultiValue(
  raw: string | null | undefined,
  options: string[]
): [string[], string] {
  if (!raw) return [[], ""]
  const parts = raw
    .split(/,\s*/)
    .map((s) => s.trim())
    .filter(Boolean)
  const known = parts.filter((p) => options.includes(p))
  const other = parts.filter((p) => !options.includes(p)).join(", ")
  return [known, other]
}

function buildMultiValue(pills: string[], otherText: string): string | null {
  const all = [...pills]
  if (otherText.trim()) all.push(otherText.trim())
  return all.length > 0 ? all.join(", ") : null
}

function calculateAge(birthDate?: string | null): number | null {
  if (!birthDate) return null
  const birth = new Date(birthDate)
  const today = new Date()
  let age = today.getFullYear() - birth.getFullYear()
  const m = today.getMonth() - birth.getMonth()
  if (m < 0 || (m === 0 && today.getDate() < birth.getDate())) age--
  return age
}

function bmiClassification(bmi: number): string {
  if (bmi < 18.5) return "Bajo peso"
  if (bmi < 25) return "Normal"
  if (bmi < 30) return "Sobrepeso"
  return "Obesidad"
}

function calcIMC(
  weight: number | null | undefined,
  height: number | null | undefined
): number | null {
  if (weight == null || height == null || height === 0) return null
  return Math.round((weight / ((height / 100) ** 2)) * 10) / 10
}

function getInitials(firstName?: string | null, lastName?: string | null): string {
  const f = firstName?.charAt(0) ?? ""
  const l = lastName?.charAt(0) ?? ""
  return (f + l).toUpperCase() || "?"
}

function timeAgo(dateStr?: string | null): string {
  if (!dateStr) return ""
  const now = new Date()
  const date = new Date(dateStr)
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  if (diffMins < 1) return "recién"
  if (diffMins < 60) return `hace ${diffMins} min`
  const diffHours = Math.floor(diffMins / 60)
  if (diffHours < 24) return `hace ${diffHours}h`
  const diffDays = Math.floor(diffHours / 24)
  if (diffDays === 1) return "hace 1 día"
  if (diffDays < 30) return `hace ${diffDays} días`
  const diffMonths = Math.floor(diffDays / 30)
  if (diffMonths === 1) return "hace 1 mes"
  if (diffMonths < 12) return `hace ${diffMonths} meses`
  const years = Math.floor(diffMonths / 12)
  return `hace ${years} años`
}

function formatDate(dateStr?: string | null): string {
  if (!dateStr) return ""
  const d = new Date(dateStr)
  return d.toLocaleDateString("es-ES", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  })
}

function checkMissingDemographics(patientData: Partial<Patient>): string[] {
  const missing: string[] = []
  if (!patientData.birth_date) missing.push("fecha de nacimiento")
  if (!patientData.sex) missing.push("sexo")
  if (!patientData.country || !patientData.city) missing.push("país o ciudad")
  return missing
}

function checkMissingProfile(profileData: Partial<PatientProfile> | null): string[] {
  const missing: string[] = []
  if (!profileData) {
    missing.push("perfil clínico completo")
  } else {
    if (!profileData.objective) missing.push("objetivo")
    if (!profileData.food_allergies) missing.push("alergias alimentarias")
    if (!profileData.foods_avoided) missing.push("alimentos a evitar")
  }
  return missing
}

// ── WeightSparkline ─────────────────────────────────────────────────────────

function WeightSparkline({ metrics }: { metrics: PatientMetric[] }) {
  const weightData = metrics
    .filter((m) => m.weight_kg != null)
    .slice(-30)
    .map((m) => m.weight_kg as number)

  if (weightData.length < 2) return null

  const w = 200
  const h = 48
  const min = Math.min(...weightData)
  const max = Math.max(...weightData)
  const range = max - min || 1
  const padding = 3

  const points = weightData
    .map((val, i) => {
      const x = (i / (weightData.length - 1)) * w
      const y = h - ((val - min) / range) * (h - padding * 2) - padding
      return `${x},${y}`
    })
    .join(" ")

  return (
    <svg
      viewBox={`0 0 ${w} ${h}`}
      className="w-full h-12"
      preserveAspectRatio="none"
    >
      <polyline
        fill="none"
        stroke="#059669"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        points={points}
      />
    </svg>
  )
}

// ── Componente PillSelect ───────────────────────────────────────────────────

interface PillSelectProps {
  options: string[]
  selected: string[]
  otherText: string
  onChange: (selected: string[]) => void
  onOtherChange: (text: string) => void
  hasOther?: boolean
}

function PillSelect({
  options,
  selected,
  otherText,
  onChange,
  onOtherChange,
  hasOther = true,
}: PillSelectProps) {
  const toggle = (opt: string) => {
    if (selected.includes(opt)) {
      onChange(selected.filter((s) => s !== opt))
    } else {
      onChange([...selected, opt])
    }
  }

  const [showOther, setShowOther] = useState(otherText !== "")

  useEffect(() => {
    setShowOther(otherText !== "")
  }, [otherText])

  const toggleOther = () => {
    if (showOther) {
      setShowOther(false)
      onOtherChange("")
    } else {
      setShowOther(true)
    }
  }

  const pillBase = "px-3 py-1 rounded-full text-sm font-medium cursor-pointer transition-all select-none"
  const pillActive = "bg-emerald-600 text-white shadow-sm"
  const pillInactive = "bg-white border border-slate-200 text-slate-700 hover:border-slate-300 hover:bg-slate-50"

  return (
    <div className="mb-2">
      <div className="flex flex-wrap gap-1.5">
        {options.map((opt) => {
          const active = selected.includes(opt)
          return (
            <button
              key={opt}
              type="button"
              onClick={() => toggle(opt)}
              className={`${pillBase} ${active ? pillActive : pillInactive}`}
            >
              {opt}
            </button>
          )
        })}
        {hasOther && (
          <button
            type="button"
            onClick={toggleOther}
            className={`${pillBase} ${showOther ? pillActive : pillInactive}`}
          >
            Otro
          </button>
        )}
      </div>
      {hasOther && showOther && (
        <input
          type="text"
          value={otherText}
          onChange={(e) => onOtherChange(e.target.value)}
          placeholder="Especificar..."
          className={`${INPUT_CLASSES} mt-2`}
        />
      )}
    </div>
  )
}

// ── Etiquetas para el modal de confirmación ─────────────────────────────────

const profileLabels: Record<string, string> = {
  objective: "Objetivo",
  diseases: "Enfermedades",
  medications: "Medicamentos",
  food_allergies: "Alergias alimentarias",
  foods_avoided: "Alimentos a evitar",
  medical_history: "Historial médico",
  dietary_style: "Patrón alimentario",
  food_preferences: "Alimentos que le gustan",
  water_intake_liters: "Agua (L/día)",
  activity_level: "Actividad física",
  stress_level: "Estrés",
  sleep_quality: "Calidad del sueño",
  sleep_hours: "Horas de sueño",
  budget_level: "Presupuesto",
  adherence_level: "Disposición al cambio",
  exercise_type: "Tipo de ejercicio",
  extra_notes: "Notas adicionales",
  weight_kg: "Peso",
  height_cm: "Altura",
  neck_cm: "Cuello",
  chest_cm: "Pecho",
  waist_cm: "Cintura",
  hip_cm: "Cadera",
  leg_cm: "Pierna",
  calf_cm: "Pantorrilla",
  first_name: "Nombre",
  last_name: "Apellido",
  whatsapp: "WhatsApp",
  email: "Email",
  country: "País",
  city: "Ciudad",
}

// ── Componente principal ────────────────────────────────────────────────────

export default function PatientDetail() {
  const { patientId: idParam } = useParams()
  const patientId = Number(idParam)
  const { addToast } = useToast()

  const [patient, setPatient] = useState<Patient | null>(null)
  const [summary, setSummary] = useState<PatientSummary | null>(null)
  const [profile, setProfile] = useState<PatientProfile | null>(null)
  const [metrics, setMetrics] = useState<PatientMetric[]>([])
  const [error, setError] = useState<string | null>(null)

  // Metric form
  const [mWeight, setMWeight] = useState("")
  const [mHeight, setMHeight] = useState("")
  const [mNeck, setMNeck] = useState("")
  const [mChest, setMChest] = useState("")
  const [mWaist, setMWaist] = useState("")
  const [mHip, setMHip] = useState("")
  const [mLeg, setMLeg] = useState("")
  const [mCalf, setMCalf] = useState("")
  const [mNotes, setMNotes] = useState("")

  // Edit form controlled states
  const [editBirthDate, setEditBirthDate] = useState(
    patient?.birth_date?.slice(0, 10) ?? "",
  )
  const [editMedications, setEditMedications] = useState(
    profile?.medications ?? "",
  )

  // Inline edit booleans
  const [editingData, setEditingData] = useState(false)
  const [editingProfile, setEditingProfile] = useState(false)
  const [editCountry, setEditCountry] = useState(patient?.country ?? "")
  const [editCity, setEditCity] = useState(patient?.city ?? "")
  const [showMetricForm, setShowMetricForm] = useState(false)
  const [editingMetricId, setEditingMetricId] = useState<number | null>(null)

  // Form keys to force re-mount with fresh defaults
  const [dataFormKey, setDataFormKey] = useState(0)
  const [profileFormKey, setProfileFormKey] = useState(0)

  // ── Modal de confirmación ───────────────────────────────────────────────
  const [confirmModal, setConfirmModal] = useState<{
    open: boolean
    changes: ChangeItem[]
    onConfirm: () => void
  }>({
    open: false,
    changes: [],
    onConfirm: () => {},
  })
  const [confirmLoading, setConfirmLoading] = useState(false)

  // ── Estado multi-selección del perfil clínico ───────────────────────────
  const [diseasesPills, setDiseasesPills] = useState<string[]>([])
  const [diseasesOther, setDiseasesOther] = useState("")
  const [allergiesPills, setAllergiesPills] = useState<string[]>([])
  const [allergiesOther, setAllergiesOther] = useState("")
  const [dietaryPills, setDietaryPills] = useState<string[]>([])
  const [dietaryOther, setDietaryOther] = useState("")
  const [exerciseTypePills, setExerciseTypePills] = useState<string[]>([])
  const [exerciseTypeOther, setExerciseTypeOther] = useState("")
  const [foodsAvoidedPills, setFoodsAvoidedPills] = useState<string[]>([])
  const [foodsAvoidedOther, setFoodsAvoidedOther] = useState("")
  const [foodPrefsPills, setFoodPrefsPills] = useState<string[]>([])
  const [foodPrefsOther, setFoodPrefsOther] = useState("")

  // Inicializar pills desde perfil cargado
  useEffect(() => {
    if (!profile) return
    const [dp, do_] = parseMultiValue(profile.diseases, DISEASE_OPTIONS)
    setDiseasesPills(dp)
    setDiseasesOther(do_)
    const [ap, ao] = parseMultiValue(profile.food_allergies, ALLERGY_OPTIONS)
    setAllergiesPills(ap)
    setAllergiesOther(ao)
    const [dsp, dso] = parseMultiValue(profile.dietary_style, DIETARY_STYLE_OPTIONS)
    setDietaryPills(dsp)
    setDietaryOther(dso)
    const [etp, eto] = parseMultiValue(profile.exercise_type, EXERCISE_TYPE_OPTIONS)
    setExerciseTypePills(etp)
    setExerciseTypeOther(eto)
    const [fap, fao] = parseMultiValue(profile.foods_avoided, FOODS_AVOIDED_OPTIONS)
    setFoodsAvoidedPills(fap)
    setFoodsAvoidedOther(fao)
    const [fpp, fpo] = parseMultiValue(profile.food_preferences, FOOD_PREFERENCES_OPTIONS)
    setFoodPrefsPills(fpp)
    setFoodPrefsOther(fpo)  }, [profile])

  // ── Carga inicial de datos ─────────────────────────────────────────────
  useEffect(() => {
    if (!patientId || Number.isNaN(patientId)) return
    let cancelled = false
    setError(null)
    setPatient(null)
    setProfile(null)
    setSummary(null)
    setMetrics([])

    Promise.all([
      getPatient(patientId),
      getProfile(patientId).catch(() => null),
      getPatientSummary(patientId).catch(() => null),
      getMetrics(patientId).catch(() => [] as PatientMetric[]),
    ])
      .then(([p, pr, s, m]) => {
        if (cancelled) return
        setPatient(p)
        if (pr) setProfile(pr as PatientProfile)
        if (s) setSummary(s as PatientSummary)
        setMetrics(m as PatientMetric[])
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : "Error")
      })

    return () => {
      cancelled = true
    }
  }, [patientId])

  const refreshMetrics = useCallback(async () => {
    const m = await getMetrics(patientId)
    setMetrics(m)
  }, [patientId])

  // ── Handlers ───────────────────────────────────────────────────────────

  async function onSaveData(e: FormEvent) {
    e.preventDefault()
    if (!patient) return
    setError(null)
    try {
      const form = e.target as HTMLFormElement
      const fd = new FormData(form)
      const body: Record<string, unknown> = {
        first_name: fd.get("first_name") as string,
        last_name: fd.get("last_name") as string,
        birth_date: (fd.get("birth_date") as string) || null,
        sex: (fd.get("sex") as string) || null,
        email: (fd.get("email") as string) || null,
        whatsapp: (fd.get("whatsapp") as string) || null,
        country: editCountry || null,
        city: editCity || null,
        is_active: fd.get("is_active") === "on",
        is_archived: fd.get("is_archived") === "on",
      }
      const p = await patchPatient(patientId, body)
      setPatient(p)
      const missing = checkMissingDemographics(p)
      if (missing.length > 0) {
        addToast(
          `Para crear una dieta, complete: ${missing.join(", ")}.`,
          "info",
        )
      }
      setEditingData(false)
      addToast("Datos guardados", "success")
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error")
      addToast(err instanceof Error ? err.message : "Error al guardar", "error")
    }
  }

  function onSaveProfile(e: FormEvent) {
    e.preventDefault()
    setError(null)
    const form = e.target as HTMLFormElement
    const fd = new FormData(form)
    const num = (k: string) => {
      const v = fd.get(k) as string
      if (!v) return null
      const n = Number(v)
      return Number.isFinite(n) ? n : null
    }
    const body: Record<string, unknown> = {
      objective: (fd.get("objective") as string) || null,
      diseases: buildMultiValue(diseasesPills, diseasesOther),
      medications: (fd.get("medications") as string) || null,
      food_allergies: buildMultiValue(allergiesPills, allergiesOther),
      foods_avoided: buildMultiValue(foodsAvoidedPills, foodsAvoidedOther),
      food_preferences: buildMultiValue(foodPrefsPills, foodPrefsOther),
      medical_history: (fd.get("medical_history") as string) || null,
      dietary_style: buildMultiValue(dietaryPills, dietaryOther),
      disliked_foods: buildMultiValue(foodsAvoidedPills, foodsAvoidedOther),  // dual-write for backward compat
      water_intake_liters: num("water_intake_liters"),
      activity_level: (fd.get("activity_level") as string) || null,
      stress_level: num("stress_level"),
      sleep_quality: num("sleep_quality"),
      sleep_hours: num("sleep_hours"),
      budget_level: (fd.get("budget_level") as string) || null,
      adherence_level: num("adherence_level"),
      exercise_type: buildMultiValue(exerciseTypePills, exerciseTypeOther),
      extra_notes: (fd.get("extra_notes") as string) || null,
    }

    const changes: ChangeItem[] = []
    for (const [key, newVal] of Object.entries(body)) {
      const label = profileLabels[key] ?? key
      const oldVal = profile?.[key as keyof PatientProfile]
      const newStr = newVal == null ? "" : String(newVal)
      const oldStr = oldVal == null ? "" : String(oldVal)
      if (newStr !== oldStr) {
        changes.push({
          label,
          oldValue: oldStr || undefined,
          newValue: newStr || "—",
        })
      }
    }

    if (changes.length === 0) {
      addToast("Sin cambios que guardar", "info")
      return
    }

    setConfirmModal({
      open: true,
      changes,
      onConfirm: async () => {
        setConfirmLoading(true)
        try {
          const pr = await patchProfile(patientId, body)
          setProfile(pr)
          const missing = checkMissingProfile(pr)
          if (missing.length > 0) {
            addToast(
              `Para crear una dieta, aún falta: ${missing.join(", ")}.`,
              "info",
            )
          }
          setEditingProfile(false)
          addToast("Perfil guardado", "success")
        } catch (err) {
          setError(err instanceof Error ? err.message : "Error")
          addToast(err instanceof Error ? err.message : "Error al guardar", "error")
        } finally {
          setConfirmLoading(false)
          setConfirmModal({ open: false, changes: [], onConfirm: () => {} })
        }
      },
    })
  }

  function resetMetricForm() {
    setMWeight("")
    setMHeight("")
    setMNeck("")
    setMChest("")
    setMWaist("")
    setMHip("")
    setMLeg("")
    setMCalf("")
    setMNotes("")
    setEditingMetricId(null)
  }

  function populateMetricForm(m: PatientMetric) {
    setMWeight(m.weight_kg != null ? String(m.weight_kg) : "")
    setMHeight(m.height_cm != null ? String(m.height_cm) : "")
    setMNeck(m.neck_cm != null ? String(m.neck_cm) : "")
    setMChest(m.chest_cm != null ? String(m.chest_cm) : "")
    setMWaist(m.waist_cm != null ? String(m.waist_cm) : "")
    setMHip(m.hip_cm != null ? String(m.hip_cm) : "")
    setMLeg(m.leg_cm != null ? String(m.leg_cm) : "")
    setMCalf(m.calf_cm != null ? String(m.calf_cm) : "")
    setMNotes(m.notes ?? "")
    setEditingMetricId(m.id)
    setShowMetricForm(true)
  }

  async function onAddMetric(e: FormEvent) {
    e.preventDefault()
    setError(null)
    try {
      const body = {
        weight_kg: mWeight ? Number(mWeight) : null,
        height_cm: mHeight ? Number(mHeight) : null,
        neck_cm: mNeck ? Number(mNeck) : null,
        chest_cm: mChest ? Number(mChest) : null,
        waist_cm: mWaist ? Number(mWaist) : null,
        hip_cm: mHip ? Number(mHip) : null,
        leg_cm: mLeg ? Number(mLeg) : null,
        calf_cm: mCalf ? Number(mCalf) : null,
        notes: mNotes || null,
        source: "admin",
      }
      if (editingMetricId != null) {
        const { updateMetric } = await import("../services/api")
        await updateMetric(patientId, editingMetricId, body)
        addToast("Medición actualizada", "success")
      } else {
        await addMetric(patientId, body)
        addToast("Medición registrada", "success")
      }
      resetMetricForm()
      setShowMetricForm(false)
      await refreshMetrics()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error")
      addToast(err instanceof Error ? err.message : "Error al guardar métrica", "error")
    }
  }

  // ── Guard de paciente inválido ─────────────────────────────────────────

  if (!patientId || Number.isNaN(patientId)) {
    return (
      <div className="max-w-5xl mx-auto px-4 py-12 text-center">
        <p className="text-slate-500 text-lg">Paciente no válido</p>
        <Link
          to="/patients"
          className="mt-4 inline-block text-sm text-emerald-600 hover:text-emerald-700 font-medium"
        >
          ← Volver a pacientes
        </Link>
      </div>
    )
  }

  // ── Estado de carga ────────────────────────────────────────────────────

  if (!patient) {
    if (error) {
      return (
        <div className="max-w-5xl mx-auto px-4 py-12 text-center">
          <div className="bg-red-50 rounded-2xl p-8 max-w-md mx-auto">
            <p className="text-red-700 font-medium mb-2">Error al cargar paciente</p>
            <p className="text-red-500 text-sm mb-4">{error}</p>
            <button
              type="button"
              onClick={() => window.location.reload()}
              className="px-4 py-2 rounded-xl text-sm font-medium bg-red-600 text-white hover:bg-red-700 transition-colors"
            >
              Reintentar
            </button>
          </div>
        </div>
      )
    }

    return (
      <div className="max-w-5xl mx-auto px-4 py-6 space-y-6">
        <SkeletonCard />
        <SkeletonCard />
        <SkeletonCard />
        <SkeletonCard />
      </div>
    )
  }

  // ── Datos calculados ───────────────────────────────────────────────────

  const latestMetric = summary?.latest_metrics
  const age = calculateAge(patient.birth_date)
  const bmi =
    latestMetric?.weight_kg != null && latestMetric?.height_cm != null
      ? calcIMC(latestMetric.weight_kg, latestMetric.height_cm)
      : null
  const sortedMetrics = [...metrics].sort(
    (a, b) => new Date(a.recorded_at).getTime() - new Date(b.recorded_at).getTime()
  )
  const lastRecordedAt = sortedMetrics.length > 0
    ? sortedMetrics[sortedMetrics.length - 1].recorded_at
    : null

  // ── Render principal ───────────────────────────────────────────────────

  function renderDataView(p: Patient) {
    const fields: { label: string; value: string | null | undefined }[] = [
      { label: "Nombre", value: p.first_name },
      { label: "Apellido", value: p.last_name },
      { label: "Fecha de nacimiento", value: p.birth_date?.slice(0, 10) ?? null },
      { label: "Sexo", value: p.sex },
      { label: "Correo electrónico", value: p.email },
      { label: "WhatsApp", value: p.whatsapp },
      { label: "País", value: p.country },
      { label: "Ciudad", value: p.city },
      {
        label: "Estado",
        value: p.is_archived ? "Archivado" : p.is_active ? "Activo" : "Inactivo",
      },
    ]

    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-8 gap-y-2.5">
        {fields.map((f) => (
          <div key={f.label}>
            <span className="text-xs text-slate-500">{f.label}</span>
            <p className="text-sm text-slate-800">{f.value ?? "—"}</p>
          </div>
        ))}
      </div>
    )
  }

  function renderProfileField(label: string, value: string | null | undefined) {
    return (
      <div>
        <span className="text-xs text-slate-500">{label}</span>
        <p className="text-sm text-slate-800">{value ?? "—"}</p>
      </div>
    )
  }

  function renderTag(value: string) {
    return (
      <span
        key={value}
        className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-700"
      >
        {value}
      </span>
    )
  }

  function renderMultiTag(raw: string | null | undefined) {
    if (!raw) return <span className="text-sm text-slate-400">—</span>
    return (
      <div className="flex flex-wrap gap-1">
        {raw.split(", ").map((v) => renderTag(v))}
      </div>
    )
  }

  return (
    <>
    <div className="max-w-5xl mx-auto px-4 py-6 space-y-6">
      {/* ── Error banner ──────────────────────────────────────────────── */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-xl px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* ── Breadcrumb + Actions ──────────────────────────────────────── */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <nav className="flex items-center gap-2 text-sm text-slate-500">
          <Link
            to="/patients"
            className="hover:text-emerald-600 transition-colors font-medium"
          >
            ← Pacientes
          </Link>
          <span className="text-slate-300">/</span>
          <span className="text-slate-800 font-semibold">
            {patient.first_name} {patient.last_name}
          </span>
        </nav>

        <div className="flex gap-2 flex-wrap">
          {editingData || editingProfile ? (
            <button
              type="button"
              onClick={() => {
                setEditingData(false)
                setEditingProfile(false)
              }}
              className="px-4 py-1.5 rounded-full text-sm font-medium bg-white border border-slate-200 text-slate-700 hover:border-slate-300 transition-colors"
            >
              Cancelar edición
            </button>
          ) : (
            <button
              type="button"
              onClick={() => {
                setDataFormKey((k) => k + 1)
                setProfileFormKey((k) => k + 1)
                setEditBirthDate(patient.birth_date?.slice(0, 10) ?? "")
                setEditMedications(profile?.medications ?? "")
                setEditCountry(patient.country ?? "")
                setEditCity(patient.city ?? "")
                setEditingData(true)
                setEditingProfile(true)
              }}
              className="px-4 py-1.5 rounded-full text-sm font-medium bg-emerald-600 text-white hover:bg-emerald-700 transition-colors shadow-sm"
            >
              Editar
            </button>
          )}
          <Link
            to={`/diets/new?patient=${patientId}`}
            className="px-4 py-1.5 rounded-full text-sm font-medium bg-white border border-slate-200 text-slate-700 hover:border-slate-300 hover:text-emerald-600 transition-colors"
          >
            Nueva Dieta
          </Link>
          <button
            type="button"
            onClick={() =>
              addToast("Funcionalidad en desarrollo — pronto podrás enviar formularios", "info")
            }
            className="px-4 py-1.5 rounded-full text-sm font-medium bg-white border border-slate-200 text-slate-700 hover:border-slate-300 transition-colors"
          >
            Enviar Formulario
          </button>
          <button
            type="button"
            onClick={() => setShowMetricForm((v) => !v)}
            className="px-4 py-1.5 rounded-full text-sm font-medium bg-white border border-slate-200 text-slate-700 hover:border-slate-300 hover:text-emerald-600 transition-colors"
          >
            + Métricas
          </button>
        </div>
      </div>

      {/* ── Cabecera ────────────────────────────────────────────────────── */}
      <div className="bg-white rounded-2xl p-6 shadow-sm border border-slate-100">
        <div className="flex items-center gap-4">
          <div className="w-16 h-16 rounded-full bg-gradient-to-br from-emerald-400 to-emerald-600 flex items-center justify-center text-white text-xl font-bold shrink-0 shadow-sm">
            {getInitials(patient.first_name, patient.last_name)}
          </div>
          <div className="min-w-0">
            <h1 className="text-2xl font-bold text-slate-900 truncate">
              {patient.first_name} {patient.last_name}
            </h1>
            <p className="text-sm text-slate-500 mt-0.5">
              {[age != null && `${age} años`, patient.sex, patient.city]
                .filter(Boolean)
                .join(" · ") || "—"}
            </p>
            <div className="flex flex-wrap gap-x-4 gap-y-0.5 mt-1">
              {patient.email && (
                <span className="text-sm text-slate-500">{patient.email}</span>
              )}
              {patient.whatsapp && (
                <span className="text-sm text-slate-500">{patient.whatsapp}</span>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* ── Resumen ──────────────────────────────────────────────────────── */}
      <div className="bg-white rounded-2xl p-6 shadow-sm border border-slate-100">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">
              Datos corporales
            </h2>
            <div className="space-y-1.5 text-sm">
              <p>
                <span className="text-slate-500">Peso:</span>{" "}
                <span className="text-slate-800 font-medium">
                  {latestMetric?.weight_kg != null ? `${latestMetric.weight_kg} kg` : "—"}
                </span>
              </p>
              <p>
                <span className="text-slate-500">Altura:</span>{" "}
                <span className="text-slate-800 font-medium">
                  {latestMetric?.height_cm != null ? `${latestMetric.height_cm} cm` : "—"}
                </span>
              </p>
              <p>
                <span className="text-slate-500">IMC:</span>{" "}
                <span className="text-slate-800 font-medium">
                  {bmi != null
                    ? `${bmi} (${bmiClassification(bmi)})`
                    : "—"}
                </span>
              </p>
            </div>
            {lastRecordedAt && (
              <p className="text-xs text-slate-400 mt-3">
                Último registro: {timeAgo(lastRecordedAt)}
              </p>
            )}
          </div>

          <div className="flex flex-col justify-center">
            {metrics.filter((m) => m.weight_kg != null).length > 1 ? (
              <div>
                <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
                  Tendencia de peso
                </p>
                <WeightSparkline metrics={metrics} />
              </div>
            ) : (
              <div className="flex items-center justify-center h-full">
                <p className="text-xs text-slate-400">
                  Se necesitan al menos 2 mediciones con peso para mostrar la tendencia
                </p>
              </div>
            )}
          </div>
        </div>

        {summary?.latest_diet && (
          <div className="mt-4 pt-4 border-t border-slate-100">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
              <div className="flex items-center gap-3">
                <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-100 text-emerald-700">
                  Dieta activa
                </span>
                <div className="text-sm text-slate-600">
                  Plan nutricional &middot; Creada el{" "}
                  {formatDate(summary.latest_diet.created_at)}
                  {summary.latest_diet.plan_duration_days != null &&
                    summary.latest_diet.plan_duration_days > 0 &&
                    ` · ${summary.latest_diet.plan_duration_days} días`}
                </div>
              </div>
              <Link
                to={`/diets/${summary.latest_diet.id}`}
                className="text-sm text-emerald-600 hover:text-emerald-700 font-medium whitespace-nowrap"
              >
                Ver dieta &rarr;
              </Link>
            </div>
          </div>
        )}
      </div>

      {/* ── Datos Demográficos ─────────────────────────────────────────── */}
      <div className="bg-white rounded-2xl p-6 shadow-sm border border-slate-100">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-slate-800">
            Datos Demográficos
          </h2>
          {!editingData && (
            <button
              type="button"
              onClick={() => {
                setDataFormKey((k) => k + 1)
                setEditBirthDate(patient.birth_date?.slice(0, 10) ?? "")
                setEditCountry(patient.country ?? "")
                setEditCity(patient.city ?? "")
                setEditingData(true)
              }}
              className="text-sm text-emerald-600 hover:text-emerald-700 font-medium"
            >
              Editar
            </button>
          )}
        </div>

        {editingData ? (
          <form key={dataFormKey} onSubmit={onSaveData} className="space-y-4 max-w-lg">
            <div>
              <label className="block text-xs font-medium text-slate-500 mb-1">
                Nombre
              </label>
              <input
                name="first_name"
                defaultValue={patient.first_name}
                className={INPUT_CLASSES}
                required
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-500 mb-1">
                Apellido
              </label>
              <input
                name="last_name"
                defaultValue={patient.last_name}
                className={INPUT_CLASSES}
                required
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-500 mb-1">
                Fecha de nacimiento
              </label>
              <DatePicker
                value={editBirthDate}
                onChange={setEditBirthDate}
                name="birth_date"
                placeholder="DD/MM/AAAA"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-500 mb-1">
                Sexo
              </label>
              <select
                name="sex"
                defaultValue={patient.sex ?? ""}
                className={SELECT_CLASSES}
              >
                <option value="">— Seleccionar —</option>
                <option value="Masculino">Masculino</option>
                <option value="Femenino">Femenino</option>
                <option value="Otro">Otro</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-500 mb-1">
                Correo electrónico
              </label>
              <input
                name="email"
                type="email"
                defaultValue={patient.email ?? ""}
                className={INPUT_CLASSES}
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-500 mb-1">
                WhatsApp
              </label>
              <input
                name="whatsapp"
                defaultValue={patient.whatsapp ?? ""}
                className={INPUT_CLASSES}
              />
            </div>

            <LocationSelector
              country={editCountry}
              city={editCity}
              onCountryChange={(c) => { setEditCountry(c); setEditCity("") }}
              onCityChange={setEditCity}
            />

            <div className="flex flex-wrap gap-4">
              <label className="flex items-center gap-2 text-sm text-slate-700 cursor-pointer">
                <input
                  type="checkbox"
                  name="is_active"
                  defaultChecked={patient.is_active}
                  className="rounded border-slate-300 text-emerald-600 focus:ring-emerald-500/20"
                />
                Activo
              </label>
              <label className="flex items-center gap-2 text-sm text-slate-700 cursor-pointer">
                <input
                  type="checkbox"
                  name="is_archived"
                  defaultChecked={patient.is_archived}
                  className="rounded border-slate-300 text-emerald-600 focus:ring-emerald-500/20"
                />
                Archivado
              </label>
            </div>

            <div className="flex gap-2 pt-2">
              <button
                type="submit"
                className="px-4 py-2.5 rounded-xl text-sm font-medium bg-emerald-600 text-white hover:bg-emerald-700 transition-colors shadow-sm"
              >
                Guardar
              </button>
              <button
                type="button"
                onClick={() => setEditingData(false)}
                className="px-4 py-2.5 rounded-xl text-sm font-medium bg-white border border-slate-200 text-slate-700 hover:bg-slate-50 transition-colors"
              >
                Cancelar
              </button>
            </div>
          </form>
        ) : (
          renderDataView(patient)
        )}
      </div>

      {/* ── Perfil Clínico ────────────────────────────────────────────── */}
      <div className="bg-white rounded-2xl p-6 shadow-sm border border-slate-100">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-slate-800">
            Perfil Clínico
          </h2>
          {!editingProfile && (
            <button
              type="button"
              onClick={() => {
                setProfileFormKey((k) => k + 1)
                setEditMedications(profile?.medications ?? "")
                setEditingProfile(true)
              }}
              className="text-sm text-emerald-600 hover:text-emerald-700 font-medium"
            >
              Editar perfil
            </button>
          )}
        </div>

        {/* Pendiente de evaluacion */}
        {profile && profile.completed_by_patient && !profile.completed_at && (
          <div className="mb-4 rounded-xl bg-amber-50 border border-amber-200 px-4 py-3 flex items-center gap-2">
            <span className="text-amber-600 text-sm shrink-0">⚠️</span>
            <p className="text-sm text-amber-700">Pendiente de evaluación clínica — completa los datos del paciente tomados en consulta</p>
          </div>
        )}

        {editingProfile ? (
          <form
            key={profileFormKey}
            onSubmit={onSaveProfile}
            className="space-y-6 max-w-2xl"
          >
            {/* Historial Clinico */}
            <div className="p-4 bg-slate-50 rounded-xl">
              <h4 className="text-sm font-semibold text-emerald-600 uppercase tracking-wider mb-3">Historial Clínico</h4>
              <div className="space-y-4">
                {/* Objetivo */}
                <div>
                  <label className="block text-xs font-medium text-slate-500 mb-1">
                    Objetivo
                  </label>
                  <select
                    name="objective"
                    defaultValue={profile?.objective ?? ""}
                    className={SELECT_CLASSES}
                  >
                    {OBJECTIVE_OPTIONS.map((o) => (
                      <option key={o.value} value={o.value}>
                        {o.label}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Enfermedades */}
                <div>
                  <label className="block text-xs font-medium text-slate-500 mb-1">
                    Enfermedades
                  </label>
                  <PillSelect
                    options={DISEASE_OPTIONS}
                    selected={diseasesPills}
                    otherText={diseasesOther}
                    onChange={setDiseasesPills}
                    onOtherChange={setDiseasesOther}
                  />
                </div>

                {/* Medicamentos */}
                <OptionalField
                  label="Medicamentos"
                  value={editMedications}
                  onChange={setEditMedications}
                  name="medications"
                  placeholder="Ej. Metformina 500mg, Losartán 50mg"
                />

                {/* Alergias */}
                <div>
                  <label className="block text-xs font-medium text-slate-500 mb-1">
                    Alergias alimentarias
                  </label>
                  <PillSelect
                    options={ALLERGY_OPTIONS}
                    selected={allergiesPills}
                    otherText={allergiesOther}
                    onChange={setAllergiesPills}
                    onOtherChange={setAllergiesOther}
                  />
                </div>

                {/* Alimentos evitados */}
                <div>
                  <label className="block text-xs font-medium text-slate-500 mb-1">
                    Alimentos evitados
                  </label>
                  <PillSelect
                    options={FOODS_AVOIDED_OPTIONS}
                    selected={foodsAvoidedPills}
                    otherText={foodsAvoidedOther}
                    onChange={setFoodsAvoidedPills}
                    onOtherChange={setFoodsAvoidedOther}
                  />
                </div>

                {/* Historial médico */}
                <div>
                  <label className="block text-xs font-medium text-slate-500 mb-1">
                    Historial médico
                  </label>
                  <textarea
                    name="medical_history"
                    rows={2}
                    defaultValue={profile?.medical_history ?? ""}
                    className={INPUT_CLASSES}
                  />
                </div>
              </div>
            </div>

            {/* Perfil Nutricional */}
            <div className="p-4 bg-slate-50 rounded-xl">
              <h4 className="text-sm font-semibold text-emerald-600 uppercase tracking-wider mb-3">Perfil Nutricional</h4>
              <div className="space-y-4">
                {/* Patrón alimentario */}
                <div>
                  <label className="block text-xs font-medium text-slate-500 mb-1">
                    Patrón alimentario
                  </label>
                  <PillSelect
                    options={DIETARY_STYLE_OPTIONS}
                    selected={dietaryPills}
                    otherText={dietaryOther}
                    onChange={setDietaryPills}
                    onOtherChange={setDietaryOther}
                  />
                </div>

                {/* Alimentos que SÍ le gustan */}
                <div>
                  <label className="block text-xs font-medium text-slate-500 mb-1">
                    Alimentos que SÍ le gustan
                  </label>
                  <PillSelect
                    options={FOOD_PREFERENCES_OPTIONS}
                    selected={foodPrefsPills}
                    otherText={foodPrefsOther}
                    onChange={setFoodPrefsPills}
                    onOtherChange={setFoodPrefsOther}
                  />
                </div>

                {/* Agua */}
                <div>
                  <label className="block text-xs font-medium text-slate-500 mb-1">
                    Consumo de agua (L/día)
                  </label>
                  <input
                    name="water_intake_liters"
                    type="number"
                    step="0.1"
                    min="0"
                    max="10"
                    defaultValue={profile?.water_intake_liters ?? ""}
                    className={INPUT_CLASSES}
                  />
                </div>
              </div>
            </div>

            {/* Estilo de Vida */}
            <div className="p-4 bg-slate-50 rounded-xl">
              <h4 className="text-sm font-semibold text-emerald-600 uppercase tracking-wider mb-3">Estilo de Vida</h4>
              <div className="space-y-4">
                {/* Nivel de actividad */}
                <div>
                  <label className="block text-xs font-medium text-slate-500 mb-1">
                    Nivel de actividad
                  </label>
                  <select
                    name="activity_level"
                    defaultValue={profile?.activity_level ?? ""}
                    className={SELECT_CLASSES}
                  >
                    <option value="">— Seleccionar —</option>
                    <option value="Sedentario">Sedentario — sin ejercicio</option>
                    <option value="Ligero">Ligero — 1-2 días/semana</option>
                    <option value="Moderado">Moderado — 3-4 días/semana</option>
                    <option value="Alto">Alto — 5-6 días/semana</option>
                    <option value="Muy alto">Muy alto — atleta / entrenamiento diario</option>
                  </select>
                </div>

                {/* Estrés */}
                <div>
                  <label className="block text-xs font-medium text-slate-500 mb-1">
                    Nivel de estrés
                  </label>
                  <select
                    name="stress_level"
                    defaultValue={profile?.stress_level ?? ""}
                    className={SELECT_CLASSES}
                  >
                    <option value="">— Seleccionar —</option>
                    <option value="1">1 — Muy bajo</option>
                    <option value="2">2 — Bajo</option>
                    <option value="3">3 — Moderado</option>
                    <option value="4">4 — Alto</option>
                    <option value="5">5 — Muy alto</option>
                  </select>
                </div>

                {/* Calidad del sueño */}
                <div>
                  <label className="block text-xs font-medium text-slate-500 mb-1">
                    Calidad del sueño
                  </label>
                  <select
                    name="sleep_quality"
                    defaultValue={profile?.sleep_quality ?? ""}
                    className={SELECT_CLASSES}
                  >
                    <option value="">— Seleccionar —</option>
                    <option value="1">1 — Muy mala</option>
                    <option value="2">2 — Mala</option>
                    <option value="3">3 — Regular</option>
                    <option value="4">4 — Buena</option>
                    <option value="5">5 — Excelente</option>
                  </select>
                </div>

                {/* Horas de sueño */}
                <div>
                  <label className="block text-xs font-medium text-slate-500 mb-1">
                    Horas de sueño por noche
                  </label>
                  <input
                    name="sleep_hours"
                    type="number"
                    step="0.5"
                    min="3"
                    max="12"
                    defaultValue={profile?.sleep_hours ?? ""}
                    className={INPUT_CLASSES}
                  />
                </div>

                {/* Presupuesto */}
                <div>
                  <label className="block text-xs font-medium text-slate-500 mb-1">
                    Presupuesto mensual estimado
                  </label>
                  <select
                    name="budget_level"
                    defaultValue={profile?.budget_level ?? ""}
                    className={SELECT_CLASSES}
                  >
                    <option value="">— Seleccionar —</option>
                    <option value="Bajo">Bajo</option>
                    <option value="Medio">Medio</option>
                    <option value="Medio-alto">Medio-alto</option>
                    <option value="Alto">Alto</option>
                  </select>
                </div>

                {/* Adherencia */}
                <div>
                  <label className="block text-xs font-medium text-slate-500 mb-1">
                    Disposición al cambio
                  </label>
                  <select
                    name="adherence_level"
                    defaultValue={profile?.adherence_level ?? ""}
                    className={SELECT_CLASSES}
                  >
                    <option value="">— Seleccionar —</option>
                    <option value="1">1 — Muy baja</option>
                    <option value="2">2 — Baja</option>
                    <option value="3">3 — Moderada</option>
                    <option value="4">4 — Alta</option>
                    <option value="5">5 — Muy alta</option>
                  </select>
                </div>

                {/* Tipo de ejercicio */}
                <div>
                  <label className="block text-xs font-medium text-slate-500 mb-1">
                    Tipo de ejercicio
                  </label>
                  <PillSelect
                    options={EXERCISE_TYPE_OPTIONS}
                    selected={exerciseTypePills}
                    otherText={exerciseTypeOther}
                    onChange={setExerciseTypePills}
                    onOtherChange={setExerciseTypeOther}
                  />
                </div>

                {/* Notas adicionales */}
                <div>
                  <label className="block text-xs font-medium text-slate-500 mb-1">
                    Notas adicionales
                  </label>
                  <textarea
                    name="extra_notes"
                    rows={2}
                    defaultValue={profile?.extra_notes ?? ""}
                    className={INPUT_CLASSES}
                  />
                </div>
              </div>
            </div>

            <div className="flex gap-2 pt-2">
              <button
                type="submit"
                className="px-4 py-2.5 rounded-xl text-sm font-medium bg-emerald-600 text-white hover:bg-emerald-700 transition-colors shadow-sm"
              >
                Guardar perfil
              </button>
              <button
                type="button"
                onClick={() => setEditingProfile(false)}
                className="px-4 py-2.5 rounded-xl text-sm font-medium bg-white border border-slate-200 text-slate-700 hover:bg-slate-50 transition-colors"
              >
                Cancelar
              </button>
            </div>
          </form>
        ) : (
          <div className="space-y-6">
            {/* Historial Clínico */}
            <div className="p-4 bg-slate-50 rounded-xl">
              <h4 className="text-sm font-semibold text-emerald-600 uppercase tracking-wider mb-3">Historial Clínico</h4>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-8 gap-y-3">
                {renderProfileField("Objetivo", OBJECTIVE_OPTIONS.find(o => o.value === profile?.objective)?.label || profile?.objective)}
                <div>
                  <span className="text-xs text-slate-500">Enfermedades</span>
                  {renderMultiTag(profile?.diseases)}
                </div>
                {renderProfileField("Medicamentos", profile?.medications)}
                <div>
                  <span className="text-xs text-slate-500">Alergias alimentarias</span>
                  {renderMultiTag(profile?.food_allergies)}
                </div>
                <div>
                  <span className="text-xs text-slate-500">Alimentos evitados</span>
                  {renderMultiTag(profile?.foods_avoided)}
                </div>
                {renderProfileField("Historial médico", profile?.medical_history)}
              </div>
            </div>

            {/* Perfil Nutricional */}
            <div className="p-4 bg-slate-50 rounded-xl">
              <h4 className="text-sm font-semibold text-emerald-600 uppercase tracking-wider mb-3">Perfil Nutricional</h4>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-8 gap-y-3">
                <div>
                  <span className="text-xs text-slate-500">Alimentos que SÍ le gustan</span>
                  {renderMultiTag(profile?.food_preferences) || <span className="text-sm text-slate-400">—</span>}
                </div>
                <div>
                  <span className="text-xs text-slate-500">Patrón alimentario</span>
                  {renderMultiTag(profile?.dietary_style)}
                </div>
                {renderProfileField(
                  "Consumo de agua",
                  profile?.water_intake_liters != null
                    ? `${profile.water_intake_liters} L/día`
                    : null
                )}
              </div>
            </div>

            {/* Estilo de Vida */}
            <div className="p-4 bg-slate-50 rounded-xl">
              <h4 className="text-sm font-semibold text-emerald-600 uppercase tracking-wider mb-3">Estilo de Vida</h4>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-8 gap-y-3">
                {renderProfileField("Nivel de actividad", profile?.activity_level)}
                {renderProfileField(
                  "Estrés",
                  profile?.stress_level != null ? `${profile.stress_level}/5` : null
                )}
                {renderProfileField(
                  "Calidad del sueño",
                  profile?.sleep_quality != null ? `${profile.sleep_quality}/5` : null
                )}
                {renderProfileField(
                  "Horas de sueño",
                  profile?.sleep_hours != null ? `${profile.sleep_hours} h` : null
                )}
                {renderProfileField("Presupuesto", profile?.budget_level)}
                {renderProfileField(
                  "Disposición al cambio",
                  profile?.adherence_level != null ? `${profile.adherence_level}/5` : null
                )}
                <div>
                  <span className="text-xs text-slate-500">Tipo de ejercicio</span>
                  {renderMultiTag(profile?.exercise_type)}
                </div>
                {renderProfileField("Notas adicionales", profile?.extra_notes)}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* ── Historial de Métricas ──────────────────────────────────────── */}
      <div className="bg-white rounded-2xl p-6 shadow-sm border border-slate-100">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-slate-800">
            Historial de Métricas
          </h2>
          <button
            type="button"
            onClick={() => { setShowMetricForm((v) => !v); if (showMetricForm) resetMetricForm() }}
            className="text-sm text-emerald-600 hover:text-emerald-700 font-medium"
          >
            {showMetricForm ? "Cancelar" : "+ Registrar Métricas"}
          </button>
        </div>

        {showMetricForm && (
          <form
            onSubmit={onAddMetric}
            className="mb-6 p-4 bg-slate-50 rounded-xl space-y-3 max-w-md"
          >
            <p className="text-sm font-medium text-slate-700">
              {editingMetricId != null ? "Editar medición" : "Nueva medición"}
            </p>
            <div>
              <label className="block text-xs font-medium text-slate-500 mb-1">
                Peso
              </label>
              <WeightInput
                valueKg={mWeight}
                onChangeKg={setMWeight}
                placeholder="ej. 65.0"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-500 mb-1">
                Altura
              </label>
              <HeightInput
                valueCm={mHeight}
                onChangeCm={setMHeight}
                placeholder="ej. 162"
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-slate-500 mb-1">Cuello (cm)</label>
                <input type="number" min="0" value={mNeck} onChange={(e) => setMNeck(e.target.value)} className={INPUT_CLASSES} placeholder="ej. 36" />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-500 mb-1">Pecho (cm)</label>
                <input type="number" min="0" value={mChest} onChange={(e) => setMChest(e.target.value)} className={INPUT_CLASSES} placeholder="ej. 95" />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-500 mb-1">Cintura (cm)</label>
                <input type="number" min="0" value={mWaist} onChange={(e) => setMWaist(e.target.value)} className={INPUT_CLASSES} placeholder="ej. 80" />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-500 mb-1">Cadera (cm)</label>
                <input type="number" min="0" value={mHip} onChange={(e) => setMHip(e.target.value)} className={INPUT_CLASSES} placeholder="ej. 100" />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-500 mb-1">Pierna (cm)</label>
                <input type="number" min="0" value={mLeg} onChange={(e) => setMLeg(e.target.value)} className={INPUT_CLASSES} placeholder="ej. 55" />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-500 mb-1">Pantorrilla (cm)</label>
                <input type="number" min="0" value={mCalf} onChange={(e) => setMCalf(e.target.value)} className={INPUT_CLASSES} placeholder="ej. 35" />
              </div>
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-500 mb-1">
                Notas
              </label>
              <input
                value={mNotes}
                onChange={(e) => setMNotes(e.target.value)}
                className={INPUT_CLASSES}
                placeholder="Opcional"
              />
            </div>
            <button
              type="submit"
              className="px-4 py-2.5 rounded-xl text-sm font-medium bg-emerald-600 text-white hover:bg-emerald-700 transition-colors shadow-sm"
            >
              Registrar
            </button>
          </form>
        )}

        {/* Sparkline principal */}
        {metrics.filter((m) => m.weight_kg != null).length > 1 && (
          <div className="mb-4">
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
              Tendencia de peso
            </p>
            <WeightSparkline metrics={metrics} />
          </div>
        )}

        {/* Tabla */}
        {metrics.length === 0 ? (
          <div className="text-center py-8">
            <p className="text-sm text-slate-400">Sin métricas registradas</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200">
                  <th className="text-left py-2.5 px-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">
                    Fecha
                  </th>
                  <th className="text-left py-2.5 px-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">
                    Peso (kg)
                  </th>
                  <th className="text-left py-2.5 px-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">
                    Altura (cm)
                  </th>
                  <th className="text-left py-2.5 px-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">
                    IMC
                  </th>
                  <th className="text-left py-2.5 px-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">
                    Fuente
                  </th>
                  <th className="text-right py-2.5 px-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">

                  </th>
                </tr>
              </thead>
              <tbody>
                {[...metrics]
                  .sort(
                    (a, b) =>
                      new Date(b.recorded_at).getTime() -
                      new Date(a.recorded_at).getTime()
                  )
                  .map((m) => {
                    const imc = calcIMC(m.weight_kg, m.height_cm)
                    return (
                      <tr
                        key={m.id}
                        className="border-b border-slate-100 hover:bg-slate-50 transition-colors"
                      >
                        <td className="py-2.5 px-3 text-slate-600 whitespace-nowrap">
                          {formatDate(m.recorded_at)}
                        </td>
                        <td className="py-2.5 px-3 text-slate-800 font-medium">
                          {m.weight_kg ?? "—"}
                        </td>
                        <td className="py-2.5 px-3 text-slate-800">
                          {m.height_cm ?? "—"}
                        </td>
                        <td className="py-2.5 px-3 text-slate-600">
                          {imc != null ? imc : "—"}
                        </td>
                        <td className="py-2.5 px-3 text-slate-500 capitalize">
                          {m.source}
                        </td>
                        <td className="py-2.5 px-3 text-right">
                          <button
                            type="button"
                            onClick={() => populateMetricForm(m)}
                            className="text-xs text-emerald-600 hover:text-emerald-700 font-medium"
                          >
                            Editar
                          </button>
                        </td>
                      </tr>
                    )
                  })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ── Dietas ──────────────────────────────────────────────────────── */}
      <div className="bg-white rounded-2xl p-6 shadow-sm border border-slate-100">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-slate-800">Dietas</h2>
          <Link
            to={`/diets/new?patient=${patientId}`}
            className="text-sm text-emerald-600 hover:text-emerald-700 font-medium"
          >
            + Nueva Dieta
          </Link>
        </div>

        {summary?.latest_diet ? (
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 p-4 bg-emerald-50 rounded-xl">
            <div className="flex items-center gap-3">
              <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-100 text-emerald-700">
                Dieta activa
              </span>
              <div className="text-sm text-slate-600">
                Plan nutricional &middot; Creada el{" "}
                {formatDate(summary.latest_diet.created_at)}
                {summary.latest_diet.plan_duration_days != null &&
                  summary.latest_diet.plan_duration_days > 0 &&
                  ` · ${summary.latest_diet.plan_duration_days} días`}
              </div>
            </div>
            <Link
              to={`/diets/${summary.latest_diet.id}`}
              className="text-sm text-emerald-600 hover:text-emerald-700 font-medium whitespace-nowrap"
            >
              Ver dieta &rarr;
            </Link>
          </div>
        ) : (
          <div className="text-center py-8">
            <p className="text-sm text-slate-400">Sin dietas generadas</p>
          </div>
        )}

        <div className="mt-3 text-right">
          <Link
            to={`/diets?patient=${patientId}`}
            className="text-sm text-slate-500 hover:text-emerald-600 transition-colors"
          >
            Ver todas las dietas &rarr;
          </Link>
        </div>
      </div>
    </div>

      <ConfirmModal
        open={confirmModal.open}
        title="Revisar cambios"
        description="Confirma los cambios que realizaste en el perfil del paciente."
        changes={confirmModal.changes}
        onConfirm={confirmModal.onConfirm}
        onEdit={() => setConfirmModal({ open: false, changes: [], onConfirm: () => {} })}
        confirmLabel="Confirmar cambios"
        editLabel="Continuar editando"
        loading={confirmLoading}
      />
    </>
  )
}
