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
  TablePagination,
  Chip,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Card,
  CardContent,
  Grid,
  LinearProgress,
  Alert,
  Tooltip,
} from '@mui/material';
import {
  Add as AddIcon,
  Cancel as CancelIcon,
  Delete as DeleteIcon,
  Refresh as RefreshIcon,
  Send as SendIcon,
  People as PeopleIcon,
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon,
  HourglassEmpty as ProcessingIcon,
} from '@mui/icons-material';
import apiClient from '../../api/client';

interface Broadcast {
  id: number;
  task_id: string;
  status: string;
  audience: string;
  total_count: number;
  success_count: number;
  failed_count: number;
  payload: {
    message: string;
    media_type?: string;
    buttons?: Array<{ text: string; url: string }>;
  };
  created_at: string;
}

interface BroadcastStats {
  total: number;
  processing: number;
  completed: number;
  canceled: number;
  error: number;
}

const audienceOptions = [
  { value: 'ALL', label: 'Все пользователи' },
  { value: 'SUBSCRIBED', label: 'С активной подпиской' },
  { value: 'UNSUBSCRIBED', label: 'Без подписки' },
  { value: 'EXPIRED', label: 'С истёкшей подпиской' },
  { value: 'TRIAL', label: 'Триальные пользователи' },
];

const statusColors: Record<string, 'default' | 'primary' | 'success' | 'error' | 'warning'> = {
  PROCESSING: 'primary',
  COMPLETED: 'success',
  CANCELED: 'warning',
  ERROR: 'error',
  DELETED: 'default',
};

const statusLabels: Record<string, string> = {
  PROCESSING: 'В процессе',
  COMPLETED: 'Завершена',
  CANCELED: 'Отменена',
  ERROR: 'Ошибка',
  DELETED: 'Удалена',
};

