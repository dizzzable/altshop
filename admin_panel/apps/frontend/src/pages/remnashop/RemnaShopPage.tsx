import { useNavigate } from 'react-router-dom';
import {
  Box,
  Typography,
  Paper,
  Grid,
  Card,
  CardActionArea,
  CardContent,
} from '@mui/material';

interface MenuButtonProps {
  emoji: string;
  title: string;
  description?: string;
  onClick: () => void;
  color?: string;
}

function MenuButton({ emoji, title, description, onClick, color = '#1e3a5f' }: MenuButtonProps) {
  return (
    <Card 
      sx={{ 
        bgcolor: color,
        borderRadius: 2,
        height: '100%',
        transition: 'transform 0.2s, box-shadow 0.2s',
        '&:hover': {
          transform: 'translateY(-2px)',
          boxShadow: 4,
        }
      }}
    >
      <CardActionArea onClick={onClick} sx={{ height: '100%', p: 2 }}>
        <CardContent sx={{ textAlign: 'center' }}>
          <Typography variant="h4" sx={{ mb: 1 }}>
            {emoji}
          </Typography>
          <Typography variant="h6" sx={{ color: 'white', fontWeight: 500 }}>
            {title}
          </Typography>
          {description && (
            <Typography variant="body2" sx={{ color: 'rgba(255,255,255,0.7)', mt: 1 }}>
              {description}
            </Typography>
          )}
        </CardContent>
      </CardActionArea>
    </Card>
  );
}

export default function RemnaShopPage() {
  const navigate = useNavigate();

  return (
    <Box>
      <Paper sx={{ p: 3, mb: 3, borderRadius: 2 }}>
        <Typography variant="h4" fontWeight={600} gutterBottom>
          🛒 RemnaShop
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Настройки магазина и бота
        </Typography>
      </Paper>

      <Grid container spacing={3}>
        {/* Row 1: Admins */}
        <Grid item xs={12}>
          <MenuButton
            emoji="👑"
            title="Администраторы"
            description="Управление администраторами бота"
            onClick={() => navigate('/bot-admins')}
            color="#2d4a6f"
          />
        </Grid>

        {/* Row 2: Gateways */}
        <Grid item xs={12}>
          <MenuButton
            emoji="💳"
            title="Платежные системы"
            description="Настройка платежных шлюзов"
            onClick={() => navigate('/gateways')}
            color="#1a4a5e"
          />
        </Grid>

        {/* Row 3: Referral & Partner */}
        <Grid item xs={12} md={6}>
          <MenuButton
            emoji="👥"
            title="Реферальная система"
            description="Настройки реферальной программы"
            onClick={() => navigate('/settings?tab=referral')}
            color="#1e5a4a"
          />
        </Grid>
        <Grid item xs={12} md={6}>
          <MenuButton
            emoji="💼"
            title="Партнерская программа"
            description="Настройки партнерки"
            onClick={() => navigate('/settings?tab=partner')}
            color="#1e5a4a"
          />
        </Grid>

        {/* Row 4: Plans & Notifications */}
        <Grid item xs={12} md={6}>
          <MenuButton
            emoji="📋"
            title="Тарифные планы"
            description="Управление планами подписок"
            onClick={() => navigate('/plans')}
            color="#3d4a6f"
          />
        </Grid>
        <Grid item xs={12} md={6}>
          <MenuButton
            emoji="🔔"
            title="Уведомления"
            description="Настройки уведомлений"
            onClick={() => navigate('/settings?tab=notifications')}
            color="#3d4a6f"
          />
        </Grid>

        {/* Row 5: Banners & Multi-subscription */}
        <Grid item xs={12} md={6}>
          <MenuButton
            emoji="🖼"
            title="Баннеры"
            description="Управление баннерами бота"
            onClick={() => navigate('/banners')}
            color="#4a3d6f"
          />
        </Grid>
        <Grid item xs={12} md={6}>
          <MenuButton
            emoji="📦"
            title="Мультиподписка"
            description="Настройки мультиподписки"
            onClick={() => navigate('/settings?tab=multisubscription')}
            color="#4a3d6f"
          />
        </Grid>

        {/* Row 6: Logs & Audit */}
        <Grid item xs={12} md={6}>
          <MenuButton
            emoji="📜"
            title="Логи"
            description="Просмотр логов системы"
            onClick={() => navigate('/audit')}
            color="#5a4a3d"
          />
        </Grid>
        <Grid item xs={12} md={6}>
          <MenuButton
            emoji="🔍"
            title="Аудит"
            description="Журнал действий"
            onClick={() => navigate('/audit')}
            color="#5a4a3d"
          />
        </Grid>

        {/* Row 7: Backup */}
        <Grid item xs={12}>
          <MenuButton
            emoji="💾"
            title="Резервное копирование"
            description="Создание и восстановление бэкапов"
            onClick={() => navigate('/backup')}
            color="#6f4a3d"
          />
        </Grid>
      </Grid>
    </Box>
  );
}