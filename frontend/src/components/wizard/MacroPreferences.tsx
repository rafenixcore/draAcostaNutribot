const LEVELS = [
  { value: "", label: "Normal" },
  { value: "low", label: "Bajo" },
  { value: "high", label: "Alto" },
]

type Props = {
  protein: string; carbs: string; fat: string
  onChange: (field: string, value: string) => void
  onNext: () => void
}

function MacroSelector({ label, field, value, onChange }: { label: string; field: string; value: string; onChange: (f: string, v: string) => void }) {
  return (
    <div>
      <p className="mb-2 text-sm font-medium text-gray-700">{label}</p>
      <div className="flex gap-2">
        {LEVELS.map((l) => (
          <button
            key={l.value}
            type="button"
            onClick={() => onChange(field, l.value)}
            className={`flex-1 rounded-lg border px-3 py-1.5 text-sm transition-colors
              ${value === l.value
                ? "border-emerald-500 bg-emerald-50 text-emerald-700"
                : "border-gray-200 bg-white text-gray-600 hover:bg-gray-50"}`}
          >
            {l.label}
          </button>
        ))}
      </div>
    </div>
  )
}

export default function MacroPreferences({ protein, carbs, fat, onChange }: Props) {
  return (
    <div className="space-y-4">
      <p className="text-sm font-medium text-gray-700">Preferencias de macronutrientes</p>
      <MacroSelector label="Proteína" field="macroProtein" value={protein} onChange={onChange} />
      <MacroSelector label="Carbohidratos" field="macroCarbs" value={carbs} onChange={onChange} />
      <MacroSelector label="Grasas" field="macroFat" value={fat} onChange={onChange} />
    </div>
  )
}
