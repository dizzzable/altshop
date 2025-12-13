import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Button,
  IconButton,
  Grid,
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
  CardMedia,
  CardActions,
} from '@mui/material';
import {
  Add as AddIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
  Visibility as VisibilityIcon,
  VisibilityOff as VisibilityOffIcon,
  Image as ImageIcon,
} from '@mui/icons-material';
import { api } from '../../api/client';

interface Banner {
  id: number;
  name: string;
  type: 'welcome' | 'menu' | 'subscription' | 'dashboard' | 'promo' | 'custom';
  filePath: string | null;
  fileId: string | null;
  locale: string;
  isActive: boolean;
  priority: number;
  startDate: string | null;
  endDate: string | null;
  createdAt: string;
  updatedAt: string;
}

const bannerTypes = [
  { value: 'welcome', label: 'Приветствие' },
  { value: 'menu', label: 'Главное меню' },
  { value: 'subscription', label: 'Подписка' },
  { value: 'dashboard', label: 'Панель управления' },
  { value: 'promo', label: 'Промо' },
  { value: 'custom', label: 'Кастомный' },
];

const locales = [
  { value: 'ru', label: 'Русский' },
  { value: 'en', label: 'English' },
];

const emptyBanner: Partial<Banner> = {
  name: '',
  type: 'custom',
  filePath: '',
  fileId: '',
  locale: 'ru',
  isActive: true,
  priority: 0,
  startDate: null,
  endDate: null,
};

