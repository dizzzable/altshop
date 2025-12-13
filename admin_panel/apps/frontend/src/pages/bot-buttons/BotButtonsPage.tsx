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
} from '@mui/material';
import {
  Add as AddIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
  Visibility as VisibilityIcon,
  VisibilityOff as VisibilityOffIcon,
  DragIndicator as DragIcon,
} from '@mui/icons-material';
import { api } from '../../api/client';

interface BotButton {
  id: number;
  name: string;
  text: string;
  textKey: string | null;
  type: 'main_menu' | 'inline' | 'reply';
  action: 'url' | 'callback' | 'state' | 'webapp';
  actionData: string | null;
  parentMenu: string | null;
  position: number;
  row: number;
  emoji: string | null;
  isActive: boolean;
  requiresAdmin: boolean;
  requiresSubscription: boolean;
  conditions: Record<string, any>;
  createdAt: string;
  updatedAt: string;
}

const buttonTypes = [
  { value: 'main_menu', label: 'Главное меню' },
  { value: 'inline', label: 'Inline кнопка' },
  { value: 'reply', label: 'Reply кнопка' },
];

const buttonActions = [
  { value: 'url', label: 'URL ссылка' },
  { value: 'callback', label: 'Callback' },
  { value: 'state', label: 'Состояние' },
  { value: 'webapp', label: 'WebApp' },
];

const emptyButton: Partial<BotButton> = {
  name: '',
  text: '',
  textKey: '',
  type: 'inline',
  action: 'callback',
  actionData: '',
  parentMenu: '',
  position: 0,
  row: 0,
  emoji: '',
  isActive: true,
  requiresAdmin: false,
  requiresSubscription: false,
  conditions: {},
};

