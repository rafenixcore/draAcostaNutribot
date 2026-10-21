import { useReducer, useState, useCallback } from "react"
import { useNavigate, useSearchParams } from "react-router-dom"
import {
  wizardReducer,
  initialWizardState,
  NEXT_FEATURES,
  type WizardStep,
} from "../types"
import type { DietGenerateRequest, DietStrategyMode, MealsPerDay, Patient } from "../types"
import { useDietGeneration } from "../hooks/useDietGeneration"
import { getPatientSummary } from "../services/api"
import { useToast } from "../context/ToastContext"
import WizardContainer from "../components/wizard/WizardContainer"
import PatientSearchInput from "../components/wizard/PatientSearchInput"
import WizardNoteStep from "../components/wizard/WizardNoteStep"
import DurationPresets from "../components/wizard/DurationPresets"
import MealCountSelector from "../components/wizard/MealCountSelector"
import StrategyModeCards from "../components/wizard/StrategyModeCards"
import DietStyleCards from "../components/wizard/DietStyleCards"
import MacroPreferences from "../components/wizard/MacroPreferences"
import ManualTargets from "../components/wizard/ManualTargets"
import WizardConfirm from "../components/wizard/WizardConfirm"
import WizardNavigation from "../components/wizard/WizardNavigation"
import DietPreviewPanel from "../components/diet/DietPreviewPanel"
import GenerationOverlay from "../components/ui/GenerationOverlay"

