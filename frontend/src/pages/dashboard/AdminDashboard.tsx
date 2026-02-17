import React, { useEffect } from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Users, ShieldCheck, FileText, AlertCircle } from 'lucide-react';
import { Card } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { useAuthStore } from '../../stores/authStore';
import { usePatientsStore } from '../../stores/patientsStore';

const AdminDashboard = () => {
  const { user } = useAuthStore();
  const { patients, fetchPatients } = usePatientsStore();

  useEffect(() => {
    fetchPatients();
  }, [fetchPatients]);

  // Mock data for audit logs
  const auditLogs = [
    {
      id: 'log1',
      action: 'User role changed',
      user: 'Maria Johnson',
      targetUser: 'John Smith',
      timestamp: '2023-03-15 14:30:22',
      details: 'Changed role from patient to doctor'
    },
    {
      id: 'log2',
      action: 'Patient record accessed',
      user: 'Dr. Alex Smith',
      targetUser: 'Emily Williams',
      timestamp: '2023-03-15 13:45:11',
      details: 'Viewed medical history'
    },
    {
      id: 'log3',
      action: 'New patient registered',
      user: 'System',
      targetUser: 'Michael Brown',
      timestamp: '2023-03-15 10:12:05',
      details: 'Self-registration completed'
    },
    {
      id: 'log4',
      action: 'Record modified',
      user: 'Dr. Maria Johnson',
      targetUser: 'John Doe',
      timestamp: '2023-03-14 16:22:45',
      details: 'Updated diagnosis information'
    },
    {
      id: 'log5',
      action: 'Login failed',
      user: 'Unknown',
      targetUser: 'N/A',
      timestamp: '2023-03-14 08:17:33',
      details: 'Multiple failed login attempts'
    }
  ];

  // User statistics
  const userStats = {
    total: 145,
    doctors: 32,
    patients: 110,
    admins: 3
  };

  // Role request statistics
  const roleRequests = {
    pending: 8,
    approved: 24,
    rejected: 5
  };

  const container = {
    hidden: { opacity: 0 },
    show: {
      opacity: 1,
      transition: {
        staggerChildren: 0.1
      }
    }
  };

  const item = {
    hidden: { opacity: 0, y: 20 },
    show: { opacity: 1, y: 0 }
  };

  return (
    <div>
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="mb-8"
      >
        <h1 className="text-2xl font-bold text-gray-900">
          Admin Dashboard
        </h1>
        <p className="mt-1 text-gray-500">
          Monitor system activity and manage users.
        </p>
      </motion.div>

      <motion.div
        variants={container}
        initial="hidden"
        animate="show"
        className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3 mb-8"
      >
        <motion.div variants={item}>
          <Card
            icon={<Users className="h-5 w-5" />}
            title="Users"
            hoverable
            onClick={() => window.location.href = '/admin'}
            className="h-full"
          >
            <div className="grid grid-cols-2 gap-2 mb-4">
              <div>
                <p className="text-sm text-gray-500">Total Users</p>
                <p className="text-2xl font-bold text-primary-600">{userStats.total}</p>
              </div>
              <div>
                <p className="text-sm text-gray-500">Doctors</p>
                <p className="text-lg font-semibold text-gray-700">{userStats.doctors}</p>
              </div>
              <div>
                <p className="text-sm text-gray-500">Patients</p>
                <p className="text-lg font-semibold text-gray-700">{userStats.patients}</p>
              </div>
              <div>
                <p className="text-sm text-gray-500">Admins</p>
                <p className="text-lg font-semibold text-gray-700">{userStats.admins}</p>
              </div>
            </div>
            <Button variant="outline" size="sm">
              Manage Users
            </Button>
          </Card>
        </motion.div>

        <motion.div variants={item}>
          <Card
            icon={<ShieldCheck className="h-5 w-5" />}
            title="Role Requests"
            hoverable
            onClick={() => window.location.href = '/admin'}
            className="h-full"
          >
            <div className="grid grid-cols-3 gap-2 mb-4">
              <div>
                <p className="text-sm text-gray-500">Pending</p>
                <p className="text-2xl font-bold text-warning-500">{roleRequests.pending}</p>
              </div>
              <div>
                <p className="text-sm text-gray-500">Approved</p>
                <p className="text-lg font-semibold text-success-600">{roleRequests.approved}</p>
              </div>
              <div>
                <p className="text-sm text-gray-500">Rejected</p>
                <p className="text-lg font-semibold text-error-600">{roleRequests.rejected}</p>
              </div>
            </div>
            <Button variant="primary" size="sm">
              Review Requests
            </Button>
          </Card>
        </motion.div>

        <motion.div variants={item}>
          <Card
            icon={<FileText className="h-5 w-5" />}
            title="System Status"
            hoverable
            className="h-full"
          >
            <div className="space-y-2 mb-4">
              <div className="flex justify-between">
                <span className="text-sm text-gray-600">Database</span>
                <span className="text-sm font-medium text-success-600">Online</span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm text-gray-600">Storage</span>
                <span className="text-sm font-medium text-success-600">84% free</span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm text-gray-600">Processing Queue</span>
                <span className="text-sm font-medium text-success-600">No backlog</span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm text-gray-600">API Services</span>
                <span className="text-sm font-medium text-success-600">Operational</span>
              </div>
            </div>
            <Button variant="outline" size="sm">
              View System Logs
            </Button>
          </Card>
        </motion.div>
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3, duration: 0.5 }}
      >
        <Card
          title="Recent Audit Logs"
          icon={<AlertCircle className="h-5 w-5" />}
        >
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Action
                  </th>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    User
                  </th>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Target
                  </th>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Timestamp
                  </th>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Details
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {auditLogs.map((log) => (
                  <tr key={log.id} className="hover:bg-gray-50 transition-colors duration-200">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm font-medium text-gray-900">{log.action}</div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm text-gray-500">{log.user}</div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm text-gray-500">{log.targetUser}</div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm text-gray-500">{log.timestamp}</div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm text-gray-500">{log.details}</div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="mt-4 flex justify-end">
            <Button variant="outline" size="sm">View All Logs</Button>
          </div>
        </Card>
      </motion.div>
    </div>
  );
};

export default AdminDashboard;
