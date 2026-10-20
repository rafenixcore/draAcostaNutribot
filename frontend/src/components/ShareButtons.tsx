import { useState } from "react"

type ShareButtonsProps = {
  url: string
  patientName: string
  type: "register" | "update"
}

const MESSAGES: Record<
  "register" | "update",
  { wa: string; emailSubject: string; emailBody: string }
> = {
  register: {
    wa: "Hola%2C%20la%20Dra.%20Acosta%20te%20invita%20a%20completar%20tu%20ficha%20nutricional%20para%20tu%20plan%20personalizado%3A",
    emailSubject: "Completa tu ficha nutricional - Dra. Acosta",
    emailBody:
      "Hola,%0D%0A%0D%0ALa Dra. Acosta te comparte este link para que completes tu información nutricional y así preparar tu plan personalizado:%0D%0A%0D%0A",
  },
  update: {
    wa: "Hola%2C%20la%20Dra.%20Acosta%20te%20comparte%20este%20link%20para%20actualizar%20tus%20datos%20nutricionales%3A",
    emailSubject: "Actualiza tus datos nutricionales - Dra. Acosta",
    emailBody:
      "Hola,%0D%0A%0D%0ALa Dra. Acosta te comparte este link para que actualices tus datos (peso, medidas, hábitos) y ajustar tu plan nutricional:%0D%0A%0D%0A",
  },
}

export default function ShareButtons({ url, type }: ShareButtonsProps) {
  const [copied, setCopied] = useState(false)
  const msg = MESSAGES[type]

  const waLink = `https://wa.me/?text=${msg.wa}%0A%0A${encodeURIComponent(url)}`
  const emailLink = `mailto:?subject=${encodeURIComponent(msg.emailSubject)}&body=${msg.emailBody}${encodeURIComponent(url)}`

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(url)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      const input = document.createElement("input")
      input.value = url
      document.body.appendChild(input)
      input.select()
      document.execCommand("copy")
      document.body.removeChild(input)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  return (
    <div className="space-y-3">
      {/* URL display */}
      <div className="flex items-center gap-2 rounded-lg border border-gray-200 bg-gray-50 px-3 py-2">
        <input
          type="text"
          readOnly
          value={url}
          className="flex-1 bg-transparent text-sm text-gray-600 truncate outline-none"
        />
        <button
          type="button"
          onClick={handleCopy}
          className="shrink-0 rounded-md px-2 py-1 text-xs font-medium text-gray-500 hover:bg-gray-200 transition-colors"
        >
          {copied ? "✓ Copiado" : "📋 Copiar"}
        </button>
      </div>

      {/* Share buttons */}
      <div className="flex gap-2">
        <a
          href={waLink}
          target="_blank"
          rel="noopener noreferrer"
          className="flex flex-1 items-center justify-center gap-2 rounded-lg bg-green-500 px-4 py-2.5 text-sm font-medium text-white hover:bg-green-600 transition-colors shadow-sm"
        >
          📱 WhatsApp
        </a>
        <a
          href={emailLink}
          className="flex flex-1 items-center justify-center gap-2 rounded-lg bg-gray-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-gray-700 transition-colors shadow-sm"
        >
          📧 Correo
        </a>
      </div>
    </div>
  )
}