export default function BotButtonsPage() {
  const queryClient = useQueryClient();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingButton, setEditingButton] = useState<Partial<BotButton> | null>(null);
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' as 'success' | 'error' });

  const { data: buttons = [], isLoading } = useQuery<BotButton[]>({
    queryKey: ['bot-buttons'],
    queryFn: async () => {
      const response = await api.get('/bot-buttons');
      return response.data;
    },
  });

  const createMutation = useMutation({
    mutationFn: async (data: Partial<BotButton>) => {
      const response = await api.post('/bot-buttons', data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bot-buttons'] });
      setDialogOpen(false);
      setSnackbar({ open: true, message: 'Кнопка создана', severity: 'success' });
    },
    onError: () => {
      setSnackbar({ open: true, message: 'Ошибка создания кнопки', severity: 'error' });
    },
  });

  const updateMutation = useMutation({
    mutationFn: async ({ id, data }: { id: number; data: Partial<BotButton> }) => {
      const response = await api.put(`/bot-buttons/${id}`, data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bot-buttons'] });
      setDialogOpen(false);
      setSnackbar({ open: true, message: 'Кнопка обновлена', severity: 'success' });
    },
    onError: () => {
      setSnackbar({ open: true, message: 'Ошибка обновления кнопки', severity: 'error' });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: number) => {
      await api.delete(`/bot-buttons/${id}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bot-buttons'] });
      setSnackbar({ open: true, message: 'Кнопка удалена', severity: 'success' });
    },
    onError: () => {
      setSnackbar({ open: true, message: 'Ошибка удаления кнопки', severity: 'error' });
    },
  });

  const toggleMutation = useMutation({
    mutationFn: async (id: number) => {
      const response = await api.put(`/bot-buttons/${id}/toggle`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bot-buttons'] });
    },
  });

  const handleCreate = () => {
    setEditingButton({ ...emptyButton });
    setDialogOpen(true);
  };

  const handleEdit = (button: BotButton) => {
    setEditingButton({ ...button });
    setDialogOpen(true);
  };

  const handleSave = () => {
    if (!editingButton) return;

    if (editingButton.id) {
      updateMutation.mutate({ id: editingButton.id, data: editingButton });
    } else {
      createMutation.mutate(editingButton);
    }
  };

  const handleDelete = (id: number) => {
    if (confirm('Вы уверены, что хотите удалить эту кнопку?')) {
      deleteMutation.mutate(id);
    }
  };

  const getTypeLabel = (type: string) => {
    return buttonTypes.find((t) => t.value === type)?.label || type;
  };

  const getActionLabel = (action: string) => {
    return buttonActions.find((a) => a.value === action)?.label || action;
  };

  if (isLoading) return <Typography>Загрузка...</Typography>;

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Box>
          <Typography variant="h4" fontWeight={600} gutterBottom>
            Кнопки бота
          </Typography>
          <Typography variant="body1" color="text.secondary">
            Управление кнопками и меню Telegram бота
          </Typography>
        </Box>
        <Button variant="contained" startIcon={<AddIcon />} onClick={handleCreate}>
          Добавить кнопку
        </Button>
      </Box>

      <Card>
        <CardContent>
          <TableContainer component={Paper} variant="outlined">
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell width={50}></TableCell>
                  <TableCell>Название</TableCell>
                  <TableCell>Текст</TableCell>
                  <TableCell>Тип</TableCell>
                  <TableCell>Действие</TableCell>
                  <TableCell>Меню</TableCell>
                  <TableCell>Позиция</TableCell>
                  <TableCell>Статус</TableCell>
                  <TableCell align="right">Действия</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {buttons.map((button) => (
                  <TableRow key={button.id} hover>
                    <TableCell>
                      <DragIcon sx={{ color: 'text.secondary', cursor: 'grab' }} />
                    </TableCell>
                    <TableCell>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        {button.emoji && <span>{button.emoji}</span>}
                        <Typography fontWeight={500}>{button.name}</Typography>
                      </Box>
                    </TableCell>
                    <TableCell>{button.text}</TableCell>
                    <TableCell>
                      <Chip label={getTypeLabel(button.type)} size="small" variant="outlined" />
                    </TableCell>
                    <TableCell>
                      <Chip label={getActionLabel(button.action)} size="small" color="primary" variant="outlined" />
                    </TableCell>
                    <TableCell>{button.parentMenu || '-'}</TableCell>
                    <TableCell>
                      Ряд {button.row}, Поз {button.position}
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={button.isActive ? 'Активна' : 'Неактивна'}
                        size="small"
                        color={button.isActive ? 'success' : 'default'}
                      />
                    </TableCell>
                    <TableCell align="right">
                      <Tooltip title={button.isActive ? 'Деактивировать' : 'Активировать'}>
                        <IconButton size="small" onClick={() => toggleMutation.mutate(button.id)}>
                          {button.isActive ? <VisibilityIcon /> : <VisibilityOffIcon />}
                        </IconButton>
                      </Tooltip>
                      <Tooltip title="Редактировать">
                        <IconButton size="small" onClick={() => handleEdit(button)}>
                          <EditIcon />
                        </IconButton>
                      </Tooltip>
                      <Tooltip title="Удалить">
                        <IconButton size="small" color="error" onClick={() => handleDelete(button.id)}>
                          <DeleteIcon />
                        </IconButton>
                      </Tooltip>
                    </TableCell>
                  </TableRow>
                ))}
                {buttons.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={9} align="center">
                      <Typography color="text.secondary" py={4}>
                        Кнопки не найдены
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
        <DialogTitle>{editingButton?.id ? 'Редактировать кнопку' : 'Создать кнопку'}</DialogTitle>
        <DialogContent>
          <Grid container spacing={2} sx={{ mt: 1 }}>
            <Grid item xs={12} md={6}>
              <TextField
                fullWidth
                label="Название (ID)"
                value={editingButton?.name || ''}
                onChange={(e) => setEditingButton((prev) => ({ ...prev, name: e.target.value }))}
              />
            </Grid>
            <Grid item xs={12} md={6}>
              <TextField
                fullWidth
                label="Emoji"
                value={editingButton?.emoji || ''}
                onChange={(e) => setEditingButton((prev) => ({ ...prev, emoji: e.target.value }))}
              />
            </Grid>
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Текст кнопки"
                value={editingButton?.text || ''}
                onChange={(e) => setEditingButton((prev) => ({ ...prev, text: e.target.value }))}
              />
            </Grid>
            <Grid item xs={12} md={6}>
              <TextField
                fullWidth
                label="Ключ перевода"
                value={editingButton?.textKey || ''}
                onChange={(e) => setEditingButton((prev) => ({ ...prev, textKey: e.target.value }))}
                helperText="Ключ для i18n перевода"
              />
            </Grid>
            <Grid item xs={12} md={6}>
              <TextField
                fullWidth
                label="Родительское меню"
                value={editingButton?.parentMenu || ''}
                onChange={(e) => setEditingButton((prev) => ({ ...prev, parentMenu: e.target.value }))}
              />
            </Grid>
            <Grid item xs={12} md={6}>
              <FormControl fullWidth>
                <InputLabel>Тип кнопки</InputLabel>
                <Select
                  value={editingButton?.type || 'inline'}
                  label="Тип кнопки"
                  onChange={(e) => setEditingButton((prev) => ({ ...prev, type: e.target.value as any }))}
                >
                  {buttonTypes.map((type) => (
                    <MenuItem key={type.value} value={type.value}>
                      {type.label}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12} md={6}>
              <FormControl fullWidth>
                <InputLabel>Действие</InputLabel>
                <Select
                  value={editingButton?.action || 'callback'}
                  label="Действие"
                  onChange={(e) => setEditingButton((prev) => ({ ...prev, action: e.target.value as any }))}
                >
                  {buttonActions.map((action) => (
                    <MenuItem key={action.value} value={action.value}>
                      {action.label}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Данные действия"
                value={editingButton?.actionData || ''}
                onChange={(e) => setEditingButton((prev) => ({ ...prev, actionData: e.target.value }))}
                helperText="URL, callback_data или state в зависимости от типа действия"
              />
            </Grid>
            <Grid item xs={6} md={3}>
              <TextField
                fullWidth
                type="number"
                label="Ряд"
                value={editingButton?.row || 0}
                onChange={(e) => setEditingButton((prev) => ({ ...prev, row: parseInt(e.target.value) }))}
              />
            </Grid>
            <Grid item xs={6} md={3}>
              <TextField
                fullWidth
                type="number"
                label="Позиция"
                value={editingButton?.position || 0}
                onChange={(e) => setEditingButton((prev) => ({ ...prev, position: parseInt(e.target.value) }))}
              />
            </Grid>
            <Grid item xs={12} md={6}>
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                <FormControlLabel
                  control={
                    <Switch
                      checked={editingButton?.isActive ?? true}
                      onChange={(e) => setEditingButton((prev) => ({ ...prev, isActive: e.target.checked }))}
                    />
                  }
                  label="Активна"
                />
                <FormControlLabel
                  control={
                    <Switch
                      checked={editingButton?.requiresAdmin ?? false}
                      onChange={(e) => setEditingButton((prev) => ({ ...prev, requiresAdmin: e.target.checked }))}
                    />
                  }
                  label="Только для админов"
                />
                <FormControlLabel
                  control={
                    <Switch
                      checked={editingButton?.requiresSubscription ?? false}
                      onChange={(e) => setEditingButton((prev) => ({ ...prev, requiresSubscription: e.target.checked }))}
                    />
                  }
                  label="Требуется подписка"
                />
              </Box>
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialogOpen(false)}>Отмена</Button>
          <Button variant="contained" onClick={handleSave}>
            {editingButton?.id ? 'Сохранить' : 'Создать'}
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