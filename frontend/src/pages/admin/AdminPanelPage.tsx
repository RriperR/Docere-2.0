import React, { useEffect, useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import { Users, Shield, FileText, AlertCircle, Search, Filter, ChevronLeft, ChevronRight } from 'lucide-react';
import { Card } from '../../components/common/Card';
import { Input } from '../../components/common/Input';
import { Button } from '../../components/common/Button';
import { Tabs } from '../../components/common/Tabs';
import api from '../../api/api';

interface User {
  id: string;
  fio: string;
  email: string;
  phone: string;
  date_of_birth: string | null;
  role: string;
  status: string;
  created_at: string;
  updated_at: string;
}

interface RoleRequest {
  id: string;
  user: {
    name: string;
    email: string;
    currentRole: string;
  };
  requestedRole: string;
  status: 'pending' | 'approved' | 'rejected';
  date: string;
  verifiers: string[];
}

interface AuditLog {
  id: string;
  actor_user_id: string | null;
  actor_fio: string | null;
  actor_email: string | null;
  event_type: string;
  entity_type: string;
  entity_id: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

const AdminPanelPage = () => {
  const [activeTab, setActiveTab] = useState('users');
  const [searchQuery, setSearchQuery] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [users, setUsers] = useState<User[]>([]);
  const [roleFilter, setRoleFilter] = useState('all');
  const [statusFilter, setStatusFilter] = useState('all');
  const [isUsersLoading, setIsUsersLoading] = useState(false);
  const [usersError, setUsersError] = useState<string | null>(null);
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
  const [isAuditLoading, setIsAuditLoading] = useState(false);
  const [auditError, setAuditError] = useState<string | null>(null);

  const pageSize = 10;

  const roleRequests: RoleRequest[] = [
    {
      id: '1',
      user: {
        name: 'Dr. Maria Johnson',
        email: 'maria.johnson@example.com',
        currentRole: 'patient'
      },
      requestedRole: 'doctor',
      status: 'pending',
      date: '2023-03-15T09:00:00',
      verifiers: ['Dr. Alex Smith', 'Dr. James Wilson']
    },
    // Add more mock requests...
  ];

  const tabs = [
    { id: 'users', label: 'Users', icon: <Users className="h-4 w-4" /> },
    { id: 'roles', label: 'Role Requests', icon: <Shield className="h-4 w-4" /> },
    { id: 'audit', label: 'Audit Log', icon: <FileText className="h-4 w-4" /> },
  ];

  const handleSearch = (query: string) => {
    setSearchQuery(query);
    setCurrentPage(1);
  };

  const handlePageChange = (page: number) => {
    setCurrentPage(page);
  };

  useEffect(() => {
    if (activeTab !== 'users') {
      return;
    }

    const loadUsers = async () => {
      setIsUsersLoading(true);
      setUsersError(null);
      try {
        const { data } = await api.get<User[]>('/admin/users', { params: { limit: 500 } });
        setUsers(data);
      } catch {
        setUsersError('Не удалось загрузить пользователей');
      } finally {
        setIsUsersLoading(false);
      }
    };

    void loadUsers();
  }, [activeTab]);

  useEffect(() => {
    if (activeTab !== 'audit') {
      return;
    }

    const loadAuditEvents = async () => {
      setIsAuditLoading(true);
      setAuditError(null);
      try {
        const { data } = await api.get<AuditLog[]>('/admin/audit-events', { params: { limit: 100 } });
        setAuditLogs(data);
      } catch {
        setAuditError('Не удалось загрузить audit log');
      } finally {
        setIsAuditLoading(false);
      }
    };

    void loadAuditEvents();
  }, [activeTab]);

  const filteredAuditLogs = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    if (!query) {
      return auditLogs;
    }
    return auditLogs.filter((log) => {
      const haystack = [
        log.actor_fio,
        log.actor_email,
        log.event_type,
        log.entity_type,
        log.entity_id,
        JSON.stringify(log.metadata_json),
      ]
        .filter(Boolean)
        .join(' ')
        .toLowerCase();
      return haystack.includes(query);
    });
  }, [auditLogs, searchQuery]);

  const filteredUsers = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    return users.filter((user) => {
      const matchesSearch =
        !query ||
        [user.fio, user.email, user.phone, user.role, user.status].join(' ').toLowerCase().includes(query);
      const matchesRole = roleFilter === 'all' || user.role === roleFilter;
      const matchesStatus = statusFilter === 'all' || user.status === statusFilter;
      return matchesSearch && matchesRole && matchesStatus;
    });
  }, [roleFilter, searchQuery, statusFilter, users]);

  const totalUserPages = Math.max(1, Math.ceil(filteredUsers.length / pageSize));
  const pagedUsers = filteredUsers.slice((currentPage - 1) * pageSize, currentPage * pageSize);
  const userRangeStart = filteredUsers.length === 0 ? 0 : (currentPage - 1) * pageSize + 1;
  const userRangeEnd = Math.min(currentPage * pageSize, filteredUsers.length);

  useEffect(() => {
    if (currentPage > totalUserPages) {
      setCurrentPage(totalUserPages);
    }
  }, [currentPage, totalUserPages]);

  const formatAuditDate = (value: string) =>
    new Intl.DateTimeFormat('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    }).format(new Date(value));

  const formatMetadata = (metadata: Record<string, unknown>) => {
    const entries = Object.entries(metadata).filter(([, value]) => value !== null && value !== undefined);
    if (entries.length === 0) {
      return 'Без дополнительных данных';
    }
    return entries
      .slice(0, 4)
      .map(([key, value]) => `${key}: ${typeof value === 'object' ? JSON.stringify(value) : String(value)}`)
      .join(', ');
  };

  const formatDateTime = (value: string) =>
    new Intl.DateTimeFormat('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    }).format(new Date(value));

  const getInitials = (fio: string) =>
    fio
      .split(' ')
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part[0])
      .join('')
      .toUpperCase();

  const renderUsersList = () => {
    return (
      <div>
        <div className="mb-6 flex flex-wrap gap-4">
          <Input
            placeholder="Поиск по ФИО, email, телефону"
            icon={<Search className="h-5 w-5" />}
            value={searchQuery}
            onChange={(e) => handleSearch(e.target.value)}
            className="flex-1"
          />
          <div className="flex items-center gap-2">
            <Filter className="h-5 w-5 text-gray-400" />
            <select
              value={roleFilter}
              onChange={(event) => {
                setRoleFilter(event.target.value);
                setCurrentPage(1);
              }}
              className="rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-700"
            >
              <option value="all">Все роли</option>
              <option value="admin">Администраторы</option>
              <option value="doctor">Врачи</option>
              <option value="patient">Пациенты</option>
            </select>
            <select
              value={statusFilter}
              onChange={(event) => {
                setStatusFilter(event.target.value);
                setCurrentPage(1);
              }}
              className="rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-700"
            >
              <option value="all">Все статусы</option>
              <option value="active">Активные</option>
              <option value="blocked">Заблокированные</option>
            </select>
          </div>
        </div>

        {isUsersLoading && (
          <div className="rounded-md border border-gray-200 p-4 text-sm text-gray-500">
            Загрузка пользователей...
          </div>
        )}

        {usersError && (
          <div className="rounded-md border border-error-200 bg-error-50 p-4 text-sm text-error-700">
            {usersError}
          </div>
        )}

        {!isUsersLoading && !usersError && filteredUsers.length === 0 && (
          <div className="rounded-md border border-gray-200 p-4 text-sm text-gray-500">
            Пользователей не найдено
          </div>
        )}

        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  User
                </th>
                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Role
                </th>
                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Status
                </th>
                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Created
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {pagedUsers.map((user) => (
                <tr key={user.id}>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="flex items-center">
                      <div className="h-10 w-10 rounded-full bg-primary-100 flex items-center justify-center text-primary-700 font-medium">
                        {getInitials(user.fio)}
                      </div>
                      <div className="ml-4">
                        <div className="text-sm font-medium text-gray-900">{user.fio}</div>
                        <div className="text-sm text-gray-500">{user.email}</div>
                        <div className="text-xs text-gray-400">{user.phone}</div>
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-primary-100 text-primary-800">
                      {user.role}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${
                      user.status === 'active'
                        ? 'bg-success-100 text-success-800'
                        : 'bg-gray-100 text-gray-800'
                    }`}>
                      {user.status}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {formatDateTime(user.created_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="mt-4 flex items-center justify-between">
          <div className="flex-1 flex justify-between sm:hidden">
            <Button
              variant="outline"
              onClick={() => handlePageChange(currentPage - 1)}
              disabled={currentPage === 1}
            >
              Previous
            </Button>
            <Button
              variant="outline"
              onClick={() => handlePageChange(currentPage + 1)}
              disabled={currentPage === totalUserPages}
            >
              Next
            </Button>
          </div>
          <div className="hidden sm:flex-1 sm:flex sm:items-center sm:justify-between">
            <div>
              <p className="text-sm text-gray-700">
                Showing <span className="font-medium">{userRangeStart}</span> to{' '}
                <span className="font-medium">{userRangeEnd}</span> of{' '}
                <span className="font-medium">{filteredUsers.length}</span> results
              </p>
            </div>
            <div>
              <nav className="relative z-0 inline-flex rounded-md shadow-sm -space-x-px">
                <button
                  onClick={() => handlePageChange(currentPage - 1)}
                  disabled={currentPage === 1}
                  className="relative inline-flex items-center px-2 py-2 rounded-l-md border border-gray-300 bg-white text-sm font-medium text-gray-500 hover:bg-gray-50"
                >
                  <span className="sr-only">Previous</span>
                  <ChevronLeft className="h-5 w-5" />
                </button>
                {Array.from({ length: totalUserPages }, (_, index) => index + 1).map((page) => (
                  <button
                    key={page}
                    onClick={() => handlePageChange(page)}
                    className={`relative inline-flex items-center px-4 py-2 border text-sm font-medium ${
                      page === currentPage
                        ? 'z-10 bg-primary-50 border-primary-500 text-primary-600'
                        : 'bg-white border-gray-300 text-gray-500 hover:bg-gray-50'
                    }`}
                  >
                    {page}
                  </button>
                ))}
                <button
                  onClick={() => handlePageChange(currentPage + 1)}
                  disabled={currentPage === totalUserPages}
                  className="relative inline-flex items-center px-2 py-2 rounded-r-md border border-gray-300 bg-white text-sm font-medium text-gray-500 hover:bg-gray-50"
                >
                  <span className="sr-only">Next</span>
                  <ChevronRight className="h-5 w-5" />
                </button>
              </nav>
            </div>
          </div>
        </div>
      </div>
    );
  };

  const renderRoleRequests = () => {
    return (
      <div className="space-y-6">
        {roleRequests.map((request) => (
          <Card key={request.id}>
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-lg font-medium text-gray-900">
                  {request.user.name}
                </h3>
                <p className="text-sm text-gray-500">
                  Requesting change from {request.user.currentRole} to {request.requestedRole}
                </p>
                <p className="text-sm text-gray-500 mt-1">
                  Submitted on {new Date(request.date).toLocaleDateString()}
                </p>
              </div>
              <div className="flex gap-2">
                <Button variant="outline" size="sm">
                  Reject
                </Button>
                <Button variant="primary" size="sm">
                  Approve
                </Button>
              </div>
            </div>

            <div className="mt-4">
              <p className="text-sm font-medium text-gray-500">Verifying Doctors:</p>
              <div className="mt-2 flex flex-wrap gap-2">
                {request.verifiers.map((verifier, index) => (
                  <span
                    key={index}
                    className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-primary-100 text-primary-800"
                  >
                    {verifier}
                  </span>
                ))}
              </div>
            </div>
          </Card>
        ))}
      </div>
    );
  };

  const renderAuditLog = () => {
    return (
      <div className="space-y-4">
        <div className="flex flex-wrap gap-4">
          <Input
            placeholder="Поиск по пользователю, действию или сущности"
            icon={<Search className="h-5 w-5" />}
            value={searchQuery}
            onChange={(e) => handleSearch(e.target.value)}
            className="flex-1"
          />
        </div>

        {isAuditLoading && (
          <div className="rounded-md border border-gray-200 p-4 text-sm text-gray-500">
            Загрузка audit log...
          </div>
        )}

        {auditError && (
          <div className="rounded-md border border-error-200 bg-error-50 p-4 text-sm text-error-700">
            {auditError}
          </div>
        )}

        {!isAuditLoading && !auditError && filteredAuditLogs.length === 0 && (
          <div className="rounded-md border border-gray-200 p-4 text-sm text-gray-500">
            Событий пока нет
          </div>
        )}

        {filteredAuditLogs.map((log) => (
          <div
            key={log.id}
            className="flex items-start space-x-3 p-4 border rounded-lg hover:bg-gray-50 transition-colors duration-200"
          >
            <div className="flex-shrink-0">
              <div className="h-8 w-8 rounded-full bg-gray-100 flex items-center justify-center">
                <AlertCircle className="h-4 w-4 text-gray-500" />
              </div>
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-gray-900">
                {log.event_type}
              </p>
              <p className="text-sm text-gray-500">
                {log.actor_fio ?? 'Системное событие'}
                {log.actor_email ? ` (${log.actor_email})` : ''} {'->'} {log.entity_type} {log.entity_id}
              </p>
              <p className="text-sm text-gray-500 mt-1">
                {formatMetadata(log.metadata_json)}
              </p>
            </div>
            <div className="flex-shrink-0 text-sm text-gray-500">
              {formatAuditDate(log.created_at)}
            </div>
          </div>
        ))}
      </div>
    );
  };

  return (
    <div>
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="mb-8"
      >
        <h1 className="text-2xl font-bold text-gray-900">Admin Panel</h1>
        <p className="mt-1 text-gray-500">
          Manage users, role requests, and system activity
        </p>
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2, duration: 0.5 }}
      >
        <Card>
          <Tabs
            tabs={tabs}
            defaultTab="users"
            onChange={setActiveTab}
            className="mb-6"
          />

          {activeTab === 'users' && renderUsersList()}
          {activeTab === 'roles' && renderRoleRequests()}
          {activeTab === 'audit' && renderAuditLog()}
        </Card>
      </motion.div>
    </div>
  );
};

export default AdminPanelPage;
