import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { Link, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import {
  ActivitySquare,
  Bell,
  LayoutDashboard,
  LogOut,
  Menu,
  Settings,
  Share2,
  Shield,
  Users,
  X,
} from 'lucide-react'

import { useAuthStore } from '../../stores/authStore'
import { usePatientsStore } from '../../stores/patientsStore'

export const DashboardLayout = () => {
  const { user, logout } = useAuthStore()
  const { patients, fetchPatients } = usePatientsStore()
  const location = useLocation()
  const navigate = useNavigate()

  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false)
  const [isNotificationsOpen, setIsNotificationsOpen] = useState(false)
  const [isProfileOpen, setIsProfileOpen] = useState(false)

  useEffect(() => {
    if (user?.role === 'patient') {
      void fetchPatients()
    }
  }, [user?.role, fetchPatients])

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
      },
      {
        path: '/share-requests',
        label: 'Sharing',
        icon: <Share2 className="h-5 w-5" />,
      },
    ]

    const roleLinks: Record<string, Array<{ path: string; label: string; icon: ReactNode }>> = {
      doctor: [
        { path: '/patients', label: 'Patients', icon: <Users className="h-5 w-5" /> },
      ],
      admin: [
        { path: '/patients', label: 'Patients', icon: <Users className="h-5 w-5" /> },
        { path: '/admin', label: 'Admin Panel', icon: <Shield className="h-5 w-5" /> },
      ],
      patient: [
        { path: patientPath, label: 'My Records', icon: <Users className="h-5 w-5" /> },
      ],
    }

    return [...commonLinks, ...(user?.role ? roleLinks[user.role] : [])]
  }

  const notifications = [
    {
      id: 1,
      title: 'Карточки пациентов синхронизированы',
      message: 'Основной рабочий сценарий теперь проходит через новый patients flow.',
      time: 'только что',
    },
  ]

  return (
    <div className="min-h-screen bg-gray-100">
      <header className="sticky top-0 z-10 bg-white shadow">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex items-center">
            <ActivitySquare className="h-8 w-8 text-primary-600" />
            <span className="ml-2 text-xl font-bold text-gray-900">Docere</span>
          </motion.div>

          <div className="flex items-center space-x-4">
            <div className="relative">
              <button
                onClick={() => setIsNotificationsOpen((opened) => !opened)}
                className="rounded-full p-1 text-gray-600 hover:text-gray-900 focus:ring-2 focus:ring-primary-500"
              >
                <span className="sr-only">View notifications</span>
                <Bell className="h-6 w-6" />
                <span className="absolute right-0 top-0 block h-2 w-2 rounded-full bg-error-500 ring-2 ring-white" />
              </button>
              <AnimatePresence>
                {isNotificationsOpen && (
                  <motion.div
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: 8 }}
                    transition={{ duration: 0.2 }}
                    className="absolute right-0 mt-2 w-80 origin-top-right rounded-md bg-white shadow ring-1 ring-black ring-opacity-5"
                  >
                    <div className="py-1">
                      <div className="border-b px-4 py-2">
                        <h3 className="text-sm font-medium">Notifications</h3>
                      </div>
                      <div className="max-h-60 overflow-y-auto">
                        {notifications.map((notification) => (
                          <div key={notification.id} className="px-4 py-3 hover:bg-gray-50">
                            <p className="text-sm font-medium">{notification.title}</p>
                            <p className="text-sm text-gray-500">{notification.message}</p>
                            <p className="mt-1 text-xs text-gray-400">{notification.time}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            <div className="relative">
              <button
                onClick={() => setIsProfileOpen((opened) => !opened)}
                className="flex items-center gap-2 focus:outline-none"
              >
                <div className="hidden text-right md:block">
                  <p className="text-sm font-medium">
                    {user?.first_name} {user?.last_name}
                  </p>
                  <p className="text-xs text-gray-500">
                    {user ? user.role.charAt(0).toUpperCase() + user.role.slice(1) : ''}
                  </p>
                </div>
                <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary-100 font-medium text-primary-700">
                  {user?.first_name?.[0] || user?.email?.[0]?.toUpperCase()}
                </div>
              </button>
              <AnimatePresence>
                {isProfileOpen && (
                  <motion.div
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: 8 }}
                    transition={{ duration: 0.2 }}
                    className="absolute right-0 mt-2 w-48 origin-top-right rounded-md bg-white shadow ring-1 ring-black ring-opacity-5"
                  >
                    <div className="py-1">
                      <Link to="/settings" className="block px-4 py-2 text-sm hover:bg-gray-100">
                        Account Settings
                      </Link>
                      <button
                        onClick={handleLogout}
                        className="block w-full px-4 py-2 text-left text-sm hover:bg-gray-100"
                      >
                        Sign out
                      </button>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            <div className="lg:hidden">
              <button
                onClick={() => setIsMobileMenuOpen((opened) => !opened)}
                className="rounded-md p-2 text-gray-400 hover:bg-gray-100 focus:ring-2 focus:ring-primary-500"
              >
                <span className="sr-only">Open menu</span>
                {isMobileMenuOpen ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
              </button>
            </div>
          </div>
        </div>
      </header>

      <div className="flex">
        <div className="fixed inset-y-0 hidden w-64 border-r border-gray-200 bg-white pt-16 lg:flex lg:flex-col">
          <nav className="mt-8 space-y-1 px-4">
            {getNavLinks().map((link) => (
              <Link
                key={link.path}
                to={link.path}
                className={`group flex items-center rounded-md px-3 py-2 text-sm font-medium ${
                  isActive(link.path)
                    ? 'bg-primary-50 text-primary-700'
                    : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                }`}
              >
                <span
                  className={`mr-3 ${
                    isActive(link.path)
                      ? 'text-primary-500'
                      : 'text-gray-400 group-hover:text-gray-500'
                  }`}
                >
                  {link.icon}
                </span>
                {link.label}
              </Link>
            ))}

            <div className="mt-8 border-t border-gray-200 pt-4">
              <div className="mb-2 px-3 text-xs font-semibold uppercase text-gray-400">Settings</div>
              <Link
                to="/settings"
                className="group flex items-center rounded-md px-3 py-2 text-sm font-medium text-gray-600 hover:bg-gray-50 hover:text-gray-900"
              >
                <Settings className="mr-3 h-5 w-5 text-gray-400 group-hover:text-gray-500" />
                Account Settings
              </Link>
              <button
                onClick={handleLogout}
                className="group flex w-full items-center rounded-md px-3 py-2 text-sm font-medium text-gray-600 hover:bg-gray-50 hover:text-error-700"
              >
                <LogOut className="mr-3 h-5 w-5 text-gray-400 group-hover:text-error-500" />
                Logout
              </button>
            </div>
          </nav>
        </div>

        <AnimatePresence>
          {isMobileMenuOpen && (
            <motion.div
              initial={{ opacity: 0, x: -100 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -100 }}
              transition={{ duration: 0.3 }}
              className="fixed inset-0 z-40 flex lg:hidden"
            >
              <div
                className="fixed inset-0 bg-gray-600 bg-opacity-75"
                onClick={() => setIsMobileMenuOpen(false)}
              />
              <div className="relative flex w-full max-w-xs flex-1 flex-col bg-white">
                <div className="px-4 pb-4 pt-5">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center">
                      <ActivitySquare className="h-8 w-8 text-primary-600" />
                      <span className="ml-2 text-xl font-bold text-gray-900">Docere</span>
                    </div>
                    <button
                      onClick={() => setIsMobileMenuOpen(false)}
                      className="rounded-md p-2 text-gray-400 hover:bg-gray-100 focus:ring-2 focus:ring-primary-500"
                    >
                      <X className="h-6 w-6" />
                    </button>
                  </div>
                </div>
                <nav className="mt-5 space-y-1 px-4">
                  {getNavLinks().map((link) => (
                    <Link
                      key={link.path}
                      to={link.path}
                      onClick={() => setIsMobileMenuOpen(false)}
                      className={`group flex items-center rounded-md px-3 py-2 text-base font-medium ${
                        isActive(link.path)
                          ? 'bg-primary-50 text-primary-700'
                          : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                      }`}
                    >
                      <span className="mr-4">{link.icon}</span>
                      {link.label}
                    </Link>
                  ))}
                  <div className="border-t border-gray-200 pt-8">
                    <div className="mb-2 px-3 text-xs font-semibold uppercase text-gray-400">Settings</div>
                    <Link
                      to="/settings"
                      onClick={() => setIsMobileMenuOpen(false)}
                      className="group flex items-center rounded-md px-3 py-2 text-base font-medium text-gray-600 hover:bg-gray-50 hover:text-gray-900"
                    >
                      <Settings className="mr-4 h-5 w-5 text-gray-400 group-hover:text-gray-500" />
                      Account Settings
                    </Link>
                    <button
                      onClick={handleLogout}
                      className="group flex w-full items-center rounded-md px-3 py-2 text-base font-medium text-gray-600 hover:bg-gray-50 hover:text-error-700"
                    >
                      <LogOut className="mr-4 h-5 w-5 text-gray-400 group-hover:text-error-500" />
                      Logout
                    </button>
                  </div>
                </nav>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        <main className="flex-1 lg:pl-64">
          <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  )
}