export default function DietWizard() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const patientParam = searchParams.get("patient")
  const initialPatientId = patientParam ? Number(patientParam) : undefined

  const [state, dispatch] = useReducer(
    wizardReducer,
    initialWizardState(initialPatientId),
  )
  const [step, setStep] = useState<WizardStep>(initialPatientId ? "note" : "patient")
  const { generate } = useDietGeneration()
  const { addToast } = useToast()

  const [profileChecking, setProfileChecking] = useState(false)
  const [profileBlocked, setProfileBlocked] = useState<Patient | null>(null)
  const [generating, setGenerating] = useState(false)

  const handlePatientSelect = useCallback(async (patient: Patient) => {
    dispatch({ type: "SET_FIELD", field: "patientId", value: patient.id })
    dispatch({
      type: "SET_FIELD",
      field: "patientName",
      value: `${patient.first_name} ${patient.last_name}`,
    })

    setProfileChecking(true)
    setProfileBlocked(null)

    try {
      const summary = await getPatientSummary(patient.id)
      if (summary.profile_flags.is_profile_complete) {
        setStep("note")
      } else {
        setProfileBlocked(patient)
      }
    } catch {
      setStep("note")
    } finally {
      setProfileChecking(false)
    }
  }, [])

  const handleClearPatient = useCallback(() => {
    dispatch({ type: "SET_FIELD", field: "patientId", value: null })
    dispatch({ type: "SET_FIELD", field: "patientName", value: "" })
    setProfileBlocked(null)
  }, [])

  const handleSendForm = useCallback(() => {
    addToast("Funcion de envio de formulario proximamente", "info")
  }, [addToast])

  const buildBody = useCallback((): DietGenerateRequest => {
    const body: DietGenerateRequest = {
      patient_id: state.patientId!,
      duration_days: state.durationDays,
      meals_per_day: state.mealsPerDay as MealsPerDay,
      strategy_mode: state.strategyMode as DietStrategyMode,
    }
    if (state.doctorInstruction.trim()) {
      body.doctor_instruction = state.doctorInstruction.trim()
    }
    if (state.strategyMode === "guided") {
      if (state.dietStyle) body.diet_style = state.dietStyle
      const macro: Record<string, string> = {}
      if (state.macroProtein) macro.protein = state.macroProtein
      if (state.macroCarbs) macro.carbs = state.macroCarbs
      if (state.macroFat) macro.fat = state.macroFat
      if (Object.keys(macro).length)
        body.macro_mode = macro as DietGenerateRequest["macro_mode"]
    }
    if (state.strategyMode === "manual") {
      const mt: Record<string, number> = {}
      if (state.manualKcal) mt.daily_calories = Number(state.manualKcal)
      if (state.manualProteinG) mt.protein_g = Number(state.manualProteinG)
      if (state.manualCarbsG) mt.carbs_g = Number(state.manualCarbsG)
      if (state.manualFatG) mt.fat_g = Number(state.manualFatG)
      if (Object.keys(mt).length)
        body.manual_targets = mt as DietGenerateRequest["manual_targets"]
    }
    return body
  }, [state])

  const handleGenerate = useCallback(async () => {
    setGenerating(true)
    try {
      const body = buildBody()
      const result = await generate.mutateAsync(body)
      dispatch({ type: "SET_DIET", diet: result })
      navigate(`/diets/${result.id}`, { replace: true })
    } catch (err) {
      setGenerating(false)
      addToast(err instanceof Error ? err.message : "Error al generar dieta", "error")
    }
  }, [buildBody, generate, navigate, addToast])

  const stepOrder: WizardStep[] = NEXT_FEATURES.advancedStrategies
    ? ["patient", "note", "duration", "meals", "strategy", "confirm"]
    : ["patient", "note", "duration", "meals", "confirm"]
  const currentIndex = stepOrder.indexOf(step)

  const goNext = useCallback(() => {
    if (currentIndex < stepOrder.length - 1) {
      const next = stepOrder[currentIndex + 1]
      if (NEXT_FEATURES.advancedStrategies && next === "confirm" && state.strategyMode === "guided" && !state.dietStyle) {
        setStep("guided_style")
      } else if (NEXT_FEATURES.advancedStrategies && next === "confirm" && state.strategyMode === "guided" && state.dietStyle) {
        setStep("guided_macros")
      } else if (NEXT_FEATURES.advancedStrategies && next === "confirm" && state.strategyMode === "manual") {
        setStep("manual_targets")
      } else {
        setStep(next)
      }
    }
  }, [currentIndex, state.strategyMode, state.dietStyle])

  const goBack = useCallback(() => {
    if (currentIndex > 0) {
      const prev = stepOrder[currentIndex - 1]
      if (NEXT_FEATURES.advancedStrategies && prev === "strategy" && state.strategyMode === "guided") {
        setStep("guided_macros")
      } else if (NEXT_FEATURES.advancedStrategies && prev === "strategy" && state.strategyMode === "manual") {
        setStep("manual_targets")
      } else {
        setStep(prev)
      }
    }
  }, [currentIndex, state.strategyMode])

  const getTitle = (): string => {
    if (state.isRegeneration) return "Regenerar Dieta"
    return "Nueva Dieta"
  }

  const renderStep = () => {
    switch (step) {
      case "patient":
        if (profileChecking) {
          return (
            <div className="flex items-center justify-center py-8">
              <div className="h-6 w-6 animate-spin rounded-full border-b-2 border-emerald-600" />
              <span className="ml-3 text-sm text-slate-500">Verificando perfil...</span>
            </div>
          )
        }
        if (profileBlocked) {
          return (
            <div className="rounded-xl border border-amber-200 bg-amber-50 p-4">
              <p className="text-sm font-medium text-amber-800">
                Este paciente necesita completar su perfil antes de generar una dieta. El perfil
                debe incluir: fecha de nacimiento, sexo, pais, ciudad, objetivo, alergias, alimentos
                a evitar, y metricas de peso y altura.
              </p>
              <div className="mt-4 flex gap-3">
                <button
                  type="button"
                  onClick={handleSendForm}
                  className="rounded-lg bg-amber-600 px-4 py-2 text-sm font-medium text-white hover:bg-amber-700 transition-colors cursor-pointer"
                >
                  Enviar formulario
                </button>
                <button
                  type="button"
                  onClick={handleClearPatient}
                  className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 transition-colors cursor-pointer"
                >
                  Seleccionar otro paciente
                </button>
              </div>
            </div>
          )
        }
        return <PatientSearchInput onSelect={handlePatientSelect} />
      case "note":
        return (
          <WizardNoteStep
            value={state.doctorInstruction}
            onChange={(v) => dispatch({ type: "SET_FIELD", field: "doctorInstruction", value: v })}
            onSkip={() => setStep("duration")}
          />
        )
      case "duration":
        return (
          <DurationPresets
            value={state.durationDays}
            onChange={(v) => dispatch({ type: "SET_FIELD", field: "durationDays", value: v })}
          />
        )
      case "meals":
        return (
          <MealCountSelector
            value={state.mealsPerDay}
            onChange={(v) => dispatch({ type: "SET_FIELD", field: "mealsPerDay", value: v })}
          />
        )
      case "strategy":
        return (
          <StrategyModeCards
            value={state.strategyMode}
            onChange={(v) => dispatch({ type: "SET_FIELD", field: "strategyMode", value: v })}
          />
        )
      case "guided_style":
        return (
          <DietStyleCards
            value={state.dietStyle}
            onChange={(v) => dispatch({ type: "SET_FIELD", field: "dietStyle", value: v })}
            onNext={() => setStep("guided_macros")}
          />
        )
      case "guided_macros":
        return (
          <MacroPreferences
            protein={state.macroProtein}
            carbs={state.macroCarbs}
            fat={state.macroFat}
            onChange={(f, v) => dispatch({ type: "SET_FIELD", field: f, value: v })}
            onNext={() => setStep("confirm")}
          />
        )
      case "manual_targets":
        return (
          <ManualTargets
            kcal={state.manualKcal}
            protein={state.manualProteinG}
            carbs={state.manualCarbsG}
            fat={state.manualFatG}
            onChange={(f, v) => dispatch({ type: "SET_FIELD", field: f, value: v })}
            onNext={() => setStep("confirm")}
          />
        )
      case "confirm":
        return (
          <WizardConfirm
            state={state}
            onGenerate={handleGenerate}
            loading={generate.isPending}
          />
        )
      case "preview":
        return state.generatedDiet ? <DietPreviewPanel diet={state.generatedDiet} /> : null
      default:
        return null
    }
  }

  return (
    <WizardContainer current={step} title={getTitle()}>
      {renderStep()}

      {generate.isError && (
        <div className="mt-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
          {(generate.error as Error)?.message || "Error al generar la dieta"}
        </div>
      )}

      <WizardNavigation
        step={step}
        onBack={goBack}
        onNext={goNext}
        hideNext={["patient", "confirm", "guided_style", "guided_macros", "manual_targets"].includes(step)}
        disableNext={
          (step === "patient" && !state.patientId)
        }
      />
      <GenerationOverlay
        open={generating}
        patientName={state.patientName}
        onComplete={() => {}}
      />
    </WizardContainer>
  )
}
