import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Box,
  Typography,
  Paper,
  Tabs,
  Tab,
  CircularProgress,
  Alert,
  Grid,
  Divider,
} from '@mui/material';
import { api } from '../../api/client';

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

interface StatItemProps {
  label: string;
  value: string | number;
  prefix?: string;
}

function StatItem({ label, value, prefix = '•' }: StatItemProps) {
  return (
    <Typography variant="body1" sx={{ mb: 0.5 }}>
      {prefix} {label}: <strong>{value}</strong>
    </Typography>
  );
}

export default function StatisticsPage() {
  const [tabValue, setTabValue] = useState(0);

  const { data: stats, isLoading, error } = useQuery({
    queryKey: ['statistics'],
    queryFn: async () => {
      const response = await api.get('/dashboard/statistics');
      return response.data;
    },
  });

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
        <Alert severity="error">Ошибка загрузки статистики</Alert>
      </Box>
    );
  }

  return (
    <Box>
      <Paper sx={{ p: 3, mb: 3, borderRadius: 2 }}>
        <Typography variant="h4" fontWeight={600} gutterBottom>
          📊 Статистика
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Детальная статистика по всем разделам системы
        </Typography>
      </Paper>

      <Paper sx={{ borderRadius: 2 }}>
        <Tabs
          value={tabValue}
          onChange={handleTabChange}
          variant="scrollable"
          scrollButtons="auto"
          sx={{ borderBottom: 1, borderColor: 'divider' }}
        >
          <Tab label="👥 Пользователи" />
          <Tab label="💳 Транзакции" />
          <Tab label="📦 Подписки" />
          <Tab label="📋 Планы" />
          <Tab label="🎟 Промокоды" />
        </Tabs>

        <Box sx={{ p: 3 }}>
          {/* Users Statistics */}
          <TabPanel value={tabValue} index={0}>
            <Typography variant="h6" gutterBottom>
              📊 Статистика по пользователям
            </Typography>
            <Box sx={{ mt: 2 }}>
              <StatItem label="Всего" value={stats?.users?.total || 0} />
              <StatItem label="Новые за день" value={stats?.users?.newDaily || 0} />
              <StatItem label="Новые за неделю" value={stats?.users?.newWeekly || 0} />
              <StatItem label="Новые за месяц" value={stats?.users?.newMonthly || 0} />
              
              <Divider sx={{ my: 2 }} />
              
              <StatItem label="С подпиской" value={stats?.users?.withSubscription || 0} />
              <StatItem label="Без подписки" value={stats?.users?.withoutSubscription || 0} />
              <StatItem label="С пробным периодом" value={stats?.users?.withTrial || 0} />
              
              <Divider sx={{ my: 2 }} />
              
              <StatItem label="Заблокированные" value={stats?.users?.blocked || 0} />
              <StatItem label="Заблокировали бота" value={stats?.users?.botBlocked || 0} />
              
              <Divider sx={{ my: 2 }} />
              
              <StatItem label="Конверсия пользователей → покупка" value={`${stats?.users?.conversionRate || 0}%`} />
              <StatItem label="Конверсия пробников → подписка" value={`${stats?.users?.trialConversionRate || 0}%`} />
            </Box>
          </TabPanel>

          {/* Transactions Statistics */}
          <TabPanel value={tabValue} index={1}>
            <Typography variant="h6" gutterBottom>
              💳 Статистика по транзакциям
            </Typography>
            <Box sx={{ mt: 2 }}>
              <StatItem label="Всего транзакций" value={stats?.transactions?.total || 0} />
              <StatItem label="Успешных" value={stats?.transactions?.completed || 0} />
              <StatItem label="Бесплатных" value={stats?.transactions?.free || 0} />
              
              <Divider sx={{ my: 2 }} />
              
              <Typography variant="subtitle2" sx={{ mb: 1 }}>По платежным системам:</Typography>
              {stats?.transactions?.byGateway?.map((gateway: { name: string; total: number; income: number }) => (
                <Box key={gateway.name} sx={{ ml: 2, mb: 1 }}>
                  <Typography variant="body2" fontWeight={600}>{gateway.name}</Typography>
                  <Typography variant="body2" color="text.secondary">
                    Транзакций: {gateway.total} | Доход: {gateway.income}
                  </Typography>
                </Box>
              )) || <Typography variant="body2" color="text.secondary">Нет данных</Typography>}
            </Box>
          </TabPanel>

          {/* Subscriptions Statistics */}
          <TabPanel value={tabValue} index={2}>
            <Typography variant="h6" gutterBottom>
              📦 Статистика по подпискам
            </Typography>
            <Box sx={{ mt: 2 }}>
              <StatItem label="Активных подписок" value={stats?.subscriptions?.active || 0} />
              <StatItem label="Истекших" value={stats?.subscriptions?.expired || 0} />
              <StatItem label="Пробных активных" value={stats?.subscriptions?.trial || 0} />
              <StatItem label="Истекают в течение 7 дней" value={stats?.subscriptions?.expiringSoon || 0} />
              
              <Divider sx={{ my: 2 }} />
              
              <StatItem label="Безлимитных" value={stats?.subscriptions?.unlimited || 0} />
              <StatItem label="С лимитом трафика" value={stats?.subscriptions?.withTrafficLimit || 0} />
              <StatItem label="С лимитом устройств" value={stats?.subscriptions?.withDeviceLimit || 0} />
            </Box>
          </TabPanel>

          {/* Plans Statistics */}
          <TabPanel value={tabValue} index={3}>
            <Typography variant="h6" gutterBottom>
              📋 Статистика по планам
            </Typography>
            <Box sx={{ mt: 2 }}>
              {stats?.plans?.list?.map((plan: { name: string; totalSubs: number; activeSubs: number; income: string }) => (
                <Paper key={plan.name} variant="outlined" sx={{ p: 2, mb: 2 }}>
                  <Typography variant="subtitle1" fontWeight={600}>{plan.name}</Typography>
                  <Grid container spacing={2} sx={{ mt: 1 }}>
                    <Grid item xs={6}>
                      <Typography variant="body2" color="text.secondary">Всего подписок</Typography>
                      <Typography variant="body1">{plan.totalSubs}</Typography>
                    </Grid>
                    <Grid item xs={6}>
                      <Typography variant="body2" color="text.secondary">Активных</Typography>
                      <Typography variant="body1">{plan.activeSubs}</Typography>
                    </Grid>
                    <Grid item xs={12}>
                      <Typography variant="body2" color="text.secondary">Доход</Typography>
                      <Typography variant="body1">{plan.income}</Typography>
                    </Grid>
                  </Grid>
                </Paper>
              )) || <Typography variant="body2" color="text.secondary">Нет данных о планах</Typography>}
            </Box>
          </TabPanel>

          {/* Promocodes Statistics */}
          <TabPanel value={tabValue} index={4}>
            <Typography variant="h6" gutterBottom>
              🎟 Статистика по промокодам
            </Typography>
            <Box sx={{ mt: 2 }}>
              <StatItem label="Всего активаций" value={stats?.promocodes?.totalActivations || 0} />
              <StatItem label="Самый популярный" value={stats?.promocodes?.mostPopular || '-'} />
              
              <Divider sx={{ my: 2 }} />
              
              <Typography variant="subtitle2" sx={{ mb: 1 }}>Выдано по типам:</Typography>
              <StatItem label="Дней подписки" value={stats?.promocodes?.totalDays || 0} />
              <StatItem label="Трафика (ГБ)" value={stats?.promocodes?.totalTraffic || 0} />
              <StatItem label="Подписок" value={stats?.promocodes?.totalSubscriptions || 0} />
              <StatItem label="Персональных скидок" value={stats?.promocodes?.totalPersonalDiscounts || 0} />
              <StatItem label="Скидок на покупку" value={stats?.promocodes?.totalPurchaseDiscounts || 0} />
            </Box>
          </TabPanel>
        </Box>
      </Paper>
    </Box>
  );
}