import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { Link, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import {
  ActivitySquare,
  Bell,
  ChevronLeft,
  ChevronRight,
  LayoutDashboard,
  LogOut,
  Menu,
  Settings,
  Share2,
  Shield,
  UploadCloud,
  UserCheck,
  Users,
  X,
} from 'lucide-react'

import { useAuthStore } from '../../stores/authStore'
import { useDoctorRoleApplicationsStore } from '../../stores/doctorRoleApplicationsStore'
import { usePatientsStore } from '../../stores/patientsStore'
import { useShareRequestsStore } from '../../stores/shareRequestsStore'

const roleLabel: Record<string, string> = {
  doctor: 'Врач',
  patient: 'Пациент',
  admin: 'Администратор',
}

const roleColor: Record<string, string> = {
  doctor: 'bg-accent-100 text-accent-700',
  patient: 'bg-secondary-100 text-secondary-700',
  admin: 'bg-primary-100 text-primary-700',
}

function getInitials(firstName?: string, lastName?: string, email?: string): string {
  if (firstName && lastName) return (firstName[0] + lastName[0]).toUpperCase()
  if (firstName) return firstName[0].toUpperCase()
  if (email) return email[0].toUpperCase()
  return '?'
}

function getAvatarColor(str: string): string {
  const colors = [
    'bg-primary-500', 'bg-secondary-500', 'bg-accent-500',
    'bg-success-500', 'bg-warning-500',
  ]
  const index = str.charCodeAt(0) % colors.length
  return colors[index]
}

export const DashboardLayout = () => {
  const { user, logout, refreshUser } = useAuthStore()
  const { patients, fetchPatients } = usePatientsStore()
  const { inbox } = useShareRequestsStore()
  const roleApplicationInbox = useDoctorRoleApplicationsStore((state) => state.inbox)
  const fetchRoleApplicationInbox = useDoctorRoleApplicationsStore((state) => state.fetchInbox)
  const location = useLocation()
  const navigate = useNavigate()

  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false)
  const [isCollapsed, setIsCollapsed] = useState(false)
  const [isNotificationsOpen, setIsNotificationsOpen] = useState(false)
  const [isProfileOpen, setIsProfileOpen] = useState(false)

  const pendingShareCount = inbox.filter((r) => r.status === 'pending').length
  const pendingRoleApplicationCount = roleApplicationInbox.length

  useEffect(() => {
    void refreshUser()
  }, [refreshUser])

  useEffect(() => {
    if (user?.role === 'patient') {
      void fetchPatients()
    }
  }, [user?.role, fetchPatients])

  useEffect(() => {
    if (user?.role === 'doctor' || user?.role === 'admin') {
      void fetchRoleApplicationInbox()
    }
  }, [fetchRoleApplicationInbox, user?.role])

  const handleLogout = () => {
    logout()
    navigate('/auth/login')
  }

  const isActive = (path: string) => location.pathname.startsWith(path)

  const patientPath =
    user?.role === 'patient' && patients.length > 0
      ? `/patients/${patients[0].id}`
      : '/patients'

  const getNavLinks = () => {
    const commonLinks = [
      {
        path: '/dashboard',
        label: 'Dashboard',
        icon: <LayoutDashboard className="h-5 w-5" />,
        badge: 0,
      },
      {
        path: '/share-requests',
        label: 'Sharing',
        icon: <Share2 className="h-5 w-5" />,
        badge: pendingShareCount,
      },
    ]

    const roleLinks: Record<string, Array<{ path: string; label: string; icon: ReactNode; badge: number }>> = {
      doctor: [
        { path: '/doctor-role-reviews', label: 'Заявки врачей', icon: <UserCheck className="h-5 w-5" />, badge: pendingRoleApplicationCount },
        { path: '/upload', label: 'Импорт архива', icon: <UploadCloud className="h-5 w-5" />, badge: 0 },
        { path: '/patients', label: 'Пациенты', icon: <Users className="h-5 w-5" />, badge: 0 },
      ],
      admin: [
        { path: '/doctor-role-reviews', label: 'Заявки врачей', icon: <UserCheck className="h-5 w-5" />, badge: pendingRoleApplicationCount },
        { path: '/upload', label: 'Импорт архива', icon: <UploadCloud className="h-5 w-5" />, badge: 0 },
        { path: '/patients', label: 'Пациенты', icon: <Users className="h-5 w-5" />, badge: 0 },
        { path: '/admin', label: 'Панель админа', icon: <Shield className="h-5 w-5" />, badge: 0 },
      ],
      patient: [
        { path: patientPath, label: 'Мои записи', icon: <Users className="h-5 w-5" />, badge: 0 },
        { path: '/doctor-role-request', label: 'Стать врачом', icon: <UserCheck className="h-5 w-5" />, badge: 0 },
      ],
    }

    return [...commonLinks, ...(user?.role ? roleLinks[user.role] ?? [] : [])]
  }

  const breadcrumbs = getBreadcrumbs(location.pathname)
  const initials = getInitials(user?.first_name, user?.last_name, user?.email)
  const avatarColor = getAvatarColor(user?.first_name ?? user?.email ?? 'A')

  const notifications = [
    {
      id: 1,
      title: 'Новый sharing-запрос',
      message: 'Вам отправили доступ к медицинским записям.',
      time: 'только что',
      unread: true,
    },
  ]

  const SidebarContent = ({ collapsed }: { collapsed: boolean }) => (
    <div className="flex h-full flex-col">
      <div className={`flex items-center border-b border-gray-100 px-4 py-5 ${collapsed ? 'justify-center' : 'justify-between'}`}>
        {!collapsed && (
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary-600">
              <ActivitySquare className="h-5 w-5 text-white" />
            </div>
            <span className="text-lg font-bold text-gray-900">Docere</span>
          </div>
        )}
        {collapsed && (
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary-600">
            <ActivitySquare className="h-5 w-5 text-white" />
          </div>
        )}
      </div>

      {!collapsed && user && (
        <div className="mx-3 mt-4 rounded-xl bg-gray-50 px-3 py-3">
          <div className="flex items-center gap-3">
            <div className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-sm font-semibold text-white ${avatarColor}`}>
              {initials}
            </div>
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold text-gray-900">
                {user.first_name} {user.last_name}
              </p>
              <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${roleColor[user.role] ?? 'bg-gray-100 text-gray-700'}`}>
                {roleLabel[user.role] ?? user.role}
              </span>
            </div>
          </div>
        </div>
      )}

      <nav className="mt-4 flex-1 space-y-0.5 overflow-y-auto px-3 scrollbar-thin">
        <p className={`mb-2 px-3 text-xs font-semibold uppercase tracking-wider text-gray-400 ${collapsed ? 'text-center' : ''}`}>
          {!collapsed && 'Меню'}
        </p>
        {getNavLinks().map((link) => (
          <Link
            key={link.path}
            to={link.path}
            className={`group relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all duration-150 ${
              isActive(link.path)
                ? 'bg-primary-50 text-primary-700'
                : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
            } ${collapsed ? 'justify-center' : ''}`}
            title={collapsed ? link.label : undefined}
          >
            {isActive(link.path) && (
              <span className="absolute left-0 top-1/2 h-5 w-0.5 -translate-y-1/2 rounded-r bg-primary-600" />
            )}
            <span className={isActive(link.path) ? 'text-primary-600' : 'text-gray-400 group-hover:text-gray-600'}>
              {link.icon}
            </span>
            {!collapsed && <span className="flex-1">{link.label}</span>}
            {!collapsed && link.badge > 0 && (
              <span className="flex h-5 min-w-5 items-center justify-center rounded-full bg-error-500 px-1 text-xs font-bold text-white">
                {link.badge}
              </span>
            )}
            {collapsed && link.badge > 0 && (
              <span className="absolute right-1 top-1 h-2 w-2 rounded-full bg-error-500" />
            )}
          </Link>
        ))}

        <div className="mt-4 border-t border-gray-100 pt-4">
          {!collapsed && (
            <p className="mb-2 px-3 text-xs font-semibold uppercase tracking-wider text-gray-400">Настройки</p>
          )}
          <Link
            to="/settings"
            className={`group flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-gray-600 transition-all duration-150 hover:bg-gray-50 hover:text-gray-900 ${collapsed ? 'justify-center' : ''}`}
            title={collapsed ? 'Настройки аккаунта' : undefined}
          >
            <Settings className="h-5 w-5 text-gray-400 group-hover:text-gray-600" />
            {!collapsed && 'Настройки аккаунта'}
          </Link>
          <button
            onClick={handleLogout}
            className={`group flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-gray-600 transition-all duration-150 hover:bg-error-50 hover:text-error-700 ${collapsed ? 'justify-center' : ''}`}
            title={collapsed ? 'Выйти' : undefined}
          >
            <LogOut className="h-5 w-5 text-gray-400 group-hover:text-error-500" />
            {!collapsed && 'Выйти'}
          </button>
        </div>
      </nav>
    </div>
  )

  return (
    <div className="flex min-h-screen bg-gray-50">
      {/* Desktop Sidebar */}
      <aside
        className={`fixed inset-y-0 left-0 z-30 hidden border-r border-gray-200 bg-white shadow-sidebar transition-all duration-300 lg:flex lg:flex-col ${
          isCollapsed ? 'w-16' : 'w-64'
        }`}
      >
        <SidebarContent collapsed={isCollapsed} />
        <button
          onClick={() => setIsCollapsed((c) => !c)}
          className="absolute -right-3 top-20 flex h-6 w-6 items-center justify-center rounded-full border border-gray-200 bg-white shadow-sm transition-colors hover:bg-gray-50"
        >
          {isCollapsed
            ? <ChevronRight className="h-3.5 w-3.5 text-gray-500" />
            : <ChevronLeft className="h-3.5 w-3.5 text-gray-500" />
          }
        </button>
      </aside>

      {/* Mobile Sidebar Overlay */}
      <AnimatePresence>
        {isMobileMenuOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-40 lg:hidden"
          >
            <div
              className="absolute inset-0 bg-gray-900/60 backdrop-blur-sm"
              onClick={() => setIsMobileMenuOpen(false)}
            />
            <motion.div
              initial={{ x: -280 }}
              animate={{ x: 0 }}
              exit={{ x: -280 }}
              transition={{ type: 'spring', damping: 30, stiffness: 300 }}
              className="relative flex h-full w-72 flex-col bg-white shadow-xl"
            >
              <button
                onClick={() => setIsMobileMenuOpen(false)}
                className="absolute right-4 top-4 rounded-md p-1 text-gray-400 hover:bg-gray-100"
              >
                <X className="h-5 w-5" />
              </button>
              <SidebarContent collapsed={false} />
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Main content */}
      <div className={`flex flex-1 flex-col transition-all duration-300 ${isCollapsed ? 'lg:pl-16' : 'lg:pl-64'}`}>
        {/* Top Header */}
        <header className="sticky top-0 z-20 flex h-14 items-center justify-between border-b border-gray-200 bg-white px-4 shadow-sm sm:px-6">
          <div className="flex items-center gap-4">
            <button
              onClick={() => setIsMobileMenuOpen(true)}
              className="rounded-md p-1.5 text-gray-500 hover:bg-gray-100 lg:hidden"
            >
              <Menu className="h-5 w-5" />
            </button>

            {/* Breadcrumbs */}
            <nav className="hidden items-center gap-1.5 text-sm sm:flex">
              {breadcrumbs.map((crumb, i) => (
                <span key={crumb.path} className="flex items-center gap-1.5">
                  {i > 0 && <span className="text-gray-300">/</span>}
                  {i === breadcrumbs.length - 1 ? (
                    <span className="font-medium text-gray-900">{crumb.label}</span>
                  ) : (
                    <Link to={crumb.path} className="text-gray-500 hover:text-gray-700">
                      {crumb.label}
                    </Link>
                  )}
                </span>
              ))}
            </nav>
          </div>

          <div className="flex items-center gap-2">
            {/* Notifications */}
            <div className="relative">
              <button
                onClick={() => {
                  setIsNotificationsOpen((o) => !o)
                  setIsProfileOpen(false)
                }}
                className="relative rounded-lg p-2 text-gray-500 hover:bg-gray-100 hover:text-gray-700"
              >
                <Bell className="h-5 w-5" />
                {notifications.some((n) => n.unread) && (
                  <span className="absolute right-1.5 top-1.5 h-2 w-2 rounded-full bg-error-500 ring-2 ring-white" />
                )}
              </button>
              <AnimatePresence>
                {isNotificationsOpen && (
                  <motion.div
                    initial={{ opacity: 0, y: 6, scale: 0.97 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    exit={{ opacity: 0, y: 6, scale: 0.97 }}
                    transition={{ duration: 0.15 }}
                    className="absolute right-0 mt-1 w-80 overflow-hidden rounded-xl border border-gray-100 bg-white shadow-lg"
                  >
                    <div className="border-b border-gray-100 px-4 py-3">
                      <h3 className="text-sm font-semibold text-gray-900">Уведомления</h3>
                    </div>
                    <div className="max-h-64 overflow-y-auto scrollbar-thin">
                      {notifications.map((n) => (
                        <div key={n.id} className={`px-4 py-3 ${n.unread ? 'bg-primary-50/50' : 'hover:bg-gray-50'}`}>
                          <div className="flex items-start gap-2">
                            {n.unread && <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-primary-500" />}
                            <div>
                              <p className="text-sm font-medium text-gray-900">{n.title}</p>
                              <p className="mt-0.5 text-xs text-gray-500">{n.message}</p>
                              <p className="mt-1 text-xs text-gray-400">{n.time}</p>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            {/* Profile */}
            <div className="relative">
              <button
                onClick={() => {
                  setIsProfileOpen((o) => !o)
                  setIsNotificationsOpen(false)
                }}
                className="flex items-center gap-2 rounded-lg px-2 py-1.5 hover:bg-gray-100"
              >
                <div className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-semibold text-white ${avatarColor}`}>
                  {initials}
                </div>
                <div className="hidden text-left md:block">
                  <p className="text-sm font-medium text-gray-900 leading-tight">
                    {user?.first_name} {user?.last_name}
                  </p>
                  <p className="text-xs text-gray-500 leading-tight">
                    {user?.role ? (roleLabel[user.role] ?? user.role) : ''}
                  </p>
                </div>
              </button>
              <AnimatePresence>
                {isProfileOpen && (
                  <motion.div
                    initial={{ opacity: 0, y: 6, scale: 0.97 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    exit={{ opacity: 0, y: 6, scale: 0.97 }}
                    transition={{ duration: 0.15 }}
                    className="absolute right-0 mt-1 w-48 overflow-hidden rounded-xl border border-gray-100 bg-white shadow-lg"
                  >
                    <Link
                      to="/settings"
                      onClick={() => setIsProfileOpen(false)}
                      className="flex items-center gap-2 px-4 py-2.5 text-sm text-gray-700 hover:bg-gray-50"
                    >
                      <Settings className="h-4 w-4 text-gray-400" />
                      Настройки
                    </Link>
                    <button
                      onClick={handleLogout}
                      className="flex w-full items-center gap-2 px-4 py-2.5 text-sm text-error-600 hover:bg-error-50"
                    >
                      <LogOut className="h-4 w-4" />
                      Выйти
                    </button>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-auto">
          <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  )
}

function getBreadcrumbs(pathname: string): Array<{ label: string; path: string }> {
  const map: Record<string, string> = {
    '/dashboard': 'Dashboard',
    '/dashboard/doctor': 'Кабинет врача',
    '/dashboard/patient': 'Личный кабинет',
    '/dashboard/admin': 'Панель администратора',
    '/patients': 'Пациенты',
    '/share-requests': 'Sharing записей',
    '/doctor-role-request': 'Заявка на роль врача',
    '/doctor-role-reviews': 'Проверка заявок врачей',
    '/upload': 'Импорт архива',
    '/admin': 'Управление системой',
    '/settings': 'Настройки аккаунта',
  }

  const crumbs: Array<{ label: string; path: string }> = [
    { label: 'Главная', path: '/dashboard' },
  ]

  const parts = pathname.split('/').filter(Boolean)
  let current = ''
  for (const part of parts) {
    current += '/' + part
    const label = map[current]
    if (label && current !== '/dashboard') {
      crumbs.push({ label, path: current })
    } else if (!label && current !== '/dashboard') {
      crumbs.push({ label: part, path: current })
    }
  }

  if (crumbs.length === 1) return crumbs
  return crumbs
}
