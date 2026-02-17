import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { CheckCircle, AlertTriangle } from 'lucide-react';
import { Card } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import api from '../../api/api';

interface BackendDoctor {
  id: number;
  user: {
    first_name: string;
    last_name: string;
    // если в будущем добавите поля specialization/hospital — можно расширить здесь
  };
}

interface Doctor {
  id: string;
  name: string;
}

const DoctorRequestPage: React.FC = () => {
  const navigate = useNavigate();

  const [doctors, setDoctors] = useState<Doctor[]>([]);
  const [selectedDoctors, setSelectedDoctors] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState<string | null>(null);

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 1) Загрузка списка врачей с сервера
  useEffect(() => {
    api.get<BackendDoctor[]>('/doctors/')
      .then(({ data }) => {
        const list = data.map((d) => ({
          id: String(d.id),
          name: `${d.user.first_name} ${d.user.last_name}`,
        }));
        setDoctors(list);
      })
      .catch((err) => {
        console.error(err);
        setFetchError('Не удалось загрузить список врачей.');
      })
      .finally(() => {
        setLoading(false);
      });
  }, []);

  const handleDoctorSelect = (doctorId: string) => {
    setSelectedDoctors((prev) =>
      prev.includes(doctorId)
        ? prev.filter((id) => id !== doctorId)
        : [...prev, doctorId]
    );
  };

  const handleSubmit = async () => {
    if (selectedDoctors.length === 0) {
      setError('Пожалуйста, выберите как минимум одного врача.');
      return;
    }
    setIsSubmitting(true);
    setError(null);

    try {
      // здесь замените на свой реальный эндпоинт отправки запроса
      await api.post('/doctor-requests/', { doctors: selectedDoctors });
      setIsSuccess(true);
      setTimeout(() => navigate('/dashboard'), 3000);
    } catch (err) {
      console.error(err);
      setError('Не удалось отправить запрос. Попробуйте снова.');
    } finally {
      setIsSubmitting(false);
    }
  };

  if (loading) {
    return <p>Загрузка врачей…</p>;
  }
  if (fetchError) {
    return <p className="text-red-500">{fetchError}</p>;
  }

  return (
    <div>
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="mb-8"
      >
        <h1 className="text-2xl font-bold text-gray-900">Request Doctor Role</h1>
        <p className="mt-1 text-gray-500">
          Select doctors to verify your medical credentials
        </p>
      </motion.div>

      {isSuccess ? (
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.5 }}
        >
          <Card>
            <div className="text-center py-8">
              <CheckCircle className="h-16 w-16 text-success-500 mx-auto mb-4" />
              <h2 className="text-2xl font-bold text-gray-900 mb-2">
                Request Submitted Successfully
              </h2>
              <p className="text-gray-500 mb-8">
                Your request has been sent to {selectedDoctors.length} doctor
                {selectedDoctors.length > 1 ? 's' : ''}. You will be notified once they review your application.
              </p>
              <Button variant="outline" onClick={() => navigate('/dashboard')}>
                Return to Dashboard
              </Button>
            </div>
          </Card>
        </motion.div>
      ) : (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2, duration: 0.5 }}
        >
          <Card>
            {error && (
              <div className="mb-6 p-4 bg-error-50 border border-error-200 rounded-md flex items-start">
                <AlertTriangle className="h-5 w-5 text-error-500 mr-2 flex-shrink-0" />
                <p className="text-sm text-error-700">{error}</p>
              </div>
            )}

            <div className="mb-6">
              <h3 className="text-lg font-medium text-gray-900 mb-2">
                Select Doctors for Verification
              </h3>
              <p className="text-gray-500 text-sm">
                Choose doctors who can verify your medical credentials.
              </p>
            </div>

            <div className="space-y-4 mb-8">
              {doctors.map((doctor) => (
                <div
                  key={doctor.id}
                  className={`border rounded-lg p-4 cursor-pointer transition-colors duration-200 ${
                    selectedDoctors.includes(doctor.id)
                      ? 'border-primary-500 bg-primary-50'
                      : 'border-gray-200 hover:border-primary-200 hover:bg-gray-50'
                  }`}
                  onClick={() => handleDoctorSelect(doctor.id)}
                >
                  <div className="flex items-center">
                    <input
                      type="checkbox"
                      checked={selectedDoctors.includes(doctor.id)}
                      onChange={() => handleDoctorSelect(doctor.id)}
                      className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded"
                    />
                    <div className="ml-3">
                      <p className="text-sm font-medium text-gray-900">
                        {doctor.name}
                      </p>
                    </div>
                  </div>
                </div>
              ))}
            </div>

            <div className="flex items-center justify-between">
              <p className="text-sm text-gray-500">
                Selected: {selectedDoctors.length} doctor
                {selectedDoctors.length !== 1 ? 's' : ''}
              </p>
              <div className="flex gap-3">
                <Button variant="outline" onClick={() => navigate('/dashboard')}>
                  Cancel
                </Button>
                <Button
                  variant="primary"
                  onClick={handleSubmit}
                  isLoading={isSubmitting}
                  disabled={selectedDoctors.length === 0}
                >
                  Submit Request
                </Button>
              </div>
            </div>
          </Card>
        </motion.div>
      )}
    </div>
  );
};

export default DoctorRequestPage;
