import { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Grid,
  Typography,
  Paper,
  LinearProgress,
  CircularProgress,
  Tooltip,
} from '@mui/material';
import api from '../../api/client';

interface CpuMetrics {
  usage: number;
  cores: number;
  model: string;
  speed: number;
}

interface MemoryMetrics {
  total: number;
  used: number;
  free: number;
  usagePercent: number;
}

interface DiskMetrics {
  total: number;
  used: number;
  free: number;
  usagePercent: number;
}

interface SystemMetrics {
  cpu: CpuMetrics;
  memory: MemoryMetrics;
  disk: DiskMetrics;
  uptime: number;
  platform: string;
  hostname: string;
  timestamp: string;
}

const formatBytes = (bytes: number): string => {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
};

const formatUptime = (seconds: number): string => {
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  
  const parts = [];
  if (days > 0) parts.push(`${days}д`);
  if (hours > 0) parts.push(`${hours}ч`);
  if (minutes > 0) parts.push(`${minutes}м`);
  
  return parts.length > 0 ? parts.join(' ') : '< 1м';
};

const getProgressColor = (percent: number): 'success' | 'warning' | 'error' => {
  if (percent < 60) return 'success';
  if (percent < 85) return 'warning';
  return 'error';
};

interface MetricCardProps {
  title: string;
  emoji: string;
  value: string;
  subValue?: string;
  percent: number;
  tooltip?: string;
}

