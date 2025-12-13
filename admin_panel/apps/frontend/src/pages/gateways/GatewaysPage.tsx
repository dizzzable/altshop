import { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Paper,
  Button,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Switch,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Chip,
  Alert,
  LinearProgress,
  Tooltip,
  Card,
  CardContent,
  Grid,
} from '@mui/material';
import {
  Settings as SettingsIcon,
  ArrowUpward as ArrowUpIcon,
  ArrowDownward as ArrowDownIcon,
  Refresh as RefreshIcon,
  CheckCircle as ConfiguredIcon,
  Warning as NotConfiguredIcon,
  Payment as PaymentIcon,
} from '@mui/icons-material';
import apiClient from '../../api/client';

interface GatewaySettings {
  api_key?: string;
  secret_key?: string;
  shop_id?: string;
  is_configure?: boolean;
  [key: string]: unknown;
}

interface PaymentGateway {
  id: number;
  order_index: number;
  type: string;
  currency: string;
  is_active: boolean;
  settings: GatewaySettings | null;
}

const gatewayLabels: Record<string, string> = {
  TELEGRAM_STARS: 'Telegram Stars',
  YOOKASSA: 'YooKassa',
  YOOMONEY: 'YooMoney',
  CRYPTOMUS: 'Cryptomus',
  HELEKET: 'Heleket',
  CRYPTOPAY: 'CryptoPay',
  ROBOKASSA: 'Robokassa',
  PAL24: 'Pal24',
  WATA: 'Wata',
  PLATEGA: 'Platega',
};

const currencySymbols: Record<string, string> = {
  USD: '$',
  XTR: '★',
  RUB: '₽',
  USDT: '₮',
  TON: '💎',
  BTC: '₿',
  ETH: 'Ξ',
  LTC: 'Ł',
};

const gatewayFields: Record<string, string[]> = {
  TELEGRAM_STARS: [],
  YOOKASSA: ['shop_id', 'secret_key'],
  YOOMONEY: ['api_key'],
  CRYPTOMUS: ['api_key', 'shop_id'],
  HELEKET: ['api_key'],
  CRYPTOPAY: ['api_key'],
  ROBOKASSA: ['shop_id', 'secret_key'],
  PAL24: ['api_key', 'shop_id'],
  WATA: ['api_key'],
  PLATEGA: ['api_key', 'shop_id'],
};

