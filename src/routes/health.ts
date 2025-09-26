// src/routes/health.ts
import express from 'express';
import { Pool } from 'pg';

const router = express.Router();

// Подключение к базе через переменную окружения
const db = new Pool({
  connectionString: process.env.DB_URL,
});

router.get('/health', (req, res) => {
  res.status(200).json({ status: 'ok' });
});

router.get('/health/db', async (req, res) => {
    try {
      await db.query('SELECT 1');
      res.status(200).json({ status: 'ok', db: 'connected' });
    } catch (err) {
      if (err instanceof Error) {
        console.error('DB healthcheck failed:', err.message);
      } else {
        console.error('DB healthcheck failed with unknown error:', err);
      }
      res.status(500).json({ status: 'error', db: 'unreachable' });
    }
  });
  

export default router;