function MetricCard({ title, emoji, value, subValue, percent, tooltip }: MetricCardProps) {
  const content = (
    <Paper
      sx={{
        p: 3,
        bgcolor: 'background.paper',
        borderRadius: 2,
        height: '100%',
        border: '1px solid',
        borderColor: 'divider',
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
        <Typography variant="h5" sx={{ mr: 1.5 }}>{emoji}</Typography>
        <Typography variant="h6" color="text.primary" fontWeight={600}>
          {title}
        </Typography>
      </Box>
      <Typography variant="h3" fontWeight={700} color="text.primary" sx={{ mb: 0.5 }}>
        {value}
      </Typography>
      {subValue && (
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          {subValue}
        </Typography>
      )}
      <Box sx={{ mt: 2 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
          <Typography variant="body2" color="text.secondary">
            Использовано
          </Typography>
          <Typography variant="body2" fontWeight={700} color={`${getProgressColor(percent)}.main`}>
            {percent}%
          </Typography>
        </Box>
        <LinearProgress
          variant="determinate"
          value={percent}
          color={getProgressColor(percent)}
          sx={{
            height: 10,
            borderRadius: 5,
            bgcolor: 'action.hover',
          }}
        />
      </Box>
    </Paper>
  );

  return tooltip ? (
    <Tooltip title={tooltip} arrow placement="top">
      {content}
    </Tooltip>
  ) : content;
}

export default function DashboardPage() {
  const [metrics, setMetrics] = useState<SystemMetrics | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchMetrics = useCallback(async () => {
    try {
      const response = await api.get<SystemMetrics>('/dashboard/system-metrics');
      setMetrics(response.data);
      setError(null);
    } catch (err) {
      console.error('Failed to fetch system metrics:', err);
      setError('Не удалось загрузить метрики сервера');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchMetrics();
    
    // Auto-refresh every 5 seconds
    const interval = setInterval(fetchMetrics, 5000);
    
    return () => clearInterval(interval);
  }, [fetchMetrics]);

  return (
    <Box>
      {/* Header */}
      <Paper
        sx={{
          p: 3,
          mb: 3,
          bgcolor: 'background.paper',
          borderRadius: 2,
        }}
      >
        <Typography variant="h4" fontWeight={600} gutterBottom>
          🎛 Панель управления
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Мониторинг состояния сервера в реальном времени
        </Typography>
      </Paper>

      {/* Server Info Header */}
      {metrics && (
        <Paper
          sx={{
            p: 2,
            mb: 3,
            bgcolor: 'background.paper',
            borderRadius: 2,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: 2,
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 3 }}>
            <Box>
              <Typography variant="caption" color="text.secondary">Хост</Typography>
              <Typography variant="body1" fontWeight={600}>{metrics.hostname}</Typography>
            </Box>
            <Box>
              <Typography variant="caption" color="text.secondary">Платформа</Typography>
              <Typography variant="body1" fontWeight={600}>{metrics.platform}</Typography>
            </Box>
            <Box>
              <Typography variant="caption" color="text.secondary">Время работы</Typography>
              <Typography variant="body1" fontWeight={600}>{formatUptime(metrics.uptime)}</Typography>
            </Box>
          </Box>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Box
              sx={{
                width: 8,
                height: 8,
                borderRadius: '50%',
                bgcolor: 'success.main',
                animation: 'pulse 2s infinite',
                '@keyframes pulse': {
                  '0%': { opacity: 1 },
                  '50%': { opacity: 0.5 },
                  '100%': { opacity: 1 },
                },
              }}
            />
            <Typography variant="body2" color="text.secondary">
              Обновление каждые 5 сек
            </Typography>
          </Box>
        </Paper>
      )}

      {/* System Metrics */}
      {isLoading && !metrics ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
          <CircularProgress size={60} />
        </Box>
      ) : error ? (
        <Paper sx={{ p: 4, textAlign: 'center', borderRadius: 2 }}>
          <Typography variant="h6" color="error" gutterBottom>
            ⚠️ Ошибка загрузки
          </Typography>
          <Typography color="text.secondary">{error}</Typography>
        </Paper>
      ) : metrics ? (
        <Grid container spacing={3}>
          <Grid item xs={12} md={4}>
            <MetricCard
              title="Процессор (CPU)"
              emoji="⚡"
              value={`${metrics.cpu.usage}%`}
              subValue={`${metrics.cpu.cores} ядер • ${metrics.cpu.speed} MHz`}
              percent={metrics.cpu.usage}
              tooltip={metrics.cpu.model}
            />
          </Grid>
          <Grid item xs={12} md={4}>
            <MetricCard
              title="Оперативная память"
              emoji="🧠"
              value={formatBytes(metrics.memory.used)}
              subValue={`из ${formatBytes(metrics.memory.total)} • Свободно: ${formatBytes(metrics.memory.free)}`}
              percent={metrics.memory.usagePercent}
            />
          </Grid>
          <Grid item xs={12} md={4}>
            <MetricCard
              title="Дисковое пространство"
              emoji="💾"
              value={formatBytes(metrics.disk.used)}
              subValue={`из ${formatBytes(metrics.disk.total)} • Свободно: ${formatBytes(metrics.disk.free)}`}
              percent={metrics.disk.usagePercent}
            />
          </Grid>
        </Grid>
      ) : null}

      {/* Additional Info */}
      {metrics && (
        <Paper sx={{ p: 3, mt: 3, borderRadius: 2 }}>
          <Typography variant="h6" fontWeight={600} gutterBottom>
            📊 Детальная информация
          </Typography>
          <Grid container spacing={3} sx={{ mt: 1 }}>
            <Grid item xs={12} md={4}>
              <Box sx={{ p: 2, bgcolor: 'action.hover', borderRadius: 2 }}>
                <Typography variant="body2" color="text.secondary" gutterBottom>
                  Модель процессора
                </Typography>
                <Typography variant="body1" fontWeight={500} sx={{ wordBreak: 'break-word' }}>
                  {metrics.cpu.model}
                </Typography>
              </Box>
            </Grid>
            <Grid item xs={12} md={4}>
              <Box sx={{ p: 2, bgcolor: 'action.hover', borderRadius: 2 }}>
                <Typography variant="body2" color="text.secondary" gutterBottom>
                  Свободная память
                </Typography>
                <Typography variant="body1" fontWeight={500}>
                  {formatBytes(metrics.memory.free)} из {formatBytes(metrics.memory.total)}
                </Typography>
              </Box>
            </Grid>
            <Grid item xs={12} md={4}>
              <Box sx={{ p: 2, bgcolor: 'action.hover', borderRadius: 2 }}>
                <Typography variant="body2" color="text.secondary" gutterBottom>
                  Свободное место на диске
                </Typography>
                <Typography variant="body1" fontWeight={500}>
                  {formatBytes(metrics.disk.free)} из {formatBytes(metrics.disk.total)}
                </Typography>
              </Box>
            </Grid>
          </Grid>
        </Paper>
      )}
    </Box>
  );
}