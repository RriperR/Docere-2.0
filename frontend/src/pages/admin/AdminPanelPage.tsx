import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { Users, Shield, FileText, AlertCircle, Search, Filter, ChevronLeft, ChevronRight } from 'lucide-react';
import { Card } from '../../components/common/Card';
import { Input } from '../../components/common/Input';
import { Button } from '../../components/common/Button';
import { Tabs } from '../../components/common/Tabs';

interface User {
  id: string;
  name: string;
  email: string;
  role: string;
  status: string;
  lastActive: string;
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
  action: string;
  user: string;
  target: string;
  timestamp: string;
  details: string;
}

const AdminPanelPage = () => {
  const [activeTab, setActiveTab] = useState('users');
  const [searchQuery, setSearchQuery] = useState('');
  const [currentPage, setCurrentPage] = useState(1);

  // Mock data
  const users: User[] = [
    {
      id: '1',
      name: 'John Doe',
      email: 'john.doe@example.com',
      role: 'doctor',
      status: 'active',
      lastActive: '2023-03-15T10:30:00'
    },
    {
      id: '2',
      name: 'Jane Smith',
      email: 'jane.smith@example.com',
      role: 'patient',
      status: 'active',
      lastActive: '2023-03-14T15:45:00'
    },
    // Add more mock users...
  ];

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

  const auditLogs: AuditLog[] = [
    {
      id: '1',
      action: 'Role Change',
      user: 'Admin',
      target: 'Dr. Alex Smith',
      timestamp: '2023-03-15T14:30:00',
      details: 'Changed role from patient to doctor'
    },
    // Add more mock logs...
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

  const renderUsersList = () => {
    return (
      <div>
        <div className="mb-6 flex flex-wrap gap-4">
          <Input
            placeholder="Search users..."
            icon={<Search className="h-5 w-5" />}
            value={searchQuery}
            onChange={(e) => handleSearch(e.target.value)}
            className="flex-1"
          />
          <Button
            variant="outline"
            icon={<Filter className="h-5 w-5" />}
          >
            Filters
          </Button>
        </div>

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
                  Last Active
                </th>
                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {users.map((user) => (
                <tr key={user.id}>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="flex items-center">
                      <div className="h-10 w-10 rounded-full bg-primary-100 flex items-center justify-center text-primary-700 font-medium">
                        {user.name.split(' ').map(n => n[0]).join('')}
                      </div>
                      <div className="ml-4">
                        <div className="text-sm font-medium text-gray-900">{user.name}</div>
                        <div className="text-sm text-gray-500">{user.email}</div>
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
                    {new Date(user.lastActive).toLocaleString()}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm">
                    <Button variant="outline" size="sm">
                      Edit
                    </Button>
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
              disabled={currentPage === 5} // Example total pages
            >
              Next
            </Button>
          </div>
          <div className="hidden sm:flex-1 sm:flex sm:items-center sm:justify-between">
            <div>
              <p className="text-sm text-gray-700">
                Showing <span className="font-medium">1</span> to{' '}
                <span className="font-medium">10</span> of{' '}
                <span className="font-medium">50</span> results
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
                {[1, 2, 3, 4, 5].map((page) => (
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
                  disabled={currentPage === 5}
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
        {auditLogs.map((log) => (
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
                {log.action}
              </p>
              <p className="text-sm text-gray-500">
                {log.user} performed action on {log.target}
              </p>
              <p className="text-sm text-gray-500 mt-1">
                {log.details}
              </p>
            </div>
            <div className="flex-shrink-0 text-sm text-gray-500">
              {new Date(log.timestamp).toLocaleString()}
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
