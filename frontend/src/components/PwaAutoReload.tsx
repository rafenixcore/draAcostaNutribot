import { useEffect, useRef } from "react"
import { useRegisterSW } from "virtual:pwa-register/react"

const CHECK_INTERVAL_MS = 5 * 60 * 1000 // every 5 minutes

/** Auto-reloads the page when a PWA update is ready, no user prompt.
 *  Also polls the service worker for updates every 5 minutes so that
 *  deploys are picked up without waiting for a browser navigation. */
export default function PwaAutoReload() {
  const { needRefresh, updateServiceWorker } = useRegisterSW({
    onRegisteredSW(swUrl, registration) {
      if (!registration) return
      // Periodic check: ask the browser to look for a new service worker
      const interval = setInterval(() => {
        registration.update().catch(() => {
          /* offline or network error – ignore */
        })
      }, CHECK_INTERVAL_MS)
      // Also check immediately once the registration is confirmed
      registration.update().catch(() => {})
      // Cleanup on unmount (should never happen for the root component)
      return () => clearInterval(interval)
    },
  })

  // Prevent double-reload: once we trigger the update, skip subsequent calls
  const triggered = useRef(false)

  useEffect(() => {
    if (needRefresh && !triggered.current) {
      triggered.current = true
      // skipWaiting + reload the page so the new SW takes control immediately
      updateServiceWorker(true)
    }
  }, [needRefresh, updateServiceWorker])

  return null
}
