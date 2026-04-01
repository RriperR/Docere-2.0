import { Suspense, lazy } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'

import { ProtectedRoute } from './components/auth/ProtectedRoute'
import { RoleRoute } from './components/auth/RoleRoute'
import { LoadingScreen } from './components/common/LoadingScreen'
import { AuthLayout } from './components/layouts/AuthLayout'
import { DashboardLayout } from './components/layouts/DashboardLayout'
import { useAuthStore } from './stores/authStore'

const LoginPage = lazy(() => import('./pages/auth/LoginPage'))
const RegisterPage = lazy(() => import('./pages/auth/RegisterPage'))
const DoctorDashboard = lazy(() => import('./pages/dashboard/DoctorDashboard'))
const PatientDashboard = lazy(() => import('./pages/dashboard/PatientDashboard'))
const AdminDashboard = lazy(() => import('./pages/dashboard/AdminDashboard'))
const PatientListPage = lazy(() => import('./pages/patients/PatientListPage'))
const PatientDetailsPage = lazy(() => import('./pages/patients/PatientDetailsPage'))
const AdminPanelPage = lazy(() => import('./pages/admin/AdminPanelPage'))
const AccountSettings = lazy(() => import('./pages/settings/AccountSettingsPage'))
const NotFoundPage = lazy(() => import('./pages/NotFoundPage'))

function App() {
  const { isAuthenticated, user } = useAuthStore()

  return (
    <Suspense fallback={<LoadingScreen />}>
      <Routes>
        <Route element={<AuthLayout />}>
          <Route path="/auth/login" element={<LoginPage />} />
          <Route path="/auth/register" element={<RegisterPage />} />
        </Route>

        <Route element={<ProtectedRoute />}>
          <Route element={<DashboardLayout />}>
            <Route
              path="/dashboard"
              element={
                user?.role === 'doctor' ? (
                  <Navigate to="/dashboard/doctor" replace />
                ) : user?.role === 'patient' ? (
                  <Navigate to="/dashboard/patient" replace />
                ) : (
                  <Navigate to="/dashboard/admin" replace />
                )
              }
            />
            <Route
              path="/dashboard/doctor"
              element={
                <RoleRoute allowedRoles={['doctor']}>
                  <DoctorDashboard />
                </RoleRoute>
              }
            />
            <Route
              path="/dashboard/patient"
              element={
                <RoleRoute allowedRoles={['patient']}>
                  <PatientDashboard />
                </RoleRoute>
              }
            />
            <Route
              path="/dashboard/admin"
              element={
                <RoleRoute allowedRoles={['admin']}>
                  <AdminDashboard />
                </RoleRoute>
              }
            />

            <Route path="/patients" element={<PatientListPage />} />
            <Route path="/patients/:id" element={<PatientDetailsPage />} />
            <Route
              path="/admin"
              element={
                <RoleRoute allowedRoles={['admin']}>
                  <AdminPanelPage />
                </RoleRoute>
              }
            />
            <Route path="/settings" element={<AccountSettings />} />
          </Route>
        </Route>

        <Route
          path="/"
          element={
            isAuthenticated ? (
              <Navigate to="/dashboard" replace />
            ) : (
              <Navigate to="/auth/login" replace />
            )
          }
        />

        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </Suspense>
  )
}

export default App
