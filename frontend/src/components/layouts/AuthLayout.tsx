import { Outlet } from 'react-router-dom'
import { motion } from 'framer-motion'
import { ActivitySquare, Heart, Shield, Users } from 'lucide-react'

const features = [
  {
    icon: <Shield className="h-5 w-5" />,
    title: 'Защита данных',
    description: 'Медицинские записи под надёжной защитой с ролевым доступом.',
  },
  {
    icon: <Users className="h-5 w-5" />,
    title: 'Совместная работа',
    description: 'Безопасный обмен записями между врачами и пациентами.',
  },
  {
    icon: <Heart className="h-5 w-5" />,
    title: 'История наблюдений',
    description: 'Полная хронология медицинских событий в одном месте.',
  },
]

export const AuthLayout = () => {
  return (
    <div className="flex min-h-screen">
      {/* Left panel — branding */}
      <motion.div
        className="relative hidden flex-col justify-between overflow-hidden bg-primary-700 px-12 py-10 lg:flex lg:w-1/2"
        initial={{ opacity: 0, x: -20 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.6 }}
      >
        {/* Background pattern */}
        <div className="pointer-events-none absolute inset-0 overflow-hidden">
          <div className="absolute -right-20 -top-20 h-80 w-80 rounded-full bg-primary-600/40 blur-3xl" />
          <div className="absolute -bottom-20 -left-20 h-80 w-80 rounded-full bg-accent-500/20 blur-3xl" />
          <div className="absolute left-1/2 top-1/2 h-60 w-60 -translate-x-1/2 -translate-y-1/2 rounded-full bg-primary-500/30 blur-3xl" />
        </div>

        <div className="relative">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-white/20 backdrop-blur-sm">
              <ActivitySquare className="h-6 w-6 text-white" />
            </div>
            <span className="text-xl font-bold text-white">Docere</span>
          </div>
        </div>

        <div className="relative space-y-8">
          <div>
            <h1 className="text-4xl font-bold leading-tight text-white">
              Медицинские записи
              <br />
              <span className="text-primary-200">нового поколения</span>
            </h1>
            <p className="mt-4 text-base leading-relaxed text-primary-100">
              Управляйте историей болезни пациентов, делитесь записями с коллегами и ведите
              медицинскую документацию в единой защищённой системе.
            </p>
          </div>

          <div className="space-y-4">
            {features.map((feature) => (
              <div key={feature.title} className="flex items-start gap-3">
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-white/15 text-white">
                  {feature.icon}
                </div>
                <div>
                  <p className="text-sm font-semibold text-white">{feature.title}</p>
                  <p className="text-xs text-primary-200">{feature.description}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="relative">
          <p className="text-xs text-primary-300">
            © {new Date().getFullYear()} Docere — Medical Records Management System
          </p>
        </div>
      </motion.div>

      {/* Right panel — form */}
      <div className="flex flex-1 flex-col items-center justify-center bg-gray-50 px-4 py-12 sm:px-8">
        {/* Mobile logo */}
        <motion.div
          className="mb-8 flex items-center gap-2 lg:hidden"
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
        >
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary-600">
            <ActivitySquare className="h-5 w-5 text-white" />
          </div>
          <span className="text-xl font-bold text-gray-900">Docere</span>
        </motion.div>

        <motion.div
          className="w-full max-w-md"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1, duration: 0.5 }}
        >
          <div className="rounded-2xl border border-gray-200 bg-white p-8 shadow-card">
            <Outlet />
          </div>
        </motion.div>

        <p className="mt-6 text-center text-xs text-gray-400">
          Ваши данные надёжно защищены и не передаются третьим лицам.
        </p>
      </div>
    </div>
  )
}
