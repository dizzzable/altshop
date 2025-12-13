import { useState, Fragment, ChangeEvent } from 'react';
import { useMutation } from '@tanstack/react-query';
import {
  Box,
  Typography,
  Paper,
  Button,
  Alert,
  CircularProgress,
  Card,
  CardContent,
  Stepper,
  Step,
  StepLabel,
  List,
  ListItem,
  ListItemText,
  Divider,
} from '@mui/material';
import {
  CloudUpload as UploadIcon,
  CheckCircle as CheckIcon,
  Error as ErrorIcon,
} from '@mui/icons-material';
import { api } from '../../api/client';

const steps = ['Выбор файла', 'Проверка данных', 'Импорт'];

interface ImportResult {
  success: number;
  failed: number;
  errors: string[];
}

export default function ImportPage() {
  const [activeStep, setActiveStep] = useState(0);
  const [file, setFile] = useState<File | null>(null);
  const [previewData, setPreviewData] = useState<string[]>([]);
  const [importResult, setImportResult] = useState<ImportResult | null>(null);

  const previewMutation = useMutation({
    mutationFn: async (formData: FormData) => {
      const response = await api.post('/users/import/preview', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      return response.data;
    },
    onSuccess: (data) => {
      setPreviewData(data.users || []);
      setActiveStep(1);
    },
  });

  const importMutation = useMutation({
    mutationFn: async (formData: FormData) => {
      const response = await api.post('/users/import', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      return response.data;
    },
    onSuccess: (data) => {
      setImportResult(data);
      setActiveStep(2);
    },
  });

  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const selectedFile = event.target.files?.[0];
    if (selectedFile) {
      setFile(selectedFile);
    }
  };

  const handlePreview = () => {
    if (file) {
      const formData = new FormData();
      formData.append('file', file);
      previewMutation.mutate(formData);
    }
  };

  const handleImport = () => {
    if (file) {
      const formData = new FormData();
      formData.append('file', file);
      importMutation.mutate(formData);
    }
  };

  const handleReset = () => {
    setActiveStep(0);
    setFile(null);
    setPreviewData([]);
    setImportResult(null);
  };

  return (
    <Box>
      <Paper sx={{ p: 3, mb: 3, borderRadius: 2 }}>
        <Typography variant="h4" fontWeight={600} gutterBottom>
          📥 Импорт пользователей
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Массовый импорт пользователей из файла
        </Typography>
      </Paper>

      <Paper sx={{ p: 3, borderRadius: 2 }}>
        <Stepper activeStep={activeStep} sx={{ mb: 4 }}>
          {steps.map((label) => (
            <Step key={label}>
              <StepLabel>{label}</StepLabel>
            </Step>
          ))}
        </Stepper>

        {/* Step 0: File Selection */}
        {activeStep === 0 && (
          <Box>
            <Card variant="outlined" sx={{ p: 4, textAlign: 'center', mb: 3 }}>
              <input
                accept=".csv,.txt,.json"
                style={{ display: 'none' }}
                id="file-upload"
                type="file"
                onChange={handleFileChange}
              />
              <label htmlFor="file-upload">
                <Button
                  variant="outlined"
                  component="span"
                  startIcon={<UploadIcon />}
                  size="large"
                >
                  Выбрать файл
                </Button>
              </label>
              {file && (
                <Typography variant="body1" sx={{ mt: 2 }}>
                  Выбран файл: <strong>{file.name}</strong> ({(file.size / 1024).toFixed(2)} KB)
                </Typography>
              )}
            </Card>

            <Alert severity="info" sx={{ mb: 3 }}>
              <Typography variant="body2">
                <strong>Поддерживаемые форматы:</strong>
              </Typography>
              <Typography variant="body2">
                • CSV: telegram_id, username (по одному на строку)
              </Typography>
              <Typography variant="body2">
                • TXT: telegram_id по одному на строку
              </Typography>
              <Typography variant="body2">
                • JSON: массив объектов с полем telegram_id
              </Typography>
            </Alert>

            <Box sx={{ display: 'flex', justifyContent: 'flex-end' }}>
              <Button
                variant="contained"
                onClick={handlePreview}
                disabled={!file || previewMutation.isPending}
              >
                {previewMutation.isPending ? <CircularProgress size={24} /> : 'Далее'}
              </Button>
            </Box>
          </Box>
        )}

        {/* Step 1: Preview */}
        {activeStep === 1 && (
          <Box>
            <Typography variant="h6" gutterBottom>
              Предпросмотр данных
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              Найдено пользователей: {previewData.length}
            </Typography>

            <Card variant="outlined" sx={{ maxHeight: 300, overflow: 'auto', mb: 3 }}>
              <List dense>
                {previewData.slice(0, 100).map((user, index) => (
                  <Fragment key={index}>
                    <ListItem>
                      <ListItemText primary={user} />
                    </ListItem>
                    {index < previewData.length - 1 && <Divider />}
                  </Fragment>
                ))}
                {previewData.length > 100 && (
                  <ListItem>
                    <ListItemText 
                      primary={`... и ещё ${previewData.length - 100} пользователей`}
                      sx={{ color: 'text.secondary' }}
                    />
                  </ListItem>
                )}
              </List>
            </Card>

            <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
              <Button onClick={() => setActiveStep(0)}>
                Назад
              </Button>
              <Button
                variant="contained"
                onClick={handleImport}
                disabled={importMutation.isPending}
              >
                {importMutation.isPending ? <CircularProgress size={24} /> : 'Импортировать'}
              </Button>
            </Box>
          </Box>
        )}

        {/* Step 2: Result */}
        {activeStep === 2 && importResult && (
          <Box>
            <Box sx={{ textAlign: 'center', mb: 4 }}>
              {importResult.failed === 0 ? (
                <CheckIcon sx={{ fontSize: 64, color: 'success.main' }} />
              ) : (
                <ErrorIcon sx={{ fontSize: 64, color: 'warning.main' }} />
              )}
              <Typography variant="h5" sx={{ mt: 2 }}>
                Импорт завершен
              </Typography>
            </Box>

            <Card variant="outlined" sx={{ mb: 3 }}>
              <CardContent>
                <Typography variant="body1">
                  ✅ Успешно импортировано: <strong>{importResult.success}</strong>
                </Typography>
                <Typography variant="body1">
                  ❌ Ошибок: <strong>{importResult.failed}</strong>
                </Typography>
              </CardContent>
            </Card>

            {importResult.errors.length > 0 && (
              <Alert severity="warning" sx={{ mb: 3 }}>
                <Typography variant="body2" fontWeight={600}>Ошибки:</Typography>
                {importResult.errors.slice(0, 10).map((error, index) => (
                  <Typography key={index} variant="body2">• {error}</Typography>
                ))}
                {importResult.errors.length > 10 && (
                  <Typography variant="body2">
                    ... и ещё {importResult.errors.length - 10} ошибок
                  </Typography>
                )}
              </Alert>
            )}

            <Box sx={{ display: 'flex', justifyContent: 'center' }}>
              <Button variant="contained" onClick={handleReset}>
                Импортировать ещё
              </Button>
            </Box>
          </Box>
        )}
      </Paper>
    </Box>
  );
}