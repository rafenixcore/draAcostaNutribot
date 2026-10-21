import { useState, useEffect, useRef } from "react"
import { Link, Outlet, useLocation, useNavigate } from "react-router-dom"
import { AnimatePresence, motion } from "framer-motion"
import {
  House,
  Users,
  BowlFood,
  LinkSimple,
  Gear,
  SignOut,
  List,
  X,
  Trash,
  CaretRight,
  ClipboardText,
  type Icon,
} from "@phosphor-icons/react"
import { useAuth } from "../context/AuthContext"
import { getDoctorMe } from "../services/api"
import { ToastContainer } from "../components/ui/Toast"
import { Avatar } from "../components/ui/Avatar"

type DoctorMe = { full_name: string; email: string; role: string }

const NAV_ITEMS = [
  { to: "/dashboard", label: "Dashboard", icon: House },
  { to: "/patients", label: "Pacientes", icon: Users },
  { to: "/diets", label: "Dietas", icon: BowlFood },
  { to: "/formularios", label: "Formularios", icon: LinkSimple },
  { to: "/trash", label: "Papelera", icon: Trash },
]

const ADMIN_ITEMS = [
  { to: "/admin/users", label: "Usuarios", icon: Gear },
  { to: "/admin/audit-log", label: "Auditoría", icon: ClipboardText },
]

const BREADCRUMB_LABELS: Record<string, string> = {
  dashboard: "Dashboard",
  patients: "Pacientes",
  diets: "Dietas",
  "diets/new": "Nueva Dieta",
  formularios: "Formularios",
  "intake-links": "Formularios",
  "/admin": "Admin",
  "/admin/users": "Usuarios",
  "/admin/audit-log": "Auditoría",
  trash: "Papelera",
}

function getBreadcrumbs(pathname: string) {
  const segments = pathname.split("/").filter(Boolean)
  const crumbs: { label: string; to: string }[] = []
  let accumulated = ""
  for (const seg of segments) {
    if (/^\d+$/.test(seg)) continue
    accumulated += "/" + seg
    const label =
      BREADCRUMB_LABELS[accumulated] || BREADCRUMB_LABELS[seg] || seg
    crumbs.push({ label, to: accumulated })
  }
  return crumbs
}

export default function AdminLayout() {
  const [doctor, setDoctor] = useState<DoctorMe | null>(null)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [dropdownOpen, setDropdownOpen] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)
  const { logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  useEffect(() => {
    let cancelled = false
    getDoctorMe()
      .then((d) => {
        if (!cancelled)
          setDoctor({ full_name: d.full_name, email: d.email, role: d.role })
      })
      .catch(() => {
        if (cancelled) return
        logout()
        navigate("/login", { replace: true })
      })
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Close sidebar on navigation
  useEffect(() => {
    setSidebarOpen(false)
  }, [location.pathname])

  // Close dropdown on outside click
  useEffect(() => {
    if (!dropdownOpen) return
    const handler = (e: MouseEvent) => {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(e.target as Node)
      ) {
        setDropdownOpen(false)
      }
    }
    document.addEventListener("mousedown", handler)
    return () => document.removeEventListener("mousedown", handler)
  }, [dropdownOpen])

  const handleLogout = () => {
    const role = doctor?.role
    logout()
    navigate(role === "admin" || role === "super_admin" ? "/admin" : "/login", { replace: true })
  }

  const isActive = (to: string) => {
    if (to === "/dashboard") return location.pathname === "/dashboard"
    return location.pathname.startsWith(to)
  }

  const breadcrumbs = getBreadcrumbs(location.pathname)
  const isAdminUser = doctor?.role === "admin" || doctor?.role === "super_admin"
  const allNavItems = isAdminUser ? ADMIN_ITEMS : [...NAV_ITEMS]

  return (
    <div className="flex min-h-[100dvh] bg-slate-50">
      {/* Desktop sidebar */}
      <aside className="hidden md:flex md:w-60 md:flex-col md:bg-white md:border-r md:border-slate-200 md:fixed md:inset-y-0">
        <DesktopSidebar
          doctor={doctor}
          navItems={allNavItems}
          isActive={isActive}
          handleLogout={handleLogout}
        />
      </aside>

      {/* Mobile sidebar */}
      <AnimatePresence>
        {sidebarOpen && (
          <motion.div
            key="mobile-backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 z-40 bg-black/30 backdrop-blur-sm md:hidden"
            onClick={() => setSidebarOpen(false)}
          />
        )}
      </AnimatePresence>
      <AnimatePresence>
        {sidebarOpen && (
          <motion.aside
            key="mobile-sidebar"
            initial={{ x: "-100%" }}
            animate={{ x: 0 }}
            exit={{ x: "-100%" }}
            transition={{ type: "spring", damping: 25, stiffness: 250 }}
            className="fixed inset-y-0 left-0 z-50 w-64 bg-white shadow-xl md:hidden"
          >
            <MobileSidebar
              doctor={doctor}
              navItems={allNavItems}
              isActive={isActive}
              handleLogout={handleLogout}
              onClose={() => setSidebarOpen(false)}
            />
          </motion.aside>
        )}
      </AnimatePresence>

      {/* Main content area */}
      <div className="flex flex-1 flex-col min-w-0 md:ml-60">
        {/* Top bar */}
        <header className="sticky top-0 z-30 h-14 bg-white/80 backdrop-blur-md border-b border-slate-200">
          <div className="flex items-center justify-between h-full px-4">
            {/* Left side */}
            <div className="flex items-center gap-2">
              {/* Mobile hamburger */}
              <button
                type="button"
                onClick={() => setSidebarOpen(true)}
                className="rounded-lg p-1.5 text-slate-500 hover:bg-slate-100 transition-colors md:hidden"
                aria-label="Abrir menú"
              >
                <List size={20} weight="bold" />
              </button>
              {/* Breadcrumbs - hidden on sm and below */}
              <nav className="hidden sm:flex items-center gap-1 text-sm">
                {breadcrumbs.map((crumb, idx) => {
                  const isLast = idx === breadcrumbs.length - 1
                  return (
                    <span key={crumb.to} className="flex items-center gap-1">
                      {idx > 0 && (
                        <CaretRight size={12} className="text-slate-300" />
                      )}
                      {isLast ? (
                        <span className="text-slate-800 font-medium">
                          {crumb.label}
                        </span>
                      ) : (
                        <Link
                          to={crumb.to}
                          className="text-slate-500 hover:text-slate-700 transition-colors"
                        >
                          {crumb.label}
                        </Link>
                      )}
                    </span>
                  )
                })}
              </nav>
            </div>

            {/* Right side */}
            <div className="relative" ref={dropdownRef}>
              <button
                type="button"
                onClick={() => setDropdownOpen(!dropdownOpen)}
                className="flex items-center gap-2 rounded-lg px-2 py-1.5 hover:bg-slate-100 transition-colors"
                aria-label="Menú de usuario"
              >
                <Avatar
                  firstName={doctor?.full_name?.split(" ")[0]}
                  lastName={doctor?.full_name?.split(" ").slice(-1)[0]}
                  size="sm"
                />
                <span className="hidden sm:block text-sm font-medium text-slate-700 truncate max-w-[140px]">
                  {doctor?.full_name || "Doctora"}
                </span>
              </button>

              {/* Dropdown menu */}
              <AnimatePresence>
                {dropdownOpen && (
                  <motion.div
                    key="dropdown"
                    initial={{ opacity: 0, y: -4, scale: 0.95 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    exit={{ opacity: 0, y: -4, scale: 0.95 }}
                    transition={{ duration: 0.15 }}
                    className="absolute right-0 top-full mt-1 z-50 w-56 rounded-xl bg-white shadow-lg border border-slate-200 py-2"
                  >
                    <div className="px-4 py-2 border-b border-slate-100">
                      <p className="text-sm font-medium text-slate-800 truncate">
                        {doctor?.full_name}
                      </p>
                      <p className="text-xs text-slate-500 truncate">
                        {doctor?.email}
                      </p>
                    </div>
                    <div className="pt-1 px-1">
                      <button
                        type="button"
                        onClick={handleLogout}
                        className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium text-slate-600 hover:bg-red-50 hover:text-red-600 transition-colors"
                      >
                        <SignOut size={18} />
                        Cerrar sesión
                      </button>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 p-4 md:p-6 lg:p-8 max-w-[1400px] mx-auto w-full">
          <Outlet />
        </main>
      </div>

      {/* Toast notifications */}
      <ToastContainer />
    </div>
  )
}

function DesktopSidebar({
  navItems,
  isActive,
  handleLogout,
}: {
  doctor: DoctorMe | null
  navItems: { to: string; label: string; icon: Icon }[]
  isActive: (to: string) => boolean
  handleLogout: () => void
}) {
  return (
    <div className="flex h-full flex-col">
      {/* Logo area */}
      <div className="flex items-center gap-3 border-b border-slate-100 px-4 py-4">
        <img
          src="/logo-sidebar.png"
          alt="Nutrisoft"
          width={48}
          height={46}
          className="rounded-lg shadow-sm"
        />
        <span className="text-lg font-bold text-slate-800">Nutrisoft</span>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-3 space-y-0.5">
        {navItems.map((item) => {
          const Icon = item.icon
          const active = isActive(item.to)
          return (
            <Link
              key={item.to}
              to={item.to}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-colors duration-150 ${
                active
                  ? "bg-emerald-50 text-emerald-700"
                  : "text-slate-600 hover:bg-slate-50 hover:text-slate-800"
              }`}
            >
              <Icon size={20} weight={active ? "fill" : "regular"} />
              {item.label}
            </Link>
          )
        })}
      </nav>

      {/* Logout */}
      <div className="border-t border-slate-200 px-3 py-3">
        <button
          type="button"
          onClick={handleLogout}
          className="flex w-full items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium text-slate-500 hover:bg-red-50 hover:text-red-600 transition-colors duration-150"
        >
          <SignOut size={20} />
          Cerrar sesión
        </button>
      </div>
    </div>
  )
}

function MobileSidebar({
  doctor,
  navItems,
  isActive,
  handleLogout,
  onClose,
}: {
  doctor: DoctorMe | null
  navItems: { to: string; label: string; icon: Icon }[]
  isActive: (to: string) => boolean
  handleLogout: () => void
  onClose: () => void
}) {
  return (
    <div className="flex h-full flex-col">
      {/* Logo + close */}
      <div className="flex items-center justify-between border-b border-slate-100 px-4 py-4">
        <div className="flex items-center gap-3">
          <img
            src="/logo-sidebar.png"
            alt="Nutrisoft"
            width={40}
            height={38}
            className="rounded-lg shadow-sm"
          />
          <span className="text-lg font-bold text-slate-800">Nutrisoft</span>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="rounded-lg p-1.5 text-slate-500 hover:bg-slate-100 transition-colors"
          aria-label="Cerrar menú"
        >
          <X size={20} weight="bold" />
        </button>
      </div>

      {/* Doctor info */}
      <div className="px-4 py-3 border-b border-slate-100">
        <p className="text-sm font-semibold text-slate-800 truncate">
          {doctor?.full_name || "Doctora"}
        </p>
        <p className="text-xs text-slate-500 truncate">{doctor?.email}</p>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-3 space-y-0.5">
        {navItems.map((item) => {
          const Icon = item.icon
          const active = isActive(item.to)
          return (
            <Link
              key={item.to}
              to={item.to}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-colors duration-150 ${
                active
                  ? "bg-emerald-50 text-emerald-700"
                  : "text-slate-600 hover:bg-slate-50 hover:text-slate-800"
              }`}
            >
              <Icon size={20} weight={active ? "fill" : "regular"} />
              {item.label}
            </Link>
          )
        })}
      </nav>

      {/* Logout */}
      <div className="border-t border-slate-200 px-3 py-3">
        <button
          type="button"
          onClick={handleLogout}
          className="flex w-full items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium text-slate-500 hover:bg-red-50 hover:text-red-600 transition-colors duration-150"
        >
          <SignOut size={20} />
          Cerrar sesión
        </button>
      </div>
    </div>
  )
}
