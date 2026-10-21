type Props = {
  kcal: string; protein: string; carbs: string; fat: string
  onChange: (field: string, value: string) => void
  onNext: () => void
}

export default function ManualTargets({ kcal, protein, carbs, fat, onChange }: Props) {
  const fields = [
    { field: "manualKcal", label: "Calorías diarias (kcal)", value: kcal, placeholder: "1800" },
    { field: "manualProteinG", label: "Proteína (g/día)", value: protein, placeholder: "135" },
    { field: "manualCarbsG", label: "Carbohidratos (g/día)", value: carbs, placeholder: "180" },
    { field: "manualFatG", label: "Grasas (g/día)", value: fat, placeholder: "60" },
  ]

  return (
    <div className="space-y-3">
      <p className="text-sm font-medium text-gray-700">Define objetivos manuales. Deja en blanco lo que no quieras fijar.</p>
      {fields.map((f) => (
        <div key={f.field}>
          <label className="mb-1 block text-sm text-gray-600">{f.label}</label>
          <input
            type="number"
            min={0}
            value={f.value}
            onChange={(e) => onChange(f.field, e.target.value)}
            placeholder={f.placeholder}
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
          />
        </div>
      ))}
    </div>
  )
}