export default function BroadcastPage() {
  const [broadcasts, setBroadcasts] = useState<Broadcast[]>([]);
  const [stats, setStats] = useState<BroadcastStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(10);
  const [total, setTotal] = useState(0);
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [newBroadcast, setNewBroadcast] = useState({
    audience: 'ALL',
    message: '',
  });
  const [audienceCount, setAudienceCount] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchBroadcasts = async () => {
    try {
      setLoading(true);
      const response = await apiClient.get('/broadcast', {
        params: { page: page + 1, limit: rowsPerPage },
      });
      setBroadcasts(response.data.data);
      setTotal(response.data.total);
    } catch (err) {
      console.error('Error fetching broadcasts:', err);
      setError('Ошибка загрузки рассылок');
    } finally {
      setLoading(false);
    }
  };

  const fetchStats = async () => {
    try {
      const response = await apiClient.get('/broadcast/stats');
      setStats(response.data);
    } catch (err) {
      console.error('Error fetching stats:', err);
    }
  };

  const fetchAudienceCount = async (audience: string) => {
    try {
      const response = await apiClient.get('/broadcast/audience-count', {
        params: { audience },
      });
      setAudienceCount(response.data.count);
    } catch (err) {
      console.error('Error fetching audience count:', err);
    }
  };

  useEffect(() => {
    fetchBroadcasts();
    fetchStats();
  }, [page, rowsPerPage]);

  useEffect(() => {
    if (createDialogOpen) {
      fetchAudienceCount(newBroadcast.audience);
    }
  }, [newBroadcast.audience, createDialogOpen]);

  const handleCreate = async () => {
    try {
      await apiClient.post('/broadcast', newBroadcast);
      setCreateDialogOpen(false);
      setNewBroadcast({ audience: 'ALL', message: '' });
      fetchBroadcasts();
      fetchStats();
    } catch (err) {
      console.error('Error creating broadcast:', err);
      setError('Ошибка создания рассылки');
    }
  };

  const handleCancel = async (id: number) => {
    try {
      await apiClient.post(`/broadcast/${id}/cancel`);
      fetchBroadcasts();
      fetchStats();
    } catch (err) {
      console.error('Error canceling broadcast:', err);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await apiClient.delete(`/broadcast/${id}`);
      fetchBroadcasts();
      fetchStats();
    } catch (err) {
      console.error('Error deleting broadcast:', err);
    }
  };

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4" fontWeight={600}>
          Рассылки
        </Typography>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button
            variant="outlined"
            startIcon={<RefreshIcon />}
            onClick={() => { fetchBroadcasts(); fetchStats(); }}
          >
            Обновить
          </Button>
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={() => setCreateDialogOpen(true)}
          >
            Новая рассылка
          </Button>
        </Box>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Stats Cards */}
      {stats && (
        <Grid container spacing={2} sx={{ mb: 3 }}>
          <Grid item xs={12} sm={6} md={2.4}>
            <Card>
              <CardContent>
                <Typography color="text.secondary" gutterBottom>
                  Всего
                </Typography>
                <Typography variant="h4">{stats.total}</Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} sm={6} md={2.4}>
            <Card>
              <CardContent>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <ProcessingIcon color="primary" />
                  <Typography color="text.secondary">В процессе</Typography>
                </Box>
                <Typography variant="h4">{stats.processing}</Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} sm={6} md={2.4}>
            <Card>
              <CardContent>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <CheckCircleIcon color="success" />
                  <Typography color="text.secondary">Завершено</Typography>
                </Box>
                <Typography variant="h4">{stats.completed}</Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} sm={6} md={2.4}>
            <Card>
              <CardContent>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <CancelIcon color="warning" />
                  <Typography color="text.secondary">Отменено</Typography>
                </Box>
                <Typography variant="h4">{stats.canceled}</Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} sm={6} md={2.4}>
            <Card>
              <CardContent>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <ErrorIcon color="error" />
                  <Typography color="text.secondary">Ошибки</Typography>
                </Box>
                <Typography variant="h4">{stats.error}</Typography>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}

      {/* Broadcasts Table */}
      <Paper>
        {loading && <LinearProgress />}
        <TableContainer>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>ID</TableCell>
                <TableCell>Статус</TableCell>
                <TableCell>Аудитория</TableCell>
                <TableCell>Прогресс</TableCell>
                <TableCell>Сообщение</TableCell>
                <TableCell>Дата</TableCell>
                <TableCell align="right">Действия</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {broadcasts.map((broadcast) => (
                <TableRow key={broadcast.id}>
                  <TableCell>{broadcast.id}</TableCell>
                  <TableCell>
                    <Chip
                      label={statusLabels[broadcast.status] || broadcast.status}
                      color={statusColors[broadcast.status] || 'default'}
                      size="small"
                    />
                  </TableCell>
                  <TableCell>
                    {audienceOptions.find(a => a.value === broadcast.audience)?.label || broadcast.audience}
                  </TableCell>
                  <TableCell>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <Box sx={{ flex: 1, minWidth: 100 }}>
                        <LinearProgress
                          variant="determinate"
                          value={broadcast.total_count > 0 
                            ? ((broadcast.success_count + broadcast.failed_count) / broadcast.total_count) * 100 
                            : 0}
                          color={broadcast.failed_count > 0 ? 'warning' : 'primary'}
                        />
                      </Box>
                      <Typography variant="body2" color="text.secondary">
                        {broadcast.success_count}/{broadcast.total_count}
                      </Typography>
                    </Box>
                  </TableCell>
                  <TableCell>
                    <Tooltip title={broadcast.payload.message}>
                      <Typography noWrap sx={{ maxWidth: 200 }}>
                        {broadcast.payload.message}
                      </Typography>
                    </Tooltip>
                  </TableCell>
                  <TableCell>
                    {new Date(broadcast.created_at).toLocaleString('ru-RU')}
                  </TableCell>
                  <TableCell align="right">
                    {broadcast.status === 'PROCESSING' && (
                      <IconButton
                        size="small"
                        onClick={() => handleCancel(broadcast.id)}
                        color="warning"
                      >
                        <CancelIcon />
                      </IconButton>
                    )}
                    <IconButton
                      size="small"
                      onClick={() => handleDelete(broadcast.id)}
                      color="error"
                    >
                      <DeleteIcon />
                    </IconButton>
                  </TableCell>
                </TableRow>
              ))}
              {broadcasts.length === 0 && !loading && (
                <TableRow>
                  <TableCell colSpan={7} align="center">
                    <Typography color="text.secondary" sx={{ py: 4 }}>
                      Рассылки не найдены
                    </Typography>
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </TableContainer>
        <TablePagination
          component="div"
          count={total}
          page={page}
          onPageChange={(_, newPage) => setPage(newPage)}
          rowsPerPage={rowsPerPage}
          onRowsPerPageChange={(e) => {
            setRowsPerPage(parseInt(e.target.value, 10));
            setPage(0);
          }}
          labelRowsPerPage="Строк на странице:"
        />
      </Paper>

      {/* Create Dialog */}
      <Dialog open={createDialogOpen} onClose={() => setCreateDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Новая рассылка</DialogTitle>
        <DialogContent>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 1 }}>
            <FormControl fullWidth>
              <InputLabel>Аудитория</InputLabel>
              <Select
                value={newBroadcast.audience}
                label="Аудитория"
                onChange={(e) => setNewBroadcast({ ...newBroadcast, audience: e.target.value })}
              >
                {audienceOptions.map((option) => (
                  <MenuItem key={option.value} value={option.value}>
                    {option.label}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            
            {audienceCount !== null && (
              <Alert severity="info" icon={<PeopleIcon />}>
                Получателей: {audienceCount}
              </Alert>
            )}

            <TextField
              label="Сообщение"
              multiline
              rows={4}
              value={newBroadcast.message}
              onChange={(e) => setNewBroadcast({ ...newBroadcast, message: e.target.value })}
              placeholder="Введите текст сообщения..."
            />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCreateDialogOpen(false)}>Отмена</Button>
          <Button
            variant="contained"
            startIcon={<SendIcon />}
            onClick={handleCreate}
            disabled={!newBroadcast.message.trim()}
          >
            Отправить
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}