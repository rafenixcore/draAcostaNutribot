import { PencilSimple, Share } from "@phosphor-icons/react"
import Button from "../ui/Button"
import QuickAdjustMenu from "./QuickAdjustMenu"
import { useState } from "react"

type Props = {
  dietId: number
  status: string
  onApprove: () => void
  onDiscard: () => void
  onQuickAdjust: (key: string, label: string) => void
  onDownloadPdf: () => void
  onSharePdf?: () => void
  onSendEmail?: () => void
  onToggleEdit?: () => void
  editing?: boolean
  loading: boolean
  emailLoading?: boolean
  patientEmail?: string | null
}

export default function DietActions({
  status,
  onApprove,
  onDiscard,
  onQuickAdjust,
  onDownloadPdf,
  onSharePdf,
  onSendEmail,
  onToggleEdit,
  editing,
  loading,
  emailLoading = false,
  patientEmail,
}: Props) {
  const [showQuickAdjust, setShowQuickAdjust] = useState(false)

  const handleSendEmail = () => {
    if (!patientEmail) {
      return  // parent handles the toast
    }
    onSendEmail?.()
  }

  if (status === "pending_approval") {
    return (
      <div className="space-y-3">
        <div className="flex gap-2">
          <Button onClick={onApprove} disabled={loading} className="flex-1">
            ✅ Aprobar
          </Button>
          <Button variant="danger" onClick={onDiscard} disabled={loading} className="flex-1">
            🗑️ Descartar
          </Button>
        </div>
        <div className="space-y-2">
          <Button variant="ghost" onClick={() => setShowQuickAdjust(!showQuickAdjust)} className="w-full text-sm">
            ⚡ {showQuickAdjust ? "Ocultar ajustes" : "Ajuste rápido"}
          </Button>
          {showQuickAdjust && <QuickAdjustMenu onSelect={onQuickAdjust} loading={loading} />}
        </div>
        <Button variant="ghost" onClick={onToggleEdit} className="w-full text-sm">
          <span className="flex items-center justify-center gap-1.5">
            <PencilSimple size={14} />
            {editing ? "Dejar de editar" : "Editar comidas"}
          </span>
        </Button>
      </div>
    )
  }

  if (status === "generated") {
    const noEmail = !patientEmail
    return (
      <div className="space-y-2">
        <Button
          onClick={handleSendEmail}
          disabled={emailLoading || noEmail}
          className="w-full"
          title={noEmail ? "El paciente no tiene correo registrado" : undefined}
        >
          {emailLoading ? "⏳ Enviando..." : "📧 Enviar por correo"}
        </Button>
        {noEmail && (
          <p className="text-xs text-amber-600 text-center">
            ⚠️ El paciente no tiene correo registrado
          </p>
        )}
        {onSharePdf && (
          <div className="md:hidden">
            <Button
              variant="secondary"
              onClick={onSharePdf}
              className="w-full border-emerald-500 text-emerald-700 hover:bg-emerald-50"
            >
              <span className="flex items-center justify-center gap-1.5">
                <Share size={14} />
                Compartir
              </span>
            </Button>
          </div>
        )}
        <div className="hidden md:block">
          <Button onClick={onDownloadPdf} className="w-full">
            📄 Descargar PDF
          </Button>
        </div>
        <Button variant="ghost" onClick={onToggleEdit} className="w-full text-sm">
          <span className="flex items-center justify-center gap-1.5">
            <PencilSimple size={14} />
            {editing ? "Dejar de editar" : "Editar comidas"}
          </span>
        </Button>
      </div>
    )
  }

  return null
}
