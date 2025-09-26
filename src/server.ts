import express from 'express';
import dotenv from 'dotenv';
import customerRoutes from './routes/customer';
import healthRouter from './routes/health';


dotenv.config();
const app = express();
app.use(express.json());
const port = 3000;

// 📦 Подключаем маршруты
app.use(healthRouter);
app.use('/api/customer', customerRoutes);

app.listen(3000, '0.0.0.0', () => {
  console.log(`Pagila API running at http://localhost:3000`);
});