export default function BannersPage() {
  const queryClient = useQueryClient();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingBanner, setEditingBanner] = useState<Partial<Banner> | null>(null);
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' as 'success' | 'error' });

  const { data: banners = [], isLoading } = useQuery<Banner[]>({
    queryKey: ['banners'],
    queryFn: async () => {
      const response = await api.get('/banners');
      return response.data;
    },
  });

  const createMutation = useMutation({
    mutationFn: async (data: Partial<Banner>) => {
      const response = await api.post('/banners', data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['banners'] });
      setDialogOpen(false);
      setSnackbar({ open: true, message: 'Баннер создан', severity: 'success' });
    },
    onError: () => {
      setSnackbar({ open: true, message: 'Ошибка создания баннера', severity: 'error' });
    },
  });

  const updateMutation = useMutation({
    mutationFn: async ({ id, data }: { id: number; data: Partial<Banner> }) => {
      const response = await api.put(`/banners/${id}`, data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['banners'] });
      setDialogOpen(false);
      setSnackbar({ open: true, message: 'Баннер обновлен', severity: 'success' });
    },
    onError: () => {
      setSnackbar({ open: true, message: 'Ошибка обновления баннера', severity: 'error' });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: number) => {
      await api.delete(`/banners/${id}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['banners'] });
      setSnackbar({ open: true, message: 'Баннер удален', severity: 'success' });
    },
    onError: () => {
      setSnackbar({ open: true, message: 'Ошибка удаления баннера', severity: 'error' });
    },
  });

  const toggleMutation = useMutation({
    mutationFn: async (id: number) => {
      const response = await api.put(`/banners/${id}/toggle`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['banners'] });
    },
  });

  const handleCreate = () => {
    setEditingBanner({ ...emptyBanner });
    setDialogOpen(true);
  };

  const handleEdit = (banner: Banner) => {
    setEditingBanner({ ...banner });
    setDialogOpen(true);
  };

  const handleSave = () => {
    if (!editingBanner) return;

    if (editingBanner.id) {
      updateMutation.mutate({ id: editingBanner.id, data: editingBanner });
    } else {
      createMutation.mutate(editingBanner);
    }
  };

  const handleDelete = (id: number) => {
    if (confirm('Вы уверены, что хотите удалить этот баннер?')) {
      deleteMutation.mutate(id);
    }
  };

  const getTypeLabel = (type: string) => {
    return bannerTypes.find((t) => t.value === type)?.label || type;
  };

  if (isLoading) return <Typography>Загрузка...</Typography>;

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Box>
          <Typography variant="h4" fontWeight={600} gutterBottom>
            Баннеры
          </Typography>
          <Typography variant="body1" color="text.secondary">
            Управление изображениями и баннерами бота
          </Typography>
        </Box>
        <Button variant="contained" startIcon={<AddIcon />} onClick={handleCreate}>
          Добавить баннер
        </Button>
      </Box>

      <Grid container spacing={3}>
        {banners.map((banner) => (
          <Grid item xs={12} sm={6} md={4} key={banner.id}>
            <Card sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
              {banner.filePath ? (
                <CardMedia
                  component="img"
                  height="160"
                  image={banner.filePath}
                  alt={banner.name}
                  sx={{ objectFit: 'cover' }}
                />
              ) : (
                <Box
                  sx={{
                    height: 160,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    bgcolor: 'action.hover',
                  }}
                >
                  <ImageIcon sx={{ fontSize: 64, color: 'text.secondary' }} />
                </Box>
              )}
              <CardContent sx={{ flexGrow: 1 }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 1 }}>
                  <Typography variant="h6" component="div">
                    {banner.name}
                  </Typography>
                  <Chip
                    label={banner.isActive ? 'Активен' : 'Неактивен'}
                    size="small"
                    color={banner.isActive ? 'success' : 'default'}
                  />
                </Box>
                <Box sx={{ display: 'flex', gap: 1, mb: 1 }}>
                  <Chip label={getTypeLabel(banner.type)} size="small" variant="outlined" />
                  <Chip label={banner.locale.toUpperCase()} size="small" variant="outlined" />
                </Box>
                <Typography variant="body2" color="text.secondary">
                  Приоритет: {banner.priority}
                </Typography>
                {banner.startDate && (
                  <Typography variant="body2" color="text.secondary">
                    С: {new Date(banner.startDate).toLocaleDateString('ru-RU')}
                  </Typography>
                )}
                {banner.endDate && (
                  <Typography variant="body2" color="text.secondary">
                    До: {new Date(banner.endDate).toLocaleDateString('ru-RU')}
                  </Typography>
                )}
              </CardContent>
              <CardActions>
                <Tooltip title={banner.isActive ? 'Деактивировать' : 'Активировать'}>
                  <IconButton size="small" onClick={() => toggleMutation.mutate(banner.id)}>
                    {banner.isActive ? <VisibilityIcon /> : <VisibilityOffIcon />}
                  </IconButton>
                </Tooltip>
                <Tooltip title="Редактировать">
                  <IconButton size="small" onClick={() => handleEdit(banner)}>
                    <EditIcon />
                  </IconButton>
                </Tooltip>
                <Tooltip title="Удалить">
                  <IconButton size="small" color="error" onClick={() => handleDelete(banner.id)}>
                    <DeleteIcon />
                  </IconButton>
                </Tooltip>
              </CardActions>
            </Card>
          </Grid>
        ))}
        {banners.length === 0 && (
          <Grid item xs={12}>
            <Card>
              <CardContent>
                <Typography color="text.secondary" align="center" py={4}>
                  Баннеры не найдены
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        )}
      </Grid>

      {/* Dialog for create/edit */}
      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>{editingBanner?.id ? 'Редактировать баннер' : 'Создать баннер'}</DialogTitle>
        <DialogContent>
          <Grid container spacing={2} sx={{ mt: 1 }}>
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Название"
                value={editingBanner?.name || ''}
                onChange={(e) => setEditingBanner((prev) => prev ? { ...prev, name: e.target.value } : null)}
              />
            </Grid>
            <Grid item xs={12} md={6}>
              <FormControl fullWidth>
                <InputLabel>Тип</InputLabel>
                <Select
                  value={editingBanner?.type || 'custom'}
                  label="Тип"
                  onChange={(e) => setEditingBanner((prev) => prev ? { ...prev, type: e.target.value as any } : null)}
                >
                  {bannerTypes.map((type) => (
                    <MenuItem key={type.value} value={type.value}>
                      {type.label}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12} md={6}>
              <FormControl fullWidth>
                <InputLabel>Язык</InputLabel>
                <Select
                  value={editingBanner?.locale || 'ru'}
                  label="Язык"
                  onChange={(e) => setEditingBanner((prev) => prev ? { ...prev, locale: e.target.value } : null)}
                >
                  {locales.map((locale) => (
                    <MenuItem key={locale.value} value={locale.value}>
                      {locale.label}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Путь к файлу"
                value={editingBanner?.filePath || ''}
                onChange={(e) => setEditingBanner((prev) => prev ? { ...prev, filePath: e.target.value } : null)}
                helperText="Относительный путь к изображению"
              />
            </Grid>
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="File ID (Telegram)"
                value={editingBanner?.fileId || ''}
                onChange={(e) => setEditingBanner((prev) => prev ? { ...prev, fileId: e.target.value } : null)}
                helperText="ID файла в Telegram (заполняется автоматически)"
              />
            </Grid>
            <Grid item xs={12} md={4}>
              <TextField
                fullWidth
                type="number"
                label="Приоритет"
                value={editingBanner?.priority || 0}
                onChange={(e) => setEditingBanner((prev) => prev ? { ...prev, priority: parseInt(e.target.value) } : null)}
              />
            </Grid>
            <Grid item xs={12} md={4}>
              <TextField
                fullWidth
                type="date"
                label="Дата начала"
                value={editingBanner?.startDate?.split('T')[0] || ''}
                onChange={(e) => setEditingBanner((prev) => prev ? { ...prev, startDate: e.target.value || null } : null)}
                InputLabelProps={{ shrink: true }}
              />
            </Grid>
            <Grid item xs={12} md={4}>
              <TextField
                fullWidth
                type="date"
                label="Дата окончания"
                value={editingBanner?.endDate?.split('T')[0] || ''}
                onChange={(e) => setEditingBanner((prev) => prev ? { ...prev, endDate: e.target.value || null } : null)}
                InputLabelProps={{ shrink: true }}
              />
            </Grid>
            <Grid item xs={12}>
              <FormControlLabel
                control={
                  <Switch
                    checked={editingBanner?.isActive ?? true}
                    onChange={(e) => setEditingBanner((prev) => prev ? { ...prev, isActive: e.target.checked } : null)}
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
            {editingBanner?.id ? 'Сохранить' : 'Создать'}
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