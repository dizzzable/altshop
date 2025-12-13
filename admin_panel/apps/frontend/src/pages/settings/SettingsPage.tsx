import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Box, Typography, Card, CardContent, Tabs, Tab, Alert, Snackbar,
  CircularProgress
} from '@mui/material';
import { api } from '../../api/client';

// Импорт вкладок настроек
import AccessSettingsTab from './tabs/AccessSettingsTab';
import NotificationsSettingsTab from './tabs/NotificationsSettingsTab';
import ReferralSettingsTab from './tabs/ReferralSettingsTab';
import PartnerSettingsTab from './tabs/PartnerSettingsTab';
import MultiSubscriptionSettingsTab from './tabs/MultiSubscriptionSettingsTab';
import GeneralSettingsTab from './tabs/GeneralSettingsTab';

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function TabPanel(props: TabPanelProps) {
  const { children, value, index, ...other } = props;
  return (
    <div role="tabpanel" hidden={value !== index} {...other}>
      {value === index && <Box sx={{ py: 3 }}>{children}</Box>}
    </div>
  );
}

export default function SettingsPage() {
  const [tabValue, setTabValue] = useState(0);
  const [snackbar, setSnackbar] = useState<{ open: boolean; message: string; severity: 'success' | 'error' }>({ open: false, message: '', severity: 'success' });

  const { data: settings, isLoading, error } = useQuery({
    queryKey: ['settings'],
    queryFn: async () => {
      const response = await api.get('/settings');
      return response.data;
    },
  });

  const showSuccess = (message: string) => {
    setSnackbar({ open: true, message, severity: 'success' });
  };

  const showError = (message: string) => {
    setSnackbar({ open: true, message, severity: 'error' });
  };

  const handleTabChange = (_event: React.SyntheticEvent, newValue: number) => {
    setTabValue(newValue);
  };

  if (isLoading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '50vh' }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="error">Ошибка загрузки настроек</Alert>
      </Box>
    );
  }

  return (
    <Box>
      <Box sx={{ mb: 3 }}>
        <Typography variant="h4" fontWeight={600} gutterBottom>
          🛠 Панель управления
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Управление настройками бота
        </Typography>
      </Box>

      <Card>
        <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
          <Tabs 
            value={tabValue} 
            onChange={handleTabChange}
            variant="scrollable"
            scrollButtons="auto"
          >
            <Tab label="🔐 Режим доступа" />
            <Tab label="🔔 Уведомления" />
            <Tab label="👥 Реф. система" />
            <Tab label="💼 Партнерка" />
            <Tab label="📦 Мультиподписка" />
            <Tab label="⚙️ Общие" />
          </Tabs>
        </Box>

        <CardContent>
          <TabPanel value={tabValue} index={0}>
            <AccessSettingsTab 
              settings={settings} 
              onSuccess={showSuccess} 
              onError={showError} 
            />
          </TabPanel>

          <TabPanel value={tabValue} index={1}>
            <NotificationsSettingsTab 
              settings={settings} 
              onSuccess={showSuccess} 
              onError={showError} 
            />
          </TabPanel>

          <TabPanel value={tabValue} index={2}>
            <ReferralSettingsTab 
              settings={settings} 
              onSuccess={showSuccess} 
              onError={showError} 
            />
          </TabPanel>

          <TabPanel value={tabValue} index={3}>
            <PartnerSettingsTab 
              settings={settings} 
              onSuccess={showSuccess} 
              onError={showError} 
            />
          </TabPanel>

          <TabPanel value={tabValue} index={4}>
            <MultiSubscriptionSettingsTab 
              settings={settings} 
              onSuccess={showSuccess} 
              onError={showError} 
            />
          </TabPanel>

          <TabPanel value={tabValue} index={5}>
            <GeneralSettingsTab 
              settings={settings} 
              onSuccess={showSuccess} 
              onError={showError} 
            />
          </TabPanel>
        </CardContent>
      </Card>

      <Snackbar 
        open={snackbar.open} 
        autoHideDuration={4000} 
        onClose={() => setSnackbar((s) => ({ ...s, open: false }))}
      >
        <Alert 
          severity={snackbar.severity} 
          onClose={() => setSnackbar((s) => ({ ...s, open: false }))}
        >
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Box>
  );
}