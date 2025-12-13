import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Chip,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  TextField,
  Grid,
  Pagination,
  IconButton,
  Collapse,
} from '@mui/material';
import {
  ExpandMore as ExpandMoreIcon,
  ExpandLess as ExpandLessIcon,
  FilterList as FilterIcon,
} from '@mui/icons-material';
import { api } from '../../api/client';

interface AuditLog {
  id: number;
  action: string;
  entityType: string;
  entityId: string | null;
  adminId: string | null;
  adminUsername: string | null;
  oldValue: Record<string, any> | null;
  newValue: Record<string, any> | null;
  description: string | null;
  ipAddress: string | null;
  userAgent: string | null;
  createdAt: string;
}

const actionLabels: Record<string, { label: string; color: 'default' | 'primary' | 'secondary' | 'error' | 'info' | 'success' | 'warning' }> = {
  create: { label: 'Создание', color: 'success' },
  update: { label: 'Обновление', color: 'info' },
  delete: { label: 'Удаление', color: 'error' },
  login: { label: 'Вход', color: 'primary' },
  logout: { label: 'Выход', color: 'default' },
  broadcast: { label: 'Рассылка', color: 'warning' },
  settings_change: { label: 'Изменение настроек', color: 'secondary' },
  user_ban: { label: 'Блокировка', color: 'error' },
  user_unban: { label: 'Разблокировка', color: 'success' },
  subscription_grant: { label: 'Выдача подписки', color: 'success' },
  subscription_revoke: { label: 'Отзыв подписки', color: 'error' },
  payment: { label: 'Платеж', color: 'primary' },
  promocode_use: { label: 'Использование промокода', color: 'info' },
};

const entityLabels: Record<string, string> = {
  user: 'Пользователь',
  subscription: 'Подписка',
  plan: 'Тариф',
  promocode: 'Промокод',
  settings: 'Настройки',
  broadcast: 'Рассылка',
  admin: 'Администратор',
  button: 'Кнопка',
  banner: 'Баннер',
  gateway: 'Платежный шлюз',
};

