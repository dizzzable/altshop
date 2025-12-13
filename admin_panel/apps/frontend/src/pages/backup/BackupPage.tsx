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
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Alert,
  LinearProgress,
  Chip,
  Card,
  CardContent,
  Grid,
  FormControlLabel,
  Checkbox,
} from '@mui/material';
import {
  Backup as BackupIcon,
  Restore as RestoreIcon,
  Delete as DeleteIcon,
  Download as DownloadIcon,
  Refresh as RefreshIcon,
  Storage as StorageIcon,
  Schedule as ScheduleIcon,
} from '@mui/icons-material';
import apiClient from '../../api/client';

interface BackupInfo {
  filename: string;
  size: number;
  createdAt: string;
  path: string;
}

export default function BackupPage() {
  const [backups, setBackups] = useState<BackupInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [restoring, setRestoring] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [restoreDialogOpen, setRestoreDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [selectedBackup, setSelectedBackup] = useState<BackupInfo | null>(null);
  const [clearExisting, setClearExisting] = useState(false);

  const fetchBackups = async () => {
    try {
      setLoading(true);
      const response = await apiClient.get('/backup');
      setBackups(response.data);
    } catch (err) {
      console.error('Error fetching backups:', err);
      setError('Ошибка загрузки списка бэкапов');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchBackups();
  }, []);

  const handleCreate = async () => {
    try {
      setCreating(true);
      setError(null);
      const response = await apiClient.post('/backup/create');
      if (response.data.success) {
        setSuccess(`Бэкап создан: ${response.data.filename}`);
        fetchBackups();
      } else {
        setError(response.data.message);
      }
    } catch (err) {
      console.error('Error creating backup:', err);
      setError('Ошибка создания бэкапа');
    } finally {
      setCreating(false);
    }
  };

  const handleRestore = async () => {
    if (!selectedBackup) return;

    try {
      setRestoring(true);
      setError(null);
      const response = await apiClient.post('/backup/restore', {
        filename: selectedBackup.filename,
        clearExisting,
      });
      if (response.data.success) {
        setSuccess('Бэкап успешно восстановлен');
      } else {
        setError(response.data.message);
      }
    } catch (err) {
      console.error('Error restoring backup:', err);
      setError('Ошибка восстановления бэкапа');
    } finally {
      setRestoring(false);
      setRestoreDialogOpen(false);
      setClearExisting(false);
    }
  };

  const handleDelete = async () => {
    if (!selectedBackup) return;

    try {
      const response = await apiClient.delete(`/backup/${selectedBackup.filename}`);
      if (response.data.success) {
        setSuccess('Бэкап удалён');
        fetchBackups();
      } else {
        setError(response.data.message);
      }
    } catch (err) {
      console.error('Error deleting backup:', err);
      setError('Ошибка удаления бэкапа');
    } finally {
      setDeleteDialogOpen(false);
    }
  };

  const handleDownload = async (backup: BackupInfo) => {
    try {
      const response = await apiClient.get(`/backup/download/${backup.filename}`, {
        responseType: 'blob',
      });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', backup.filename);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (err) {
      console.error('Error downloading backup:', err);
      setError('Ошибка скачивания бэкапа');
    }
  };

  const formatSize = (bytes: number): string => {
    const units = ['B', 'KB', 'MB', 'GB'];
    let size = bytes;
    let unitIndex = 0;

    while (size >= 1024 && unitIndex < units.length - 1) {
      size /= 1024;
      unitIndex++;
    }

    return `${size.toFixed(2)} ${units[unitIndex]}`;
  };

  const totalSize = backups.reduce((acc, b) => acc + b.size, 0);

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4" fontWeight={600}>
          Резервные копии
        </Typography>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button
            variant="outlined"
            startIcon={<RefreshIcon />}
            onClick={fetchBackups}
            disabled={loading}
          >
            Обновить
          </Button>
          <Button
            variant="contained"
            startIcon={<BackupIcon />}
            onClick={handleCreate}
            disabled={creating}
          >
            {creating ? 'Создание...' : 'Создать бэкап'}
          </Button>
        </Box>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {success && (
        <Alert severity="success" sx={{ mb: 2 }} onClose={() => setSuccess(null)}>
          {success}
        </Alert>
      )}

      {/* Stats Cards */}
      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid item xs={12} sm={4}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <BackupIcon color="primary" />
                <Typography color="text.secondary">Всего бэкапов</Typography>
              </Box>
              <Typography variant="h4">{backups.length}</Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={4}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <StorageIcon color="info" />
                <Typography color="text.secondary">Общий размер</Typography>
              </Box>
              <Typography variant="h4">{formatSize(totalSize)}</Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={4}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <ScheduleIcon color="success" />
                <Typography color="text.secondary">Последний бэкап</Typography>
              </Box>
              <Typography variant="h6">
                {backups.length > 0
                  ? new Date(backups[0].createdAt).toLocaleString('ru-RU')
                  : 'Нет бэкапов'}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Backups Table */}
      <Paper>
        {loading && <LinearProgress />}
        <TableContainer>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>Имя файла</TableCell>
                <TableCell>Размер</TableCell>
                <TableCell>Дата создания</TableCell>
                <TableCell align="right">Действия</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {backups.map((backup) => (
                <TableRow key={backup.filename}>
                  <TableCell>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <BackupIcon color="action" />
                      <Typography>{backup.filename}</Typography>
                    </Box>
                  </TableCell>
                  <TableCell>
                    <Chip label={formatSize(backup.size)} size="small" variant="outlined" />
                  </TableCell>
                  <TableCell>
                    {new Date(backup.createdAt).toLocaleString('ru-RU')}
                  </TableCell>
                  <TableCell align="right">
                    <IconButton
                      size="small"
                      onClick={() => handleDownload(backup)}
                      title="Скачать"
                    >
                      <DownloadIcon />
                    </IconButton>
                    <IconButton
                      size="small"
                      onClick={() => {
                        setSelectedBackup(backup);
                        setRestoreDialogOpen(true);
                      }}
                      title="Восстановить"
                      color="primary"
                    >
                      <RestoreIcon />
                    </IconButton>
                    <IconButton
                      size="small"
                      onClick={() => {
                        setSelectedBackup(backup);
                        setDeleteDialogOpen(true);
                      }}
                      title="Удалить"
                      color="error"
                    >
                      <DeleteIcon />
                    </IconButton>
                  </TableCell>
                </TableRow>
              ))}
              {backups.length === 0 && !loading && (
                <TableRow>
                  <TableCell colSpan={4} align="center">
                    <Typography color="text.secondary" sx={{ py: 4 }}>
                      Резервные копии не найдены
                    </Typography>
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </TableContainer>
      </Paper>

      {/* Restore Dialog */}
      <Dialog open={restoreDialogOpen} onClose={() => setRestoreDialogOpen(false)}>
        <DialogTitle>Восстановление из бэкапа</DialogTitle>
        <DialogContent>
          <Typography gutterBottom>
            Вы уверены, что хотите восстановить базу данных из бэкапа{' '}
            <strong>{selectedBackup?.filename}</strong>?
          </Typography>
          <Alert severity="warning" sx={{ mt: 2 }}>
            Это действие перезапишет текущие данные!
          </Alert>
          <FormControlLabel
            control={
              <Checkbox
                checked={clearExisting}
                onChange={(e) => setClearExisting(e.target.checked)}
                color="error"
              />
            }
            label="Полностью очистить базу перед восстановлением (опасно!)"
            sx={{ mt: 2 }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setRestoreDialogOpen(false)}>Отмена</Button>
          <Button
            variant="contained"
            color="warning"
            onClick={handleRestore}
            disabled={restoring}
            startIcon={<RestoreIcon />}
          >
            {restoring ? 'Восстановление...' : 'Восстановить'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Delete Dialog */}
      <Dialog open={deleteDialogOpen} onClose={() => setDeleteDialogOpen(false)}>
        <DialogTitle>Удаление бэкапа</DialogTitle>
        <DialogContent>
          <Typography>
            Вы уверены, что хотите удалить бэкап{' '}
            <strong>{selectedBackup?.filename}</strong>?
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteDialogOpen(false)}>Отмена</Button>
          <Button
            variant="contained"
            color="error"
            onClick={handleDelete}
            startIcon={<DeleteIcon />}
          >
            Удалить
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}