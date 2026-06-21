import React, { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import {
  Calendar,
  Camera,
  Lock,
  Mail,
  Phone,
  Save,
  Shield,
  User,
} from 'lucide-react'
import { DateInput } from '../../components/common/DateInput'
import { Input } from '../../components/common/Input'
import { Button } from '../../components/common/Button'
import { useAuthStore } from '../../stores/authStore'

interface FormData {
  firstName: string
  lastName: string
  email: string
  phone: string
  dateOfBirth: string
  currentPassword: string
  newPassword: string
  confirmPassword: string
}

function getInitials(firstName?: string, lastName?: string): string {
  const a = firstName?.[0] ?? ''
  const b = lastName?.[0] ?? ''
  return (a + b).toUpperCase() || '?'
}

const roleLabel: Record<string, string> = {
  doctor: 'Врач',
  patient: 'Пациент',
  admin: 'Администратор',
}

const AccountSettingsPage: React.FC = () => {
  const { user, isLoading, updateProfile } = useAuthStore()
  const [isEditing, setIsEditing] = useState(false)
  const [saved, setSaved] = useState(false)
  const [formData, setFormData] = useState<FormData>({
    firstName: '',
    lastName: '',
    email: '',
    phone: '',
    dateOfBirth: '',
    currentPassword: '',
    newPassword: '',
    confirmPassword: '',
  })

  useEffect(() => {
    if (user) {
      setFormData({
        firstName: user.first_name,
        lastName: user.last_name,
        email: user.email,
        phone: user.phone || '',
        dateOfBirth: user.birthday || '',
        currentPassword: '',
        newPassword: '',
        confirmPassword: '',
      })
    }
  }, [user])

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target
    setFormData((prev) => ({ ...prev, [name]: value }))
  }

  const handleSave = async () => {
    try {
      await updateProfile({
        first_name: formData.firstName,
        last_name: formData.lastName,
        phone: formData.phone || null,
        birthday: formData.dateOfBirth || null,
      })
      setIsEditing(false)
      setSaved(true)
      setTimeout(() => setSaved(false), 3000)
    } catch {
      // ошибка в сторе
    }
  }

  if (isLoading || !user) {
    return (
      <div className="space-y-4 animate-pulse">
        <div className="h-8 w-48 rounded bg-gray-200" />
        <div className="h-40 rounded-xl bg-gray-200" />
      </div>
    )
  }

  const initials = getInitials(user.first_name, user.last_name)

  return (
    <div className="space-y-6">
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
      >
        <h1 className="text-2xl font-bold text-gray-900">Настройки аккаунта</h1>
        <p className="mt-0.5 text-sm text-gray-500">
          Управляйте личными данными и безопасностью аккаунта.
        </p>
      </motion.div>

      {saved && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: 'auto' }}
          exit={{ opacity: 0, height: 0 }}
          className="rounded-xl border border-success-200 bg-success-50 px-4 py-3 text-sm font-medium text-success-800"
        >
          Изменения сохранены успешно.
        </motion.div>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Avatar + role card */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1, duration: 0.4 }}
          className="flex flex-col items-center rounded-xl border border-gray-100 bg-white p-6 shadow-card text-center lg:col-span-1"
        >
          <div className="relative">
            <div className="flex h-20 w-20 items-center justify-center rounded-2xl bg-primary-600 text-3xl font-bold text-white">
              {initials}
            </div>
            <button className="absolute -bottom-2 -right-2 flex h-7 w-7 items-center justify-center rounded-full border-2 border-white bg-gray-200 text-gray-600 hover:bg-gray-300">
              <Camera className="h-3.5 w-3.5" />
            </button>
          </div>
          <h3 className="mt-4 text-base font-bold text-gray-900">
            {user.first_name} {user.last_name}
          </h3>
          <p className="mt-0.5 text-sm text-gray-500">{user.email}</p>
          <span className={`mt-3 inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold ${user.role === 'doctor' ? 'bg-accent-100 text-accent-700' : user.role === 'admin' ? 'bg-primary-100 text-primary-700' : 'bg-secondary-100 text-secondary-700'}`}>
            <Shield className="h-3 w-3" />
            {roleLabel[user.role] ?? user.role}
          </span>

          <div className="mt-5 w-full space-y-2 text-left">
            {[
              { label: 'Телефон', value: user.phone || 'Не указан' },
              { label: 'Дата рождения', value: user.birthday || 'Не указана' },
            ].map((item) => (
              <div key={item.label} className="flex justify-between text-sm">
                <span className="text-gray-400">{item.label}</span>
                <span className="font-medium text-gray-900">{item.value}</span>
              </div>
            ))}
          </div>
        </motion.div>

        {/* Personal info */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15, duration: 0.4 }}
          className="rounded-xl border border-gray-100 bg-white shadow-card lg:col-span-2"
        >
          <div className="flex items-center justify-between border-b border-gray-100 px-6 py-4">
            <div className="flex items-center gap-2">
              <User className="h-4 w-4 text-primary-500" />
              <h3 className="font-semibold text-gray-900">Личные данные</h3>
            </div>
            {!isEditing ? (
              <Button variant="outline" size="sm" onClick={() => setIsEditing(true)}>
                Редактировать
              </Button>
            ) : (
              <div className="flex gap-2">
                <Button variant="outline" size="sm" onClick={() => setIsEditing(false)}>
                  Отмена
                </Button>
                <Button size="sm" icon={<Save className="h-3.5 w-3.5" />} onClick={handleSave} isLoading={isLoading}>
                  Сохранить
                </Button>
              </div>
            )}
          </div>
          <div className="p-6">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Input
                label="Имя"
                name="firstName"
                value={formData.firstName}
                onChange={handleInputChange}
                disabled={!isEditing}
                icon={<User size={15} />}
              />
              <Input
                label="Фамилия"
                name="lastName"
                value={formData.lastName}
                onChange={handleInputChange}
                disabled={!isEditing}
                icon={<User size={15} />}
              />
              <Input
                label="Email"
                name="email"
                type="email"
                value={formData.email}
                disabled
                icon={<Mail size={15} />}
              />
              <Input
                label="Телефон"
                name="phone"
                value={formData.phone}
                onChange={handleInputChange}
                disabled={!isEditing}
                icon={<Phone size={15} />}
              />
              <DateInput
                label="Дата рождения"
                name="dateOfBirth"
                value={formData.dateOfBirth}
                onChange={(value) => setFormData((prev) => ({ ...prev, dateOfBirth: value ?? '' }))}
                disabled={!isEditing}
                icon={<Calendar size={15} />}
              />
              {user.role === 'doctor' && (
                <div className="flex items-center gap-2 rounded-xl bg-accent-50 px-4 py-3">
                  <Shield className="h-5 w-5 text-accent-600" />
                  <div>
                    <p className="text-sm font-semibold text-accent-800">Верифицированный врач</p>
                    <p className="text-xs text-accent-600">Роль подтверждена администратором</p>
                  </div>
                </div>
              )}
            </div>
          </div>
        </motion.div>

        {/* Change password */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2, duration: 0.4 }}
          className="rounded-xl border border-gray-100 bg-white shadow-card lg:col-span-3"
        >
          <div className="flex items-center gap-2 border-b border-gray-100 px-6 py-4">
            <Lock className="h-4 w-4 text-primary-500" />
            <h3 className="font-semibold text-gray-900">Изменить пароль</h3>
          </div>
          <div className="p-6">
            <div className="grid max-w-xl grid-cols-1 gap-4 sm:grid-cols-3">
              <Input
                label="Текущий пароль"
                name="currentPassword"
                type="password"
                value={formData.currentPassword}
                onChange={handleInputChange}
                icon={<Lock size={15} />}
              />
              <Input
                label="Новый пароль"
                name="newPassword"
                type="password"
                value={formData.newPassword}
                onChange={handleInputChange}
                icon={<Lock size={15} />}
              />
              <Input
                label="Подтвердить пароль"
                name="confirmPassword"
                type="password"
                value={formData.confirmPassword}
                onChange={handleInputChange}
                icon={<Lock size={15} />}
              />
            </div>
            <div className="mt-4">
              <Button
                size="sm"
                variant="outline"
                onClick={() => alert('Смена пароля будет реализована')}
              >
                Обновить пароль
              </Button>
            </div>
          </div>
        </motion.div>
      </div>
    </div>
  )
}

export default AccountSettingsPage
