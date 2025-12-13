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
  Card,
  CardContent,
  Chip,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
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

export default function RemnaWavePage() {
  const [tabValue, setTabValue] = useState(0);

  const { data: system, isLoading: systemLoading } = useQuery({
    queryKey: ['remnawave', 'system'],
    queryFn: async () => {
      const response = await api.get('/remnawave/system');
      return response.data;
    },
  });

  const { data: users } = useQuery({
    queryKey: ['remnawave', 'users'],
    queryFn: async () => {
      const response = await api.get('/remnawave/users');
      return response.data;
    },
    enabled: tabValue === 1,
  });

  const { data: hosts } = useQuery({
    queryKey: ['remnawave', 'hosts'],
    queryFn: async () => {
      const response = await api.get('/remnawave/hosts');
      return response.data;
    },
    enabled: tabValue === 2,
  });

  const { data: nodes } = useQuery({
    queryKey: ['remnawave', 'nodes'],
    queryFn: async () => {
      const response = await api.get('/remnawave/nodes');
      return response.data;
    },
    enabled: tabValue === 3,
  });

  const { data: inbounds } = useQuery({
    queryKey: ['remnawave', 'inbounds'],
    queryFn: async () => {
      const response = await api.get('/remnawave/inbounds');
      return response.data;
    },
    enabled: tabValue === 4,
  });

  const handleTabChange = (_event: React.SyntheticEvent, newValue: number) => {
    setTabValue(newValue);
  };

  if (systemLoading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '50vh' }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box>
      <Paper sx={{ p: 3, mb: 3, borderRadius: 2 }}>
        <Typography variant="h4" fontWeight={600} gutterBottom>
          🌊 RemnaWave
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Управление VPN-панелью RemnaWave
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
          <Tab label="📊 Система" />
          <Tab label="👥 Пользователи" />
          <Tab label="🌐 Хосты" />
          <Tab label="🖥 Ноды" />
          <Tab label="📥 Inbounds" />
        </Tabs>

        <Box sx={{ p: 3 }}>
          {/* System Info */}
          <TabPanel value={tabValue} index={0}>
            <Typography variant="h6" gutterBottom>
              📊 Информация о системе
            </Typography>
            <Grid container spacing={3} sx={{ mt: 1 }}>
              <Grid item xs={12} md={6}>
                <Card variant="outlined">
                  <CardContent>
                    <Typography variant="subtitle2" color="text.secondary">Версия</Typography>
                    <Typography variant="h6">{system?.version || '-'}</Typography>
                  </CardContent>
                </Card>
              </Grid>
              <Grid item xs={12} md={6}>
                <Card variant="outlined">
                  <CardContent>
                    <Typography variant="subtitle2" color="text.secondary">Статус</Typography>
                    <Chip 
                      label={system?.status || 'Unknown'} 
                      color={system?.status === 'online' ? 'success' : 'error'}
                      size="small"
                    />
                  </CardContent>
                </Card>
              </Grid>
              <Grid item xs={12} md={4}>
                <Card variant="outlined">
                  <CardContent>
                    <Typography variant="subtitle2" color="text.secondary">Всего пользователей</Typography>
                    <Typography variant="h6">{system?.totalUsers || 0}</Typography>
                  </CardContent>
                </Card>
              </Grid>
              <Grid item xs={12} md={4}>
                <Card variant="outlined">
                  <CardContent>
                    <Typography variant="subtitle2" color="text.secondary">Активных</Typography>
                    <Typography variant="h6">{system?.activeUsers || 0}</Typography>
                  </CardContent>
                </Card>
              </Grid>
              <Grid item xs={12} md={4}>
                <Card variant="outlined">
                  <CardContent>
                    <Typography variant="subtitle2" color="text.secondary">Онлайн</Typography>
                    <Typography variant="h6">{system?.onlineUsers || 0}</Typography>
                  </CardContent>
                </Card>
              </Grid>
            </Grid>
          </TabPanel>

          {/* Users */}
          <TabPanel value={tabValue} index={1}>
            <Typography variant="h6" gutterBottom>
              👥 Пользователи RemnaWave
            </Typography>
            {users?.length > 0 ? (
              <TableContainer>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Username</TableCell>
                      <TableCell>Статус</TableCell>
                      <TableCell>Трафик</TableCell>
                      <TableCell>Истекает</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {users.map((user: { username: string; status: string; traffic: string; expiresAt: string }) => (
                      <TableRow key={user.username}>
                        <TableCell>{user.username}</TableCell>
                        <TableCell>
                          <Chip 
                            label={user.status} 
                            size="small"
                            color={user.status === 'active' ? 'success' : 'default'}
                          />
                        </TableCell>
                        <TableCell>{user.traffic}</TableCell>
                        <TableCell>{user.expiresAt}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            ) : (
              <Alert severity="info">Нет данных о пользователях</Alert>
            )}
          </TabPanel>

          {/* Hosts */}
          <TabPanel value={tabValue} index={2}>
            <Typography variant="h6" gutterBottom>
              🌐 Хосты
            </Typography>
            {hosts?.length > 0 ? (
              <Grid container spacing={2}>
                {hosts.map((host: { id: string; address: string; port: number; remark: string }) => (
                  <Grid item xs={12} md={6} key={host.id}>
                    <Card variant="outlined">
                      <CardContent>
                        <Typography variant="subtitle1" fontWeight={600}>{host.remark || host.address}</Typography>
                        <Typography variant="body2" color="text.secondary">
                          {host.address}:{host.port}
                        </Typography>
                      </CardContent>
                    </Card>
                  </Grid>
                ))}
              </Grid>
            ) : (
              <Alert severity="info">Нет данных о хостах</Alert>
            )}
          </TabPanel>

          {/* Nodes */}
          <TabPanel value={tabValue} index={3}>
            <Typography variant="h6" gutterBottom>
              🖥 Ноды
            </Typography>
            {nodes?.length > 0 ? (
              <Grid container spacing={2}>
                {nodes.map((node: { id: string; name: string; address: string; status: string }) => (
                  <Grid item xs={12} md={6} key={node.id}>
                    <Card variant="outlined">
                      <CardContent>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <Typography variant="subtitle1" fontWeight={600}>{node.name}</Typography>
                          <Chip 
                            label={node.status} 
                            size="small"
                            color={node.status === 'online' ? 'success' : 'error'}
                          />
                        </Box>
                        <Typography variant="body2" color="text.secondary">
                          {node.address}
                        </Typography>
                      </CardContent>
                    </Card>
                  </Grid>
                ))}
              </Grid>
            ) : (
              <Alert severity="info">Нет данных о нодах</Alert>
            )}
          </TabPanel>

          {/* Inbounds */}
          <TabPanel value={tabValue} index={4}>
            <Typography variant="h6" gutterBottom>
              📥 Inbounds
            </Typography>
            {inbounds?.length > 0 ? (
              <TableContainer>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Tag</TableCell>
                      <TableCell>Протокол</TableCell>
                      <TableCell>Порт</TableCell>
                      <TableCell>Статус</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {inbounds.map((inbound: { tag: string; protocol: string; port: number; enabled: boolean }) => (
                      <TableRow key={inbound.tag}>
                        <TableCell>{inbound.tag}</TableCell>
                        <TableCell>{inbound.protocol}</TableCell>
                        <TableCell>{inbound.port}</TableCell>
                        <TableCell>
                          <Chip 
                            label={inbound.enabled ? 'Включен' : 'Выключен'} 
                            size="small"
                            color={inbound.enabled ? 'success' : 'default'}
                          />
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            ) : (
              <Alert severity="info">Нет данных об inbounds</Alert>
            )}
          </TabPanel>
        </Box>
      </Paper>
    </Box>
  );
}