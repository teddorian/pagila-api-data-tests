import express from 'express';
import dotenv from 'dotenv';
import customerRouter from './routes/customer';
import { Pool } from 'pg';

dotenv.config();
const app = express();
app.use(express.json());

const pool = new Pool({ connectionString: process.env.DB_URL });

app.use('/api/customer', customerRouter);

app.get('/health/db', async (_, res) => {
  try {
    await pool.query('SELECT 1');
    res.json({ db: 'connected' });
  } catch {
    res.status(500).json({ db: 'error' });
  }
});

app.listen(3000, () => {
  console.log('Server running on http://localhost:3000');
});
