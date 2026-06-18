import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Eye, EyeOff, Lock, Mail } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { Input } from '../../components/common/Input'
import { Button } from '../../components/common/Button'
import { useAuthStore } from '../../stores/authStore'

const loginSchema = z.object({
  email: z.string().email('Введите корректный email'),
  password: z.string().min(1, 'Введите пароль'),
})

type LoginFormData = z.infer<typeof loginSchema>

const LoginPage = () => {
  const navigate = useNavigate()
  const { login, isLoading, error } = useAuthStore()
  const [showPassword, setShowPassword] = useState(false)
  const [hasError, setHasError] = useState(false)

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginFormData>({
    resolver: zodResolver(loginSchema),
  })

  const onSubmit = async (data: LoginFormData) => {
    setHasError(false)
    try {
      await login(data.email, data.password)
      navigate('/dashboard')
    } catch {
      setHasError(true)
    }
  }

  return (
    <div>
      <div className="mb-6 text-center">
        <h2 className="text-2xl font-bold text-gray-900">Вход в аккаунт</h2>
        <p className="mt-1.5 text-sm text-gray-500">
          Ещё нет аккаунта?{' '}
          <Link to="/auth/register" className="font-medium text-primary-600 hover:text-primary-700">
            Зарегистрируйтесь
          </Link>
        </p>
      </div>

      <AnimatePresence>
        {(error || hasError) && (
          <motion.div
            initial={{ opacity: 0, y: -4, height: 0 }}
            animate={{ opacity: 1, y: 0, height: 'auto' }}
            exit={{ opacity: 0, y: -4, height: 0 }}
            className="mb-4 overflow-hidden rounded-lg border border-error-200 bg-error-50 px-4 py-3 text-sm text-error-700"
          >
            {error || 'Неверный email или пароль. Попробуйте снова.'}
          </motion.div>
        )}
      </AnimatePresence>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <Input
          id="email"
          type="email"
          label="Email"
          placeholder="you@example.com"
          icon={<Mail size={16} />}
          error={errors.email?.message}
          autoComplete="email"
          {...register('email')}
        />

        <div className="relative">
          <Input
            id="password"
            type={showPassword ? 'text' : 'password'}
            label="Пароль"
            placeholder="••••••••"
            icon={<Lock size={16} />}
            error={errors.password?.message}
            autoComplete="current-password"
            {...register('password')}
          />
          <button
            type="button"
            onClick={() => setShowPassword((s) => !s)}
            className="absolute right-3 top-[34px] text-gray-400 hover:text-gray-600"
            tabIndex={-1}
          >
            {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
          </button>
        </div>

        <div className="flex items-center justify-between text-sm">
          <label className="flex cursor-pointer items-center gap-2 text-gray-600">
            <input
              type="checkbox"
              className="h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
            />
            Запомнить меня
          </label>
          <a href="#" className="font-medium text-primary-600 hover:text-primary-700">
            Забыли пароль?
          </a>
        </div>

        <Button type="submit" fullWidth isLoading={isLoading} size="lg">
          Войти
        </Button>
      </form>
    </div>
  )
}

export default LoginPage
