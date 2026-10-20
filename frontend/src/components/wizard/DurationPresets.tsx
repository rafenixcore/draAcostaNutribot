const PRESETS = [7, 14, 21, 28, 42, 56, 84, 112, 168]

type Props = { value: number; onChange: (v: number) => void }

export default function DurationPresets({ value, onChange }: Props) {
  return (
    <div className="space-y-4">
      <p className="text-sm font-medium text-gray-700">¿Cuántos días debe durar el plan?</p>
      <div className="grid grid-cols-3 gap-2">
        {PRESETS.map((d) => (
          <button
            key={d}
            type="button"
            onClick={() => onChange(d)}
            className={`rounded-lg border px-3 py-2 text-sm font-medium transition-colors
              ${value === d
                ? "border-emerald-500 bg-emerald-50 text-emerald-700 shadow-sm"
                : "border-gray-200 bg-white text-gray-600 hover:bg-gray-50"}`}
          >
            {d} días
          </button>
        ))}
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Otro (múltiplo de 7)</label>
        <input
          type="number"
          min={7}
          max={364}
          step={7}
          value={value}
          onChange={(e) => onChange(Number(e.target.value) || 7)}
          className="w-32 rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
        />
      </div>
    </div>
  )
}