export default function GatewaysPage() {
  const [gateways, setGateways] = useState<PaymentGateway[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [settingsDialogOpen, setSettingsDialogOpen] = useState(false);
  const [selectedGateway, setSelectedGateway] = useState<PaymentGateway | null>(null);
  const [editSettings, setEditSettings] = useState<Record<string, string>>({});

  const fetchGateways = async () => {
    try {
      setLoading(true);
      const response = await apiClient.get('/gateways');
      setGateways(response.data);
    } catch (err) {
      console.error('Error fetching gateways:', err);
      setError('Ошибка загрузки платёжных шлюзов');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchGateways();
  }, []);

  const handleToggle = async (id: number) => {
    try {
      await apiClient.post(`/gateways/${id}/toggle`);
      fetchGateways();
    } catch (err) {
      console.error('Error toggling gateway:', err);
      setError('Ошибка изменения статуса');
    }
  };

  const handleMoveUp = async (id: number) => {
    try {
      await apiClient.post(`/gateways/${id}/move-up`);
      fetchGateways();
    } catch (err) {
      console.error('Error moving gateway:', err);
    }
  };

  const handleMoveDown = async (id: number) => {
    try {
      await apiClient.post(`/gateways/${id}/move-down`);
      fetchGateways();
    } catch (err) {
      console.error('Error moving gateway:', err);
    }
  };

  const openSettings = (gateway: PaymentGateway) => {
    setSelectedGateway(gateway);
    setEditSettings({
      api_key: gateway.settings?.api_key || '',
      secret_key: gateway.settings?.secret_key || '',
      shop_id: gateway.settings?.shop_id || '',
    });
    setSettingsDialogOpen(true);
  };

  const handleSaveSettings = async () => {
    if (!selectedGateway) return;

    try {
      await apiClient.patch(`/gateways/${selectedGateway.id}/settings`, editSettings);
      setSettingsDialogOpen(false);
      fetchGateways();
    } catch (err) {
      console.error('Error saving settings:', err);
      setError('Ошибка сохранения настроек');
    }
  };

  const activeGateways = gateways.filter(g => g.is_active);
  const configuredGateways = gateways.filter(g => g.settings?.is_configure);

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4" fontWeight={600}>
          Платёжные шлюзы
        </Typography>
        <Button
          variant="outlined"
          startIcon={<RefreshIcon />}
          onClick={fetchGateways}
        >
          Обновить
        </Button>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Stats Cards */}
      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid item xs={12} sm={4}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <PaymentIcon color="primary" />
                <Typography color="text.secondary">Всего шлюзов</Typography>
              </Box>
              <Typography variant="h4">{gateways.length}</Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={4}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <ConfiguredIcon color="success" />
                <Typography color="text.secondary">Настроено</Typography>
              </Box>
              <Typography variant="h4">{configuredGateways.length}</Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={4}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <CheckCircle color="info" />
                <Typography color="text.secondary">Активно</Typography>
              </Box>
              <Typography variant="h4">{activeGateways.length}</Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Gateways Table */}
      <Paper>
        {loading && <LinearProgress />}
        <TableContainer>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell width={60}>Порядок</TableCell>
                <TableCell>Шлюз</TableCell>
                <TableCell>Валюта</TableCell>
                <TableCell>Статус</TableCell>
                <TableCell>Настроен</TableCell>
                <TableCell align="right">Действия</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {gateways.map((gateway, index) => (
                <TableRow key={gateway.id}>
                  <TableCell>
                    <Box sx={{ display: 'flex', flexDirection: 'column' }}>
                      <IconButton
                        size="small"
                        onClick={() => handleMoveUp(gateway.id)}
                        disabled={index === 0}
                      >
                        <ArrowUpIcon fontSize="small" />
                      </IconButton>
                      <IconButton
                        size="small"
                        onClick={() => handleMoveDown(gateway.id)}
                        disabled={index === gateways.length - 1}
                      >
                        <ArrowDownIcon fontSize="small" />
                      </IconButton>
                    </Box>
                  </TableCell>
                  <TableCell>
                    <Typography fontWeight={500}>
                      {gatewayLabels[gateway.type] || gateway.type}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Chip
                      label={`${currencySymbols[gateway.currency] || ''} ${gateway.currency}`}
                      size="small"
                      variant="outlined"
                    />
                  </TableCell>
                  <TableCell>
                    <Switch
                      checked={gateway.is_active}
                      onChange={() => handleToggle(gateway.id)}
                      disabled={!gateway.settings?.is_configure && gateway.type !== 'TELEGRAM_STARS'}
                    />
                  </TableCell>
                  <TableCell>
                    {gateway.type === 'TELEGRAM_STARS' ? (
                      <Tooltip title="Не требует настройки">
                        <ConfiguredIcon color="success" />
                      </Tooltip>
                    ) : gateway.settings?.is_configure ? (
                      <Tooltip title="Настроен">
                        <ConfiguredIcon color="success" />
                      </Tooltip>
                    ) : (
                      <Tooltip title="Требуется настройка">
                        <NotConfiguredIcon color="warning" />
                      </Tooltip>
                    )}
                  </TableCell>
                  <TableCell align="right">
                    {gatewayFields[gateway.type]?.length > 0 && (
                      <IconButton
                        size="small"
                        onClick={() => openSettings(gateway)}
                      >
                        <SettingsIcon />
                      </IconButton>
                    )}
                  </TableCell>
                </TableRow>
              ))}
              {gateways.length === 0 && !loading && (
                <TableRow>
                  <TableCell colSpan={6} align="center">
                    <Typography color="text.secondary" sx={{ py: 4 }}>
                      Платёжные шлюзы не найдены
                    </Typography>
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </TableContainer>
      </Paper>

      {/* Settings Dialog */}
      <Dialog open={settingsDialogOpen} onClose={() => setSettingsDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>
          Настройки {selectedGateway ? gatewayLabels[selectedGateway.type] : ''}
        </DialogTitle>
        <DialogContent>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 1 }}>
            {selectedGateway && gatewayFields[selectedGateway.type]?.map((field) => (
              <TextField
                key={field}
                label={field === 'api_key' ? 'API Key' : field === 'secret_key' ? 'Secret Key' : 'Shop ID'}
                type={field.includes('key') ? 'password' : 'text'}
                value={editSettings[field] || ''}
                onChange={(e) => setEditSettings({ ...editSettings, [field]: e.target.value })}
                fullWidth
              />
            ))}
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setSettingsDialogOpen(false)}>Отмена</Button>
          <Button variant="contained" onClick={handleSaveSettings}>
            Сохранить
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}

// Helper component for the stats card
function CheckCircle({ color }: { color: 'info' | 'success' | 'warning' | 'error' }) {
  return <ConfiguredIcon color={color} />;
}