import express from 'express';
import dotenv from 'dotenv';
import customerRoutes from './routes/customer';

dotenv.config();
const app = express();
const port = 3000;

// 📦 Подключаем маршруты
app.use('/api/customer', customerRoutes);

app.listen(port, () => {
  console.log(`Pagila API running at http://localhost:${port}`);
});
