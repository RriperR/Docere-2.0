// src/components/layouts/DashboardLayout.tsx
import { Link, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  ActivitySquare,
  Users,
  Upload,
  LayoutDashboard,
  Settings,
  LogOut,
  Menu,
  X,
  Bell,
  Shield
} from 'lucide-react';
import { useAuthStore } from '../../stores/authStore';
import { usePatientsStore } from '../../stores/patientsStore';

export const DashboardLayout = () => {
  const { user, logout } = useAuthStore();
  const { patients, fetchPatients } = usePatientsStore();
  const location = useLocation();
  const navigate = useNavigate();

  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [isNotificationsOpen, setIsNotificationsOpen] = useState(false);
  const [isProfileOpen, setIsProfileOpen] = useState(false);

  // При входе пациента — подгружаем его единственную карточку
  useEffect(() => {
    if (user?.role === 'patient') {
      void fetchPatients();
    }
  }, [user?.role, fetchPatients]);

  const handleLogout = () => {
    logout();
    navigate('/auth/login');
  };

  const isActive = (path: string) => location.pathname.startsWith(path);

  // Если пациент — дергаем id его карточки
  const patientPath =
    user?.role === 'patient' && patients.length > 0
      ? `/patients/${patients[0].id}`
      : '/patients';

  // Навигационные ссылки
  const getNavLinks = () => {
    const commonLinks = [
      {
        path: '/dashboard',
        label: 'Dashboard',
        icon: <LayoutDashboard className="h-5 w-5" />,
      },
    ];

    const roleLinks: Record<string, Array<{path:string;label:string;icon:React.ReactNode}>> = {
      doctor: [
        { path: '/upload',        label: 'Upload Archive', icon: <Upload className="h-5 w-5" /> },
        { path: '/patients',      label: 'Patients',       icon: <Users className="h-5 w-5" /> },
      ],
      admin: [
        { path: '/patients',      label: 'Patients',       icon: <Users className="h-5 w-5" /> },
        { path: '/admin',         label: 'Admin Panel',    icon: <Shield className="h-5 w-5" /> },
      ],
      patient: [
        { path: '/upload',                     label: 'Upload Archive',     icon: <Upload className="h-5 w-5" /> },
        { path: patientPath,                   label: 'My Records',         icon: <Users className="h-5 w-5" /> },
        { path: '/roles/request',              label: 'Request Doctor Role',icon: <Shield className="h-5 w-5" /> },
      ],
    };

    return [
      ...commonLinks,
      ...(user?.role ? roleLinks[user.role] : []),
    ];
  };

  // Мок уведомлений
  const notifications = [
    { id: 1, title: 'New upload completed', message: 'Records for John Doe uploaded.', time: '5 minutes ago' },
    { id: 2, title: 'Doctor role request', message: 'Dr. Maria Johnson requested privileges.', time: '1 hour ago' },
  ];

  return (
    <div className="min-h-screen bg-gray-100">
      {/* Header */}
      <header className="bg-white shadow sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16 items-center">
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex items-center">
              <ActivitySquare className="h-8 w-8 text-primary-600" />
              <span className="ml-2 text-xl font-bold text-gray-900">Docere</span>
            </motion.div>

            <div className="flex items-center space-x-4">
              {/* Notifications */}
              <div className="relative">
                <button
                  onClick={() => setIsNotificationsOpen(o => !o)}
                  className="p-1 rounded-full text-gray-600 hover:text-gray-900 focus:ring-2 focus:ring-primary-500"
                >
                  <span className="sr-only">View notifications</span>
                  <Bell className="h-6 w-6" />
                  <span className="absolute top-0 right-0 block h-2 w-2 rounded-full bg-error-500 ring-2 ring-white" />
                </button>
                <AnimatePresence>
                  {isNotificationsOpen && (
                    <motion.div
                      initial={{ opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: 8 }}
                      transition={{ duration: 0.2 }}
                      className="origin-top-right absolute right-0 mt-2 w-80 bg-white shadow rounded-md ring-1 ring-black ring-opacity-5"
                    >
                      <div className="py-1">
                        <div className="px-4 py-2 border-b">
                          <h3 className="text-sm font-medium">Notifications</h3>
                        </div>
                        <div className="max-h-60 overflow-y-auto">
                          {notifications.map(n => (
                            <div key={n.id} className="px-4 py-3 hover:bg-gray-50">
                              <p className="font-medium text-sm">{n.title}</p>
                              <p className="text-gray-500 text-sm">{n.message}</p>
                              <p className="text-gray-400 text-xs mt-1">{n.time}</p>
                            </div>
                          ))}
                        </div>
                        <div className="px-4 py-2 border-t">
                          <button className="text-primary-600 text-sm">View all notifications</button>
                        </div>
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>

              {/* Profile */}
              <div className="relative">
                <button
                  onClick={() => setIsProfileOpen(o => !o)}
                  className="flex items-center gap-2 focus:outline-none"
                >
                  <div className="hidden md:block text-right">
                    <p className="text-sm font-medium">{user?.first_name} {user?.last_name}</p>
                    <p className="text-xs text-gray-500">{user!.role.charAt(0).toUpperCase() + user!.role.slice(1)}</p>
                  </div>
                  <div className="h-8 w-8 rounded-full bg-primary-100 flex items-center justify-center text-primary-700 font-medium">
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
                      className="origin-top-right absolute right-0 mt-2 w-48 bg-white shadow rounded-md ring-1 ring-black ring-opacity-5"
                    >
                      <div className="py-1">
                        <Link to="/settings" className="block px-4 py-2 text-sm hover:bg-gray-100">Account Settings</Link>
                        {user?.role === 'doctor' && (
                          <Link to="/roles/review" className="block px-4 py-2 text-sm hover:bg-gray-100">Review Requests</Link>
                        )}
                        <button onClick={handleLogout} className="block w-full text-left px-4 py-2 text-sm hover:bg-gray-100">Sign out</button>
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>

              {/* Mobile menu toggle */}
              <div className="lg:hidden">
                <button
                  onClick={() => setIsMobileMenuOpen(o => !o)}
                  className="p-2 rounded-md text-gray-400 hover:bg-gray-100 focus:ring-2 focus:ring-primary-500"
                >
                  <span className="sr-only">Open menu</span>
                  {isMobileMenuOpen ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
                </button>
              </div>
            </div>
          </div>
        </div>
      </header>

      <div className="flex">
        {/* Sidebar desktop */}
        <div className="hidden lg:flex lg:flex-col lg:w-64 lg:fixed lg:inset-y-0 lg:pt-16 lg:border-r lg:border-gray-200 lg:bg-white">
          <nav className="mt-8 px-4 space-y-1">
            {getNavLinks().map(link => (
              <Link
                key={link.path}
                to={link.path}
                className={`group flex items-center px-3 py-2 text-sm font-medium rounded-md ${
                  isActive(link.path)
                    ? 'bg-primary-50 text-primary-700'
                    : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                }`}
              >
                <span className={`mr-3 ${
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

            <div className="mt-8 pt-4 border-t border-gray-200">
              <div className="px-3 mb-2 text-xs font-semibold text-gray-400 uppercase">Settings</div>
              <Link
                to="/settings"
                className="group flex items-center px-3 py-2 text-sm font-medium rounded-md text-gray-600 hover:bg-gray-50 hover:text-gray-900"
              >
                <Settings className="h-5 w-5 mr-3 text-gray-400 group-hover:text-gray-500" />
                Account Settings
              </Link>
              <button
                onClick={handleLogout}
                className="group flex items-center w-full px-3 py-2 text-sm font-medium rounded-md text-gray-600 hover:bg-gray-50 hover:text-error-700"
              >
                <LogOut className="h-5 w-5 mr-3 text-gray-400 group-hover:text-error-500" />
                Logout
              </button>
            </div>
          </nav>
        </div>

        {/* Mobile menu */}
        <AnimatePresence>
          {isMobileMenuOpen && (
            <motion.div
              initial={{ opacity: 0, x: -100 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -100 }}
              transition={{ duration: 0.3 }}
              className="fixed inset-0 flex z-40 lg:hidden"
            >
              <div
                className="fixed inset-0 bg-gray-600 bg-opacity-75"
                onClick={() => setIsMobileMenuOpen(false)}
              />
              <div className="relative flex-1 flex flex-col max-w-xs w-full bg-white">
                <div className="px-4 pt-5 pb-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center">
                      <ActivitySquare className="h-8 w-8 text-primary-600" />
                      <span className="ml-2 text-xl font-bold text-gray-900">Docere</span>
                    </div>
                    <button
                      onClick={() => setIsMobileMenuOpen(false)}
                      className="p-2 rounded-md text-gray-400 hover:bg-gray-100 focus:ring-2 focus:ring-primary-500"
                    >
                      <X className="h-6 w-6" />
                    </button>
                  </div>
                </div>
                <nav className="mt-5 px-4 space-y-1">
                  {getNavLinks().map(link => (
                    <Link
                      key={link.path}
                      to={link.path}
                      onClick={() => setIsMobileMenuOpen(false)}
                      className={`group flex items-center px-3 py-2 text-base font-medium rounded-md ${
                        isActive(link.path)
                          ? 'bg-primary-50 text-primary-700'
                          : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                      }`}
                    >
                      <span className="mr-4">
                        {link.icon}
                      </span>
                      {link.label}
                    </Link>
                  ))}
                  <div className="pt-8 border-t border-gray-200">
                    <div className="px-3 mb-2 text-xs font-semibold text-gray-400 uppercase">Settings</div>
                    <Link
                      to="/settings"
                      onClick={() => setIsMobileMenuOpen(false)}
                      className="group flex items-center px-3 py-2 text-base font-medium rounded-md text-gray-600 hover:bg-gray-50 hover:text-gray-900"
                    >
                      <Settings className="h-5 w-5 mr-4 text-gray-400 group-hover:text-gray-500" />
                      Account Settings
                    </Link>
                    <button
                      onClick={handleLogout}
                      className="group flex items-center w-full px-3 py-2 text-base font-medium rounded-md text-gray-600 hover:bg-gray-50 hover:text-error-700"
                    >
                      <LogOut className="h-5 w-5 mr-4 text-gray-400 group-hover:text-error-500" />
                      Logout
                    </button>
                  </div>
                </nav>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Main content */}
        <main className="flex-1 lg:pl-64">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
};
