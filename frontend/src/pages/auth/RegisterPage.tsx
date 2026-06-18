import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Calendar, Eye, EyeOff, Lock, Mail, Phone, User } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { Input } from '../../components/common/Input'
import { Button } from '../../components/common/Button'
import { useAuthStore } from '../../stores/authStore'

const registerSchema = z
  .object({
    firstName: z.string().min(1, 'Введите имя'),
    lastName: z.string().min(1, 'Введите фамилию'),
    middleName: z.string().optional().or(z.literal('')),
    phone: z
      .string()
      .min(5, 'Введите корректный телефон')
      .regex(/^\+?\d+$/, 'Только цифры и +'),
    email: z.string().email('Неверный email'),
    birthday: z
      .string()
      .optional()
      .or(z.literal(''))
      .refine((val) => !val || !isNaN(Date.parse(val)), 'Неверная дата'),
    password: z.string().min(8, 'Минимум 8 символов'),
    confirmPassword: z.string().min(1, 'Подтвердите пароль'),
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: 'Пароли не совпадают',
    path: ['confirmPassword'],
  })

type RegisterFormData = z.infer<typeof registerSchema>

function PasswordStrength({ password }: { password: string }) {
  const getStrength = (pwd: string): { score: number; label: string; color: string } => {
    if (!pwd) return { score: 0, label: '', color: '' }
    let score = 0
    if (pwd.length >= 8) score++
    if (/[A-Z]/.test(pwd)) score++
    if (/[0-9]/.test(pwd)) score++
    if (/[^A-Za-z0-9]/.test(pwd)) score++
    const levels = [
      { score: 0, label: '', color: '' },
      { score: 1, label: 'Слабый', color: 'bg-error-400' },
      { score: 2, label: 'Средний', color: 'bg-warning-400' },
      { score: 3, label: 'Хороший', color: 'bg-accent-400' },
      { score: 4, label: 'Сильный', color: 'bg-success-500' },
    ]
    return levels[score]
  }

  const { score, label, color } = getStrength(password)
  if (!password) return null

  return (
    <div className="mt-1.5 space-y-1">
      <div className="flex gap-1">
        {[1, 2, 3, 4].map((i) => (
          <div
            key={i}
            className={`h-1 flex-1 rounded-full transition-colors duration-300 ${
              i <= score ? color : 'bg-gray-200'
            }`}
          />
        ))}
      </div>
      {label && <p className={`text-xs font-medium ${score <= 1 ? 'text-error-600' : score === 2 ? 'text-warning-600' : score === 3 ? 'text-accent-600' : 'text-success-600'}`}>{label}</p>}
    </div>
  )
}

const RegisterPage = () => {
  const navigate = useNavigate()
  const { register: registerUser, isLoading, error } = useAuthStore()
  const [showPassword, setShowPassword] = useState(false)
  const [showConfirm, setShowConfirm] = useState(false)

  const {
    register: registerField,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm<RegisterFormData>({
    resolver: zodResolver(registerSchema),
  })

  const password = watch('password', '')

  const onSubmit = async (data: RegisterFormData) => {
    try {
      await registerUser(
        data.firstName,
        data.lastName,
        data.middleName || null,
        data.email,
        data.phone,
        data.birthday || null,
        data.password,
      )
      navigate('/dashboard')
    } catch {
      // ошибка в сторе
    }
  }

  return (
    <div>
      <div className="mb-6 text-center">
        <h2 className="text-2xl font-bold text-gray-900">Создайте аккаунт</h2>
        <p className="mt-1.5 text-sm text-gray-500">
          Уже есть аккаунт?{' '}
          <Link to="/auth/login" className="font-medium text-primary-600 hover:text-primary-700">
            Войдите
          </Link>
        </p>
      </div>

      <AnimatePresence>
        {error && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="mb-4 overflow-hidden rounded-lg border border-error-200 bg-error-50 px-4 py-3 text-sm text-error-700"
          >
            {error}
          </motion.div>
        )}
      </AnimatePresence>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <Input
            id="lastName"
            label="Фамилия *"
            icon={<User size={15} />}
            error={errors.lastName?.message}
            placeholder="Иванов"
            {...registerField('lastName')}
          />
          <Input
            id="firstName"
            label="Имя *"
            icon={<User size={15} />}
            error={errors.firstName?.message}
            placeholder="Иван"
            {...registerField('firstName')}
          />
        </div>

        <Input
          id="middleName"
          label="Отчество"
          icon={<User size={15} />}
          error={errors.middleName?.message}
          placeholder="Иванович (необязательно)"
          {...registerField('middleName')}
        />

        <Input
          id="email"
          type="email"
          label="Email *"
          placeholder="you@example.com"
          icon={<Mail size={15} />}
          error={errors.email?.message}
          {...registerField('email')}
        />

        <div className="grid grid-cols-2 gap-3">
          <Input
            id="phone"
            label="Телефон *"
            placeholder="+79991234567"
            icon={<Phone size={15} />}
            error={errors.phone?.message}
            {...registerField('phone')}
          />
          <Input
            id="birthday"
            type="date"
            label="Дата рождения"
            icon={<Calendar size={15} />}
            error={errors.birthday?.message}
            {...registerField('birthday')}
          />
        </div>

        <div className="relative">
          <Input
            id="password"
            type={showPassword ? 'text' : 'password'}
            label="Пароль *"
            placeholder="Минимум 8 символов"
            icon={<Lock size={15} />}
            error={errors.password?.message}
            {...registerField('password')}
          />
          <button
            type="button"
            onClick={() => setShowPassword((s) => !s)}
            className="absolute right-3 top-[34px] text-gray-400 hover:text-gray-600"
            tabIndex={-1}
          >
            {showPassword ? <EyeOff size={15} /> : <Eye size={15} />}
          </button>
          <PasswordStrength password={password} />
        </div>

        <div className="relative">
          <Input
            id="confirmPassword"
            type={showConfirm ? 'text' : 'password'}
            label="Подтвердите пароль *"
            placeholder="••••••••"
            icon={<Lock size={15} />}
            error={errors.confirmPassword?.message}
            {...registerField('confirmPassword')}
          />
          <button
            type="button"
            onClick={() => setShowConfirm((s) => !s)}
            className="absolute right-3 top-[34px] text-gray-400 hover:text-gray-600"
            tabIndex={-1}
          >
            {showConfirm ? <EyeOff size={15} /> : <Eye size={15} />}
          </button>
        </div>

        <Button type="submit" fullWidth isLoading={isLoading} size="lg">
          Зарегистрироваться
        </Button>
      </form>

      <p className="mt-4 text-center text-xs text-gray-400">
        Регистрируясь, вы соглашаетесь с{' '}
        <a href="#" className="text-primary-600 hover:underline">правилами</a> и{' '}
        <a href="#" className="text-primary-600 hover:underline">политикой конфиденциальности</a>.
      </p>
    </div>
  )
}

export default RegisterPage
