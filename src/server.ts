import express from 'express';
import dotenv from 'dotenv';
import customerRouter from './routes/customer';
import healthRouter from './routes/health';

dotenv.config();

const app = express();
app.use(express.json());

app.use('/', healthRouter);
app.use('/api/customer', customerRouter);

const PORT = Number(process.env.PORT ?? 3000);

app.listen(PORT, () => {
  console.log(`Server running on http://localhost:${PORT}`);
});

export default app;
