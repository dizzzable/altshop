import { useMemo } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider, CssBaseline } from '@mui/material';
import { createAppTheme } from './theme';
import { useAuthStore } from './stores/authStore';
import { useThemeStore } from './stores/themeStore';

// Layouts
import MainLayout from './layouts/MainLayout';
import AuthLayout from './layouts/AuthLayout';

// Pages
import LoginPage from './pages/auth/LoginPage';
import DashboardPage from './pages/dashboard/DashboardPage';
import StatisticsPage from './pages/statistics/StatisticsPage';
import UsersPage from './pages/users/UsersPage';
import UserDetailPage from './pages/users/UserDetailPage';
import PlansPage from './pages/plans/PlansPage';
import SubscriptionsPage from './pages/subscriptions/SubscriptionsPage';
import TransactionsPage from './pages/transactions/TransactionsPage';
import PromocodesPage from './pages/promocodes/PromocodesPage';
import SettingsPage from './pages/settings/SettingsPage';
import BroadcastPage from './pages/broadcast/BroadcastPage';
import GatewaysPage from './pages/gateways/GatewaysPage';
import BackupPage from './pages/backup/BackupPage';
import BotButtonsPage from './pages/bot-buttons/BotButtonsPage';
import BotAdminsPage from './pages/bot-admins/BotAdminsPage';
import BannersPage from './pages/banners/BannersPage';
import AuditPage from './pages/audit/AuditPage';
import AccessPage from './pages/access/AccessPage';
import RemnaWavePage from './pages/remnawave/RemnaWavePage';
import RemnaShopPage from './pages/remnashop/RemnaShopPage';
import ImportPage from './pages/import/ImportPage';

// Protected Route Component
const ProtectedRoute = ({ children }: { children: React.ReactNode }) => {
  const { isAuthenticated } = useAuthStore();
  
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  
  return <>{children}</>;
};

function App() {
  const { mode } = useThemeStore();
  const theme = useMemo(() => createAppTheme(mode), [mode]);

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Routes>
        {/* Auth Routes */}
        <Route element={<AuthLayout />}>
          <Route path="/login" element={<LoginPage />} />
        </Route>

        {/* Protected Routes */}
        <Route
          element={
            <ProtectedRoute>
              <MainLayout />
            </ProtectedRoute>
          }
        >
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/statistics" element={<StatisticsPage />} />
          <Route path="/users" element={<UsersPage />} />
          <Route path="/users/:id" element={<UserDetailPage />} />
          <Route path="/plans" element={<PlansPage />} />
          <Route path="/subscriptions" element={<SubscriptionsPage />} />
          <Route path="/transactions" element={<TransactionsPage />} />
          <Route path="/promocodes" element={<PromocodesPage />} />
          <Route path="/broadcast" element={<BroadcastPage />} />
          <Route path="/access" element={<AccessPage />} />
          <Route path="/remnawave" element={<RemnaWavePage />} />
          <Route path="/remnashop" element={<RemnaShopPage />} />
          <Route path="/import" element={<ImportPage />} />
          <Route path="/gateways" element={<GatewaysPage />} />
          <Route path="/backup" element={<BackupPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/bot-buttons" element={<BotButtonsPage />} />
          <Route path="/bot-admins" element={<BotAdminsPage />} />
          <Route path="/banners" element={<BannersPage />} />
          <Route path="/audit" element={<AuditPage />} />
        </Route>

        {/* Catch all */}
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </ThemeProvider>
  );
}

export default App;