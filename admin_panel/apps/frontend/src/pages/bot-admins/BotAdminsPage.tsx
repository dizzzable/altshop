import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Button,
  IconButton,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Chip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Switch,
  FormControlLabel,
  Alert,
  Snackbar,
  Tooltip,
  Grid,
  Avatar,
} from '@mui/material';
import {
  Add as AddIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
  Block as BlockIcon,
  CheckCircle as CheckCircleIcon,
  AdminPanelSettings as AdminIcon,
} from '@mui/icons-material';
import { api } from '../../api/client';

interface BotAdmin {
  id: number;
  telegramId: string;
  username: string | null;
  firstName: string | null;
  lastName: string | null;
  role: 'super_admin' | 'admin' | 'moderator';
  permissions: string[];
  isActive: boolean;
  addedBy: string | null;
  lastActivity: string | null;
  createdAt: string;
  updatedAt: string;
}

const adminRoles = [
  { value: 'super_admin', label: 'Супер Админ', color: 'error' as const },
  { value: 'admin', label: 'Администратор', color: 'primary' as const },
  { value: 'moderator', label: 'Модератор', color: 'info' as const },
];

const availablePermissions = [
  { value: 'users.view', label: 'Просмотр пользователей' },
  { value: 'users.edit', label: 'Редактирование пользователей' },
  { value: 'users.ban', label: 'Блокировка пользователей' },
  { value: 'subscriptions.view', label: 'Просмотр подписок' },
  { value: 'subscriptions.manage', label: 'Управление подписками' },
  { value: 'promocodes.view', label: 'Просмотр промокодов' },
  { value: 'promocodes.manage', label: 'Управление промокодами' },
  { value: 'broadcast.send', label: 'Отправка рассылок' },
  { value: 'settings.view', label: 'Просмотр настроек' },
  { value: 'settings.edit', label: 'Редактирование настроек' },
  { value: 'statistics.view', label: 'Просмотр статистики' },
];

const emptyAdmin: Partial<BotAdmin> = {
  telegramId: '',
  username: '',
  firstName: '',
  lastName: '',
  role: 'moderator',
  permissions: [],
  isActive: true,
};

export default function BotAdminsPage() {
  const queryClient = useQueryClient();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingAdmin, setEditingAdmin] = useState<Partial<BotAdmin> | null>(null);
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' as 'success' | 'error' });

  const { data: admins = [], isLoading } = useQuery<BotAdmin[]>({
    queryKey: ['bot-admins'],
    queryFn: async () => {
      const response = await api.get('/bot-admins');
      return response.data;
    },
  });

  const createMutation = useMutation({
    mutationFn: async (data: Partial<BotAdmin>) => {
      const response = await api.post('/bot-admins', data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bot-admins'] });
      setDialogOpen(false);
      setSnackbar({ open: true, message: 'Администратор добавлен', severity: 'success' });
    },
    onError: () => {
      setSnackbar({ open: true, message: 'Ошибка добавления администратора', severity: 'error' });
    },
  });

  const updateMutation = useMutation({
    mutationFn: async ({ id, data }: { id: number; data: Partial<BotAdmin> }) => {
      const response = await api.put(`/bot-admins/${id}`, data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bot-admins'] });
      setDialogOpen(false);
      setSnackbar({ open: true, message: 'Администратор обновлен', severity: 'success' });
    },
    onError: () => {
      setSnackbar({ open: true, message: 'Ошибка обновления администратора', severity: 'error' });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: number) => {
      await api.delete(`/bot-admins/${id}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bot-admins'] });
      setSnackbar({ open: true, message: 'Администратор удален', severity: 'success' });
    },
    onError: () => {
      setSnackbar({ open: true, message: 'Ошибка удаления администратора', severity: 'error' });
    },
  });

  const toggleMutation = useMutation({
    mutationFn: async (id: number) => {
      const response = await api.put(`/bot-admins/${id}/toggle`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bot-admins'] });
    },
  });

  const handleCreate = () => {
    setEditingAdmin({ ...emptyAdmin });
    setDialogOpen(true);
  };

  const handleEdit = (admin: BotAdmin) => {
    setEditingAdmin({ ...admin });
    setDialogOpen(true);
  };

  const handleSave = () => {
    if (!editingAdmin) return;

    if (editingAdmin.id) {
      updateMutation.mutate({ id: editingAdmin.id, data: editingAdmin });
    } else {
      createMutation.mutate(editingAdmin);
    }
  };

  const handleDelete = (id: number) => {
    if (confirm('Вы уверены, что хотите удалить этого администратора?')) {
      deleteMutation.mutate(id);
    }
  };

  const getRoleInfo = (role: string) => {
    return adminRoles.find((r) => r.value === role) || { label: role, color: 'default' as const };
  };

  const formatDate = (dateString: string | null) => {
    if (!dateString) return '-';
    return new Date(dateString).toLocaleString('ru-RU');
  };

  if (isLoading) return <Typography>Загрузка...</Typography>;

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Box>
          <Typography variant="h4" fontWeight={600} gutterBottom>
            Администраторы бота
          </Typography>
          <Typography variant="body1" color="text.secondary">
            Управление администраторами Telegram бота
          </Typography>
        </Box>
        <Button variant="contained" startIcon={<AddIcon />} onClick={handleCreate}>
          Добавить админа
        </Button>
      </Box>

      <Card>
        <CardContent>
          <TableContainer component={Paper} variant="outlined">
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Пользователь</TableCell>
                  <TableCell>Telegram ID</TableCell>
                  <TableCell>Роль</TableCell>
                  <TableCell>Права</TableCell>
                  <TableCell>Последняя активность</TableCell>
                  <TableCell>Статус</TableCell>
                  <TableCell align="right">Действия</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {admins.map((admin) => (
                  <TableRow key={admin.id} hover>
                    <TableCell>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                        <Avatar sx={{ bgcolor: getRoleInfo(admin.role).color + '.main' }}>
                          <AdminIcon />
                        </Avatar>
                        <Box>
                          <Typography fontWeight={500}>
                            {admin.firstName || admin.username || 'Без имени'}
                            {admin.lastName && ` ${admin.lastName}`}
                          </Typography>
                          {admin.username && (
                            <Typography variant="body2" color="text.secondary">
                              @{admin.username}
                            </Typography>
                          )}
                        </Box>
                      </Box>
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2" fontFamily="monospace">
                        {admin.telegramId}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={getRoleInfo(admin.role).label}
                        size="small"
                        color={getRoleInfo(admin.role).color}
                      />
                    </TableCell>
                    <TableCell>
                      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                        {admin.permissions.slice(0, 3).map((perm) => (
                          <Chip key={perm} label={perm} size="small" variant="outlined" />
                        ))}
                        {admin.permissions.length > 3 && (
                          <Chip label={`+${admin.permissions.length - 3}`} size="small" />
                        )}
                      </Box>
                    </TableCell>
                    <TableCell>{formatDate(admin.lastActivity)}</TableCell>
                    <TableCell>
                      <Chip
                        label={admin.isActive ? 'Активен' : 'Заблокирован'}
                        size="small"
                        color={admin.isActive ? 'success' : 'error'}
                      />
                    </TableCell>
                    <TableCell align="right">
                      <Tooltip title={admin.isActive ? 'Заблокировать' : 'Разблокировать'}>
                        <IconButton size="small" onClick={() => toggleMutation.mutate(admin.id)}>
                          {admin.isActive ? <BlockIcon /> : <CheckCircleIcon />}
                        </IconButton>
                      </Tooltip>
                      <Tooltip title="Редактировать">
                        <IconButton size="small" onClick={() => handleEdit(admin)}>
                          <EditIcon />
                        </IconButton>
                      </Tooltip>
                      <Tooltip title="Удалить">
                        <IconButton size="small" color="error" onClick={() => handleDelete(admin.id)}>
                          <DeleteIcon />
                        </IconButton>
                      </Tooltip>
                    </TableCell>
                  </TableRow>
                ))}
                {admins.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={7} align="center">
                      <Typography color="text.secondary" py={4}>
                        Администраторы не найдены
                      </Typography>
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </TableContainer>
        </CardContent>
      </Card>

      {/* Dialog for create/edit */}
      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} maxWidth="md" fullWidth>
        <DialogTitle>{editingAdmin?.id ? 'Редактировать администратора' : 'Добавить администратора'}</DialogTitle>
        <DialogContent>
          <Grid container spacing={2} sx={{ mt: 1 }}>
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Telegram ID"
                value={editingAdmin?.telegramId || ''}
                onChange={(e) => setEditingAdmin((prev) => prev ? { ...prev, telegramId: e.target.value } : null)}
                helperText="Числовой ID пользователя в Telegram"
              />
            </Grid>
            <Grid item xs={12} md={6}>
              <TextField
                fullWidth
                label="Username"
                value={editingAdmin?.username || ''}
                onChange={(e) => setEditingAdmin((prev) => prev ? { ...prev, username: e.target.value } : null)}
              />
            </Grid>
            <Grid item xs={12} md={6}>
              <FormControl fullWidth>
                <InputLabel>Роль</InputLabel>
                <Select
                  value={editingAdmin?.role || 'moderator'}
                  label="Роль"
                  onChange={(e) => setEditingAdmin((prev) => prev ? { ...prev, role: e.target.value as any } : null)}
                >
                  {adminRoles.map((role) => (
                    <MenuItem key={role.value} value={role.value}>
                      {role.label}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12} md={6}>
              <TextField
                fullWidth
                label="Имя"
                value={editingAdmin?.firstName || ''}
                onChange={(e) => setEditingAdmin((prev) => prev ? { ...prev, firstName: e.target.value } : null)}
              />
            </Grid>
            <Grid item xs={12} md={6}>
              <TextField
                fullWidth
                label="Фамилия"
                value={editingAdmin?.lastName || ''}
                onChange={(e) => setEditingAdmin((prev) => prev ? { ...prev, lastName: e.target.value } : null)}
              />
            </Grid>
            <Grid item xs={12}>
              <Typography variant="subtitle2" gutterBottom>
                Права доступа
              </Typography>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                {availablePermissions.map((perm) => (
                  <Chip
                    key={perm.value}
                    label={perm.label}
                    onClick={() => {
                      setEditingAdmin((prev) => {
                        if (!prev) return null;
                        const permissions = prev.permissions || [];
                        if (permissions.includes(perm.value)) {
                          return { ...prev, permissions: permissions.filter((p) => p !== perm.value) };
                        } else {
                          return { ...prev, permissions: [...permissions, perm.value] };
                        }
                      });
                    }}
                    color={editingAdmin?.permissions?.includes(perm.value) ? 'primary' : 'default'}
                    variant={editingAdmin?.permissions?.includes(perm.value) ? 'filled' : 'outlined'}
                  />
                ))}
              </Box>
            </Grid>
            <Grid item xs={12}>
              <FormControlLabel
                control={
                  <Switch
                    checked={editingAdmin?.isActive ?? true}
                    onChange={(e) => setEditingAdmin((prev) => prev ? { ...prev, isActive: e.target.checked } : null)}
                  />
                }
                label="Активен"
              />
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialogOpen(false)}>Отмена</Button>
          <Button variant="contained" onClick={handleSave}>
            {editingAdmin?.id ? 'Сохранить' : 'Добавить'}
          </Button>
        </DialogActions>
      </Dialog>

      <Snackbar open={snackbar.open} autoHideDuration={4000} onClose={() => setSnackbar((s) => ({ ...s, open: false }))}>
        <Alert severity={snackbar.severity} onClose={() => setSnackbar((s) => ({ ...s, open: false }))}>
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Box>
  );
}