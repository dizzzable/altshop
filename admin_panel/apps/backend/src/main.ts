import { NestFactory } from '@nestjs/core';
import { ValidationPipe } from '@nestjs/common';
import { SwaggerModule, DocumentBuilder } from '@nestjs/swagger';
import { AppModule } from './app.module';

async function bootstrap() {
  const app = await NestFactory.create(AppModule);

  // Enable CORS
  app.enableCors({
    origin: process.env.FRONTEND_URL || 'http://localhost:3001',
    credentials: true,
  });

  // Global validation pipe
  app.useGlobalPipes(
    new ValidationPipe({
      whitelist: true,
      forbidNonWhitelisted: true,
      transform: true,
    }),
  );

  // API prefix (exclude health endpoint)
  app.setGlobalPrefix('api', {
    exclude: ['health'],
  });

  // Health check endpoint for Docker healthcheck
  const httpAdapter = app.getHttpAdapter();
  httpAdapter.get('/health', (req, res) => {
    res.status(200).send('OK');
  });

  // Swagger documentation
  const config = new DocumentBuilder()
    .setTitle('AltShop Admin Panel API')
    .setDescription('API for managing AltShop Telegram Bot')
    .setVersion('1.0')
    .addBearerAuth()
    .build();
  const document = SwaggerModule.createDocument(app, config);
  SwaggerModule.setup('api/docs', app, document);

  const port = process.env.PORT || process.env.BACKEND_PORT || 4000;
  await app.listen(port);
  console.log(`🚀 Backend is running on: http://localhost:${port}`);
  console.log(`📚 Swagger docs: http://localhost:${port}/api/docs`);
}
bootstrap();