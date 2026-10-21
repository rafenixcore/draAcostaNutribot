const ADJUSTMENTS: { key: string; label: string }[] = [
  { key: "more_prot", label: "Más proteína" },
  { key: "less_cal", label: "Menos calorías" },
  { key: "more_cal", label: "Más calorías" },
  { key: "mediter", label: "Estilo mediterráneo" },
  { key: "low_carb", label: "Menos hidratos" },
  { key: "snack_add", label: "Incluir snack" },
  { key: "snack_rm", label: "Quitar snack" },
  { key: "less_ultra", label: "Menos ultraprocesados" },
]

type Props = { onSelect: (key: string, label: string) => void; loading: boolean }

export default function QuickAdjustMenu({ onSelect, loading }: Props) {
  return (
    <div className="space-y-2">
      <p className="text-sm font-medium text-gray-700">⚡ Ajuste Rápido</p>
      <div className="grid grid-cols-2 gap-2">
        {ADJUSTMENTS.map((adj) => (
          <button
            key={adj.key}
            type="button"
            disabled={loading}
            onClick={() => onSelect(adj.key, adj.label)}
            className="rounded-lg border border-gray-200 bg-white px-3 py-2 text-left text-sm text-gray-600 hover:bg-emerald-50 hover:border-emerald-300 transition-colors disabled:opacity-50"
          >
            {adj.label}
          </button>
        ))}
      </div>
    </div>
  )
}
