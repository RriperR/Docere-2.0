// src/App.tsx
import { Suspense, lazy } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { LoadingScreen }      from './components/common/LoadingScreen';
import { AuthLayout }         from './components/layouts/AuthLayout';
import { DashboardLayout }    from './components/layouts/DashboardLayout';
import { ProtectedRoute }     from './components/auth/ProtectedRoute';
import { RoleRoute }          from './components/auth/RoleRoute';
import { useAuthStore }       from './stores/authStore';

const LoginPage          = lazy(() => import('./pages/auth/LoginPage'));
const RegisterPage       = lazy(() => import('./pages/auth/RegisterPage'));
const DoctorDashboard    = lazy(() => import('./pages/dashboard/DoctorDashboard'));
const PatientDashboard   = lazy(() => import('./pages/dashboard/PatientDashboard'));
const AdminDashboard     = lazy(() => import('./pages/dashboard/AdminDashboard'));
const UploadPage         = lazy(() => import('./pages/upload/UploadPage'));
const UploadStatusPage   = lazy(() => import('./pages/upload/UploadStatusPage'));
const PatientListPage    = lazy(() => import('./pages/patients/PatientListPage'));
const PatientDetailsPage = lazy(() => import('./pages/patients/PatientDetailsPage'));
const DoctorRequestPage  = lazy(() => import('./pages/roles/DoctorRequestPage'));
const AdminPanelPage     = lazy(() => import('./pages/admin/AdminPanelPage'));
const AccountSettings    = lazy(() => import('./pages/settings/AccountSettingsPage'));
const ReviewRequestsPage = lazy(() => import('./pages/roles/ReviewRequestsPage'));
const NotFoundPage       = lazy(() => import('./pages/NotFoundPage'));
import { ShareRequestsPage } from './pages/shares/ShareRequestsPage';

function App() {
  const { isAuthenticated, user } = useAuthStore();

  return (
    <Suspense fallback={<LoadingScreen />}>
      <Routes>
        {/* 1) публичные */}
        <Route element={<AuthLayout />}>
          <Route path="/auth/login"    element={<LoginPage />} />
          <Route path="/auth/register" element={<RegisterPage />} />
        </Route>

        {/* 2) все остальное только для залогиненных */}
        <Route element={<ProtectedRoute />}>
          {/* 2.1) общий layout с меню + header */}
          <Route element={<DashboardLayout />}>
            {/* дашборды по ролям */}
            <Route path="/dashboard"
              element={
                user?.role === 'doctor'
                  ? <Navigate to="/dashboard/doctor" replace/>
                  : user?.role === 'patient'
                    ? <Navigate to="/dashboard/patient" replace/>
                    : <Navigate to="/dashboard/admin"   replace/>
              }
            />
            <Route path="/dashboard/doctor"  element={<RoleRoute allowedRoles={['doctor']}><DoctorDashboard/></RoleRoute>} />
            <Route path="/dashboard/patient" element={<RoleRoute allowedRoles={['patient']}><PatientDashboard/></RoleRoute>} />
            <Route path="/dashboard/admin"   element={<RoleRoute allowedRoles={['admin']}><AdminDashboard/></RoleRoute>} />

            {/* общий функционал */}
            <Route path="/upload"           element={<RoleRoute allowedRoles={['doctor','admin','patient']}><UploadPage/></RoleRoute>} />
            <Route path="/upload/status/:jobId" element={<UploadStatusPage/>} />

            <Route path="/patients"         element={<PatientListPage/>} />
            <Route path="/patients/:id"     element={<PatientDetailsPage/>} />

            <Route path="/roles/request"    element={<RoleRoute allowedRoles={['patient']}><DoctorRequestPage/></RoleRoute>} />
            <Route path="/roles/review"     element={<RoleRoute allowedRoles={['doctor']}><ReviewRequestsPage/></RoleRoute>} />
            <Route path="/admin"            element={<RoleRoute allowedRoles={['admin']}><AdminPanelPage/></RoleRoute>} />
            <Route path="/settings"         element={<AccountSettings />} />

            <Route path="/share-requests"  element={<ShareRequestsPage/>} />
          </Route>
        </Route>

        {/* корень --> дашбоард или логин */}
        <Route path="/" element={
          isAuthenticated
            ? <Navigate to="/dashboard" replace/>
            : <Navigate to="/auth/login" replace/>
        }/>

        {/* 404 */}
        <Route path="*" element={<NotFoundPage/>}/>
      </Routes>
    </Suspense>
  );
}

export default App;
