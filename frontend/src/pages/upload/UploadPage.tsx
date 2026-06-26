import { useState, useCallback, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useDropzone } from 'react-dropzone';
import { motion } from 'framer-motion';
import { Upload, FileText, X, AlertCircle, FileSearch, RefreshCw } from 'lucide-react';
import { Card } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { UploadJob, useUploadStore } from '../../stores/uploadStore';

type StatusFilter = UploadJob['status'] | 'all';
type SortOrder = 'newest' | 'oldest';

const statusLabel: Record<UploadJob['status'], string> = {
  queued: 'В очереди',
  running: 'Обработка',
  needs_review: 'Нужна проверка',
  completed: 'Завершено',
  completed_with_warnings: 'Завершено с предупреждениями',
  failed: 'Ошибка',
};

const UploadPage = () => {
  const navigate = useNavigate();
  const {
    currentUpload,
    setCurrentUpload,
    uploadFile,
    listJobs,
    jobs,
    isLoadingJobs,
    isUploading,
    progress,
    error,
  } = useUploadStore();
  const [uploadError, setUploadError] = useState('');
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');
  const [sortOrder, setSortOrder] = useState<SortOrder>('newest');
  const filteredJobs = jobs
    .filter((job) => statusFilter === 'all' || job.status === statusFilter)
    .sort((left, right) => {
      const diff = new Date(left.created_at).getTime() - new Date(right.created_at).getTime();
      return sortOrder === 'newest' ? -diff : diff;
    });

  useEffect(() => {
    void listJobs();
  }, [listJobs]);

  const onDrop = useCallback((acceptedFiles: File[]) => {
    if (acceptedFiles.length === 0) return;

    const file = acceptedFiles[0];

    const acceptedTypes = ['application/zip', 'application/x-zip-compressed'];
    const isZip = acceptedTypes.includes(file.type) || file.name.toLowerCase().endsWith('.zip');
    if (!isZip) {
      setUploadError('Выберите ZIP-архив.');
      return;
    }

    if (file.size > 200 * 1024 * 1024) {
      setUploadError('Файл слишком большой. Максимальный размер - 200 МБ.');
      return;
    }

    setUploadError('');
    setCurrentUpload(file);
  }, [setCurrentUpload]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    multiple: false,
    accept: {
      'application/zip': ['.zip'],
      'application/x-zip-compressed': ['.zip'],
    },
  });

  const handleUpload = async () => {
    if (!currentUpload) return;

    try {
      const jobId = await uploadFile(currentUpload);
      navigate(`/upload/status/${jobId}`);
    } catch {
      // Error is handled by the upload store
    }
  };

  const openJob = (job: UploadJob) => {
    navigate(job.status === 'needs_review' ? `/upload/review/${job.id}` : `/upload/status/${job.id}`);
  };

  const clearUpload = () => {
    setCurrentUpload(null);
    setUploadError('');
  };

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';

    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));

    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  return (
    <div>
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="mb-8"
      >
        <h1 className="text-2xl font-bold text-gray-900">Импорт архива</h1>
        <p className="mt-1 text-gray-500">
          Загрузите ZIP-архив с медицинскими данными пациента.
        </p>
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2, duration: 0.5 }}
      >
        <Card>
          {error && (
            <div className="mb-4 p-3 bg-error-50 border border-error-200 rounded-md flex items-start">
              <AlertCircle className="h-5 w-5 text-error-500 mr-2 flex-shrink-0 mt-0.5" />
              <p className="text-sm text-error-700">{error}</p>
            </div>
          )}

          {uploadError && (
            <div className="mb-4 p-3 bg-error-50 border border-error-200 rounded-md flex items-start">
              <AlertCircle className="h-5 w-5 text-error-500 mr-2 flex-shrink-0 mt-0.5" />
              <p className="text-sm text-error-700">{uploadError}</p>
            </div>
          )}

          {!currentUpload ? (
            <div
              {...getRootProps()}
              className={`border-2 border-dashed rounded-lg p-12 text-center cursor-pointer transition-colors duration-200 ${
                isDragActive
                  ? 'border-primary-500 bg-primary-50'
                  : 'border-gray-300 hover:border-primary-400 hover:bg-gray-50'
              }`}
            >
              <input {...getInputProps()} />
              <div className="flex flex-col items-center justify-center">
                <Upload
                  className={`h-12 w-12 mb-4 ${
                    isDragActive ? 'text-primary-500' : 'text-gray-400'
                  }`}
                />

                <p className="text-lg font-medium text-gray-700 mb-1">
                  {isDragActive
                    ? 'Отпустите архив здесь'
                    : 'Перетащите ZIP-архив сюда или выберите файл'}
                </p>
                <p className="text-sm text-gray-500 mb-4">
                  Поддерживается ZIP до 200 МБ
                </p>

                <Button
                  type="button"
                  variant="outline"
                  size="md"
                >
                  Выбрать файл
                </Button>
              </div>
            </div>
          ) : (
            <div className="border rounded-lg p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-medium text-gray-900">Выбранный архив</h3>
                {!isUploading && (
                  <button
                    onClick={clearUpload}
                    className="text-gray-400 hover:text-gray-500"
                  >
                    <X className="h-5 w-5" />
                  </button>
                )}
              </div>

              <div className="flex items-center p-4 bg-gray-50 rounded-md mb-6">
                <div className="bg-primary-100 p-3 rounded-md mr-4">
                  <FileText className="h-6 w-6 text-primary-600" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-900 truncate">
                    {currentUpload.name}
                  </p>
                  <p className="text-sm text-gray-500">
                    {formatFileSize(currentUpload.size)}
                  </p>
                </div>
              </div>

              {isUploading ? (
                <div className="mb-6">
                  <div className="flex justify-between text-sm font-medium text-gray-700 mb-1">
                    <span>Загрузка...</span>
                    <span>{progress}%</span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-2.5">
                    <div
                      className="bg-primary-600 h-2.5 rounded-full transition-all duration-300"
                      style={{ width: `${progress}%` }}
                    ></div>
                  </div>
                </div>
              ) : (
                <div className="flex justify-end">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={clearUpload}
                    className="mr-2"
                  >
                    Отмена
                  </Button>
                  <Button
                    type="button"
                    variant="primary"
                    onClick={handleUpload}
                  >
                    Загрузить
                  </Button>
                </div>
              )}
            </div>
          )}
        </Card>
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3, duration: 0.5 }}
        className="mt-8"
      >
        <Card
          title="Загруженные архивы"
          footer={
            <div className="flex justify-end">
              <Button
                type="button"
                variant="outline"
                size="sm"
                icon={<RefreshCw className="h-4 w-4" />}
                isLoading={isLoadingJobs}
                onClick={() => void listJobs()}
              >
                Обновить
              </Button>
            </div>
          }
        >
          <div className="mb-4 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <select
              value={statusFilter}
              onChange={(event) => setStatusFilter(event.target.value as StatusFilter)}
              className="rounded-md border border-gray-200 px-3 py-2 text-sm"
            >
              <option value="all">Все статусы</option>
              {Object.entries(statusLabel).map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
            <select
              value={sortOrder}
              onChange={(event) => setSortOrder(event.target.value as SortOrder)}
              className="rounded-md border border-gray-200 px-3 py-2 text-sm"
            >
              <option value="newest">Сначала новые</option>
              <option value="oldest">Сначала старые</option>
            </select>
          </div>
          {jobs.length === 0 ? (
            <p className="text-sm text-gray-500">Загруженных архивов пока нет.</p>
          ) : filteredJobs.length === 0 ? (
            <p className="text-sm text-gray-500">Архивов с выбранным статусом нет.</p>
          ) : (
            <div className="divide-y divide-gray-100">
              {filteredJobs.map((job) => (
                <div key={job.id} className="flex flex-col gap-3 py-3 md:flex-row md:items-center md:justify-between">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-gray-900">
                      {job.original_filename ?? 'archive.zip'}
                    </p>
                    <p className="text-xs text-gray-500">
                      {statusLabel[job.status]} · {new Date(job.created_at).toLocaleString()}
                    </p>
                    <p className="mt-1 text-xs text-gray-500">
                      Пациентов: {getPatientCount(job)} · Записей: {getRecordCount(job)} · Вложений: {getAttachmentCount(job)}
                    </p>
                  </div>
                  <Button
                    type="button"
                    variant={job.status === 'needs_review' ? 'primary' : 'outline'}
                    size="sm"
                    icon={job.status === 'needs_review' ? <FileSearch className="h-4 w-4" /> : <FileText className="h-4 w-4" />}
                    onClick={() => openJob(job)}
                  >
                    {job.status === 'needs_review' ? 'Проверить импорт' : 'Статус'}
                  </Button>
                </div>
              ))}
            </div>
          )}
        </Card>
      </motion.div>
    </div>
  );
};

function getPatientCount(job: UploadJob) {
  return Number(job.report_json.patients_created ?? job.report_json.patients?.length ?? 0);
}

function getRecordCount(job: UploadJob) {
  if (typeof job.report_json.records_created === 'number') return job.report_json.records_created;
  return job.report_json.patients?.reduce((sum, patient) => sum + patient.record_groups.length, 0) ?? 0;
}

function getAttachmentCount(job: UploadJob) {
  if (typeof job.report_json.attachments_created === 'number') return job.report_json.attachments_created;
  return job.report_json.patients?.reduce((sum, patient) => {
    return sum + patient.record_groups.reduce((inner, group) => inner + group.files.length, 0);
  }, 0) ?? 0;
}

export default UploadPage;
