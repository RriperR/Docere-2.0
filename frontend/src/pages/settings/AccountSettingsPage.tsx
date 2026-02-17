import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import {
  User as UserIcon,
  Mail,
  Lock as LockIcon,
  Phone,
  Calendar,
  Shield,
  Save,
} from 'lucide-react';
import { Card } from '../../components/common/Card';
import { Input } from '../../components/common/Input';
import { Button } from '../../components/common/Button';
import { useAuthStore } from '../../stores/authStore';

interface FormData {
  firstName: string;
  lastName: string;
  email: string;
  phone: string;
  dateOfBirth: string;
  currentPassword: string;
  newPassword: string;
  confirmPassword: string;
}

const AccountSettingsPage: React.FC = () => {
  const { user, isLoading, updateProfile } = useAuthStore();
  const [isEditing, setIsEditing] = useState(false);
  const [formData, setFormData] = useState<FormData>({
    firstName: '',
    lastName: '',
    email: '',
    phone: '',
    dateOfBirth: '',
    currentPassword: '',
    newPassword: '',
    confirmPassword: '',
  });

  // Инициализируем форму из стора
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
      });
    }
  }, [user]);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const handleSave = async () => {
    try {
      await updateProfile({
        first_name: formData.firstName,
        last_name: formData.lastName,
        phone: formData.phone || null,
        birthday: formData.dateOfBirth || null,
      });
      setIsEditing(false);
    } catch {
      // Ошибку мы уже сохранили в сторе, можно показать нотификацию
    }
  };

  if (isLoading || !user) {
    return <p>Loading profile...</p>;
  }

  return (
    <div>
      {/* Заголовок */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="mb-8"
      >
        <h1 className="text-2xl font-bold text-gray-900">
          Account Settings
        </h1>
        <p className="mt-1 text-gray-500">
          Manage your account information and preferences
        </p>
      </motion.div>

      <div className="space-y-6">
        {/* Personal Information */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2, duration: 0.5 }}
        >
          <Card
            title="Personal Information"
            icon={<UserIcon className="h-5 w-5" />}
            footer={
              <div className="flex justify-end">
                {isEditing ? (
                  <>
                    <Button
                      variant="outline"
                      onClick={() => setIsEditing(false)}
                      className="mr-2"
                    >
                      Cancel
                    </Button>
                    <Button
                      variant="primary"
                      onClick={handleSave}
                      icon={<Save className="h-4 w-4" />}
                    >
                      Save Changes
                    </Button>
                  </>
                ) : (
                  <Button
                    variant="outline"
                    onClick={() => setIsEditing(true)}
                  >
                    Edit Profile
                  </Button>
                )}
              </div>
            }
          >
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Input
                label="First Name"
                name="firstName"
                value={formData.firstName}
                onChange={handleInputChange}
                disabled={!isEditing}
                icon={<UserIcon className="h-4 w-4" />}
              />
              <Input
                label="Last Name"
                name="lastName"
                value={formData.lastName}
                onChange={handleInputChange}
                disabled={!isEditing}
                icon={<UserIcon className="h-4 w-4" />}
              />
              <Input
                label="Email"
                name="email"
                type="email"
                value={formData.email}
                disabled
                icon={<Mail className="h-4 w-4" />}
              />
              <Input
                label="Phone"
                name="phone"
                value={formData.phone}
                onChange={handleInputChange}
                disabled={!isEditing}
                icon={<Phone className="h-4 w-4" />}
              />
              <Input
                label="Date of Birth"
                name="dateOfBirth"
                type="date"
                value={formData.dateOfBirth}
                onChange={handleInputChange}
                disabled={!isEditing}
                icon={<Calendar className="h-4 w-4" />}
              />
              {user.role === 'doctor' && (
                <div className="flex items-center space-x-2 px-3 py-2 bg-primary-50 rounded-md">
                  <Shield className="h-5 w-5 text-primary-600" />
                  <span className="text-sm font-medium text-primary-700">
                    Verified Doctor
                  </span>
                </div>
              )}
            </div>
          </Card>
        </motion.div>

        {/* Change Password */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4, duration: 0.5 }}
        >
          <Card title="Change Password" icon={<LockIcon className="h-5 w-5" />}>
            <div className="space-y-4">
              <Input
                label="Current Password"
                name="currentPassword"
                type="password"
                value={formData.currentPassword}
                onChange={handleInputChange}
                icon={<LockIcon className="h-4 w-4" />}
              />
              <Input
                label="New Password"
                name="newPassword"
                type="password"
                value={formData.newPassword}
                onChange={handleInputChange}
                icon={<LockIcon className="h-4 w-4" />}
              />
              <Input
                label="Confirm New Password"
                name="confirmPassword"
                type="password"
                value={formData.confirmPassword}
                onChange={handleInputChange}
                icon={<LockIcon className="h-4 w-4" />}
              />
              <div className="flex justify-end">
                <Button
                  variant="primary"
                  onClick={() => {
                    // Если будет отдельный endpoint — можно аналогично вызвать метод из сторa
                    alert('Password change will be implemented here');
                  }}
                >
                  Update Password
                </Button>
              </div>
            </div>
          </Card>
        </motion.div>
      </div>
    </div>
  );
};

export default AccountSettingsPage;
