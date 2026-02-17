import { Navigate } from 'react-router-dom';
import { useAuthStore, UserRole } from '../../stores/authStore';
import { LoadingScreen } from '../common/LoadingScreen';

interface RoleRouteProps {
  children: React.ReactNode;
  allowedRoles: UserRole[];
}

export const RoleRoute: React.FC<RoleRouteProps> = ({
  children,
  allowedRoles
}) => {
  const { user, isLoading } = useAuthStore();

  if (isLoading) {
    return <LoadingScreen />;
  }

  // If user role is not in the allowed roles, redirect to their dashboard
  if (user && !allowedRoles.includes(user.role)) {
    return <Navigate to={`/dashboard/${user.role}`} replace />;
  }

  return <>{children}</>;
};
