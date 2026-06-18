import { motion } from 'framer-motion'
import { ActivitySquare } from 'lucide-react'

export const LoadingScreen = () => {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-gray-50">
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="flex flex-col items-center"
      >
        <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-primary-600 shadow-lg">
          <motion.div
            animate={{ scale: [1, 1.08, 1] }}
            transition={{ duration: 1.8, repeat: Infinity, ease: 'easeInOut' }}
          >
            <ActivitySquare className="h-8 w-8 text-white" />
          </motion.div>
        </div>

        <motion.p
          className="mt-4 text-sm font-semibold text-gray-800"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.3 }}
        >
          Загрузка...
        </motion.p>

        <div className="mt-3 flex gap-1">
          {[0, 0.15, 0.3].map((delay) => (
            <motion.div
              key={delay}
              className="h-1.5 w-1.5 rounded-full bg-primary-400"
              animate={{ scale: [1, 1.5, 1], opacity: [0.5, 1, 0.5] }}
              transition={{ duration: 0.9, repeat: Infinity, delay }}
            />
          ))}
        </div>
      </motion.div>
    </div>
  )
}