export default function AuditPage() {
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState({
    action: '',
    entityType: '',
    startDate: '',
    endDate: '',
  });
  const [expandedRow, setExpandedRow] = useState<number | null>(null);
  const [showFilters, setShowFilters] = useState(false);
  const limit = 20;

  const { data, isLoading } = useQuery<{ data: AuditLog[]; total: number }>({
    queryKey: ['audit', page, filters],
    queryFn: async () => {
      const params = new URLSearchParams();
      params.append('limit', limit.toString());
      params.append('offset', ((page - 1) * limit).toString());
      if (filters.action) params.append('action', filters.action);
      if (filters.entityType) params.append('entityType', filters.entityType);
      if (filters.startDate) params.append('startDate', filters.startDate);
      if (filters.endDate) params.append('endDate', filters.endDate);

      const response = await api.get(`/audit?${params.toString()}`);
      return response.data;
    },
  });

  const logs = data?.data || [];
  const total = data?.total || 0;
  const totalPages = Math.ceil(total / limit);

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString('ru-RU');
  };

  const getActionInfo = (action: string) => {
    return actionLabels[action] || { label: action, color: 'default' as const };
  };

  const getEntityLabel = (entityType: string) => {
    return entityLabels[entityType] || entityType;
  };

  const renderJsonDiff = (oldValue: any, newValue: any) => {
    if (!oldValue && !newValue) return null;

    return (
      <Box sx={{ display: 'flex', gap: 2, mt: 1 }}>
        {oldValue && (
          <Box sx={{ flex: 1 }}>
            <Typography variant="caption" color="error.main" fontWeight={600}>
              Было:
            </Typography>
            <Paper variant="outlined" sx={{ p: 1, mt: 0.5, bgcolor: 'error.light', opacity: 0.1 }}>
              <pre style={{ margin: 0, fontSize: 12, overflow: 'auto' }}>
                {JSON.stringify(oldValue, null, 2)}
              </pre>
            </Paper>
          </Box>
        )}
        {newValue && (
          <Box sx={{ flex: 1 }}>
            <Typography variant="caption" color="success.main" fontWeight={600}>
              Стало:
            </Typography>
            <Paper variant="outlined" sx={{ p: 1, mt: 0.5, bgcolor: 'success.light', opacity: 0.1 }}>
              <pre style={{ margin: 0, fontSize: 12, overflow: 'auto' }}>
                {JSON.stringify(newValue, null, 2)}
              </pre>
            </Paper>
          </Box>
        )}
      </Box>
    );
  };

  if (isLoading) return <Typography>Загрузка...</Typography>;

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Box>
          <Typography variant="h4" fontWeight={600} gutterBottom>
            Журнал аудита
          </Typography>
          <Typography variant="body1" color="text.secondary">
            История всех действий в системе
          </Typography>
        </Box>
        <IconButton onClick={() => setShowFilters(!showFilters)}>
          <FilterIcon />
        </IconButton>
      </Box>

      <Collapse in={showFilters}>
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Grid container spacing={2}>
              <Grid item xs={12} md={3}>
                <FormControl fullWidth size="small">
                  <InputLabel>Действие</InputLabel>
                  <Select
                    value={filters.action}
                    label="Действие"
                    onChange={(e) => setFilters((f) => ({ ...f, action: e.target.value }))}
                  >
                    <MenuItem value="">Все</MenuItem>
                    {Object.entries(actionLabels).map(([value, { label }]) => (
                      <MenuItem key={value} value={value}>
                        {label}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              </Grid>
              <Grid item xs={12} md={3}>
                <FormControl fullWidth size="small">
                  <InputLabel>Сущность</InputLabel>
                  <Select
                    value={filters.entityType}
                    label="Сущность"
                    onChange={(e) => setFilters((f) => ({ ...f, entityType: e.target.value }))}
                  >
                    <MenuItem value="">Все</MenuItem>
                    {Object.entries(entityLabels).map(([value, label]) => (
                      <MenuItem key={value} value={value}>
                        {label}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              </Grid>
              <Grid item xs={12} md={3}>
                <TextField
                  fullWidth
                  size="small"
                  type="date"
                  label="С даты"
                  value={filters.startDate}
                  onChange={(e) => setFilters((f) => ({ ...f, startDate: e.target.value }))}
                  InputLabelProps={{ shrink: true }}
                />
              </Grid>
              <Grid item xs={12} md={3}>
                <TextField
                  fullWidth
                  size="small"
                  type="date"
                  label="По дату"
                  value={filters.endDate}
                  onChange={(e) => setFilters((f) => ({ ...f, endDate: e.target.value }))}
                  InputLabelProps={{ shrink: true }}
                />
              </Grid>
            </Grid>
          </CardContent>
        </Card>
      </Collapse>

      <Card>
        <CardContent>
          <TableContainer component={Paper} variant="outlined">
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell width={50}></TableCell>
                  <TableCell>Дата</TableCell>
                  <TableCell>Действие</TableCell>
                  <TableCell>Сущность</TableCell>
                  <TableCell>ID</TableCell>
                  <TableCell>Администратор</TableCell>
                  <TableCell>Описание</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {logs.map((log) => (
                  <>
                    <TableRow
                      key={log.id}
                      hover
                      sx={{ cursor: 'pointer' }}
                      onClick={() => setExpandedRow(expandedRow === log.id ? null : log.id)}
                    >
                      <TableCell>
                        <IconButton size="small">
                          {expandedRow === log.id ? <ExpandLessIcon /> : <ExpandMoreIcon />}
                        </IconButton>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2">{formatDate(log.createdAt)}</Typography>
                      </TableCell>
                      <TableCell>
                        <Chip
                          label={getActionInfo(log.action).label}
                          size="small"
                          color={getActionInfo(log.action).color}
                        />
                      </TableCell>
                      <TableCell>
                        <Chip label={getEntityLabel(log.entityType)} size="small" variant="outlined" />
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" fontFamily="monospace">
                          {log.entityId || '-'}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        {log.adminUsername ? (
                          <Typography variant="body2">@{log.adminUsername}</Typography>
                        ) : (
                          <Typography variant="body2" color="text.secondary">
                            Система
                          </Typography>
                        )}
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" noWrap sx={{ maxWidth: 200 }}>
                          {log.description || '-'}
                        </Typography>
                      </TableCell>
                    </TableRow>
                    <TableRow>
                      <TableCell colSpan={7} sx={{ py: 0 }}>
                        <Collapse in={expandedRow === log.id}>
                          <Box sx={{ py: 2 }}>
                            {log.description && (
                              <Typography variant="body2" sx={{ mb: 2 }}>
                                {log.description}
                              </Typography>
                            )}
                            {renderJsonDiff(log.oldValue, log.newValue)}
                            {(log.ipAddress || log.userAgent) && (
                              <Box sx={{ mt: 2 }}>
                                <Typography variant="caption" color="text.secondary">
                                  IP: {log.ipAddress || '-'} | User Agent: {log.userAgent || '-'}
                                </Typography>
                              </Box>
                            )}
                          </Box>
                        </Collapse>
                      </TableCell>
                    </TableRow>
                  </>
                ))}
                {logs.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={7} align="center">
                      <Typography color="text.secondary" py={4}>
                        Записи не найдены
                      </Typography>
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </TableContainer>

          {totalPages > 1 && (
            <Box sx={{ display: 'flex', justifyContent: 'center', mt: 3 }}>
              <Pagination
                count={totalPages}
                page={page}
                onChange={(_, value) => setPage(value)}
                color="primary"
              />
            </Box>
          )}
        </CardContent>
      </Card>
    </Box>
  );
}