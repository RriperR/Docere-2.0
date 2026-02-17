import { Link, useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Mail, Lock, Phone, User, Calendar } from 'lucide-react';
import { motion } from 'framer-motion';
import { Input } from '../../components/common/Input';
import { Button } from '../../components/common/Button';
import { useAuthStore } from '../../stores/authStore';

const registerSchema = z
  .object({
    firstName: z.string().min(1, 'Введите имя'),
    lastName: z.string().min(1, 'Введите фамилию'),
    middleName: z.string().optional().or(z.literal('')).describe('Отчество'),
    phone: z
      .string()
      .min(5, 'Введите корректный телефон')
      .regex(/^\+?\d+$/, 'Телефон может содержать только цифры и +'),
    email: z.string().email('Неверный email'),
    birthday: z
      .string()
      .optional()
      .or(z.literal(''))
      .refine(val => !val || !isNaN(Date.parse(val)), 'Неверная дата'),
    password: z.string().min(6, 'Пароль минимум 6 символов'),
    confirmPassword: z.string().min(1, 'Подтвердите пароль'),
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: "Пароли не совпадают",
    path: ['confirmPassword'],
  });

type RegisterFormData = z.infer<typeof registerSchema>;

const RegisterPage: React.FC = () => {
  const navigate = useNavigate();
  const { register: registerUser, isLoading, error } = useAuthStore();

  const {
    register: registerField,
    handleSubmit,
    formState: { errors },
  } = useForm<RegisterFormData>({
    resolver: zodResolver(registerSchema),
  });

  const onSubmit = async (data: RegisterFormData) => {
    try {
      await registerUser(
        data.firstName,
        data.lastName,
        data.middleName || null,
        data.email,
        data.phone,
        data.birthday || null,
        data.password
      );
      navigate('/dashboard');
    } catch {
      // Ошибка уже сохранена в сторе и отображается ниже
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="max-w-md mx-auto px-4 py-8"
    >
      <h2 className="text-2xl font-bold text-center mb-4">
        Создайте аккаунт
      </h2>
      <p className="text-center text-sm text-gray-600 mb-6">
        Или{' '}
        <Link
          to="/auth/login"
          className="text-primary-600 hover:underline"
        >
          войдите в существующий
        </Link>
      </p>

      {error && (
        <div className="mb-4 p-3 bg-error-50 text-error-700 rounded">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <Input
          id="firstName"
          label="Имя"
          icon={<User className="h-5 w-5" />}
          error={errors.firstName?.message}
          {...registerField('firstName')}
        />

        <Input
          id="lastName"
          label="Фамилия"
          icon={<User className="h-5 w-5" />}
          error={errors.lastName?.message}
          {...registerField('lastName')}
        />

        <Input
          id="middleName"
          label="Отчество (необязательно)"
          icon={<User className="h-5 w-5" />}
          error={errors.middleName?.message}
          {...registerField('middleName')}
        />

        <Input
          id="phone"
          label="Телефон"
          placeholder="+7 123 456 78 90"
          icon={<Phone className="h-5 w-5" />}
          error={errors.phone?.message}
          {...registerField('phone')}
        />

        <Input
          id="email"
          type="email"
          label="Email"
          placeholder="you@example.com"
          icon={<Mail className="h-5 w-5" />}
          error={errors.email?.message}
          {...registerField('email')}
        />

        <Input
          id="birthday"
          type="date"
          label="Дата рождения (необязательно)"
          icon={<Calendar className="h-5 w-5" />}
          error={errors.birthday?.message}
          {...registerField('birthday')}
        />

        <Input
          id="password"
          type="password"
          label="Пароль"
          placeholder="••••••••"
          icon={<Lock className="h-5 w-5" />}
          error={errors.password?.message}
          {...registerField('password')}
        />

        <Input
          id="confirmPassword"
          type="password"
          label="Подтвердите пароль"
          placeholder="••••••••"
          icon={<Lock className="h-5 w-5" />}
          error={errors.confirmPassword?.message}
          {...registerField('confirmPassword')}
        />

        <Button
          type="submit"
          fullWidth
          isLoading={isLoading}
        >
          Зарегистрироваться
        </Button>
      </form>

      <p className="mt-6 text-center text-sm text-gray-500">
        Регистрируясь, вы соглашаетесь с нашими{' '}
        <a href="#" className="underline text-primary-600">
          правилами
        </a>{' '}
        и{' '}
        <a href="#" className="underline text-primary-600">
          политикой конфиденциальности
        </a>.
      </p>
    </motion.div>
  );
};

export default RegisterPage;
