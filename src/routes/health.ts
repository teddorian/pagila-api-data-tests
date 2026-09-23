import { Router } from 'express';
import { query } from '../utils/db';

const router = Router();

router.get('/health', (_req, res) => {
  res.status(200).json({ status: 'ok' });
});

router.get('/health/db', async (_req, res) => {
  try {
    await query('SELECT 1');
    res.status(200).json({ status: 'ok', db: 'connected' });
  } catch (err) {
    console.error('DB healthcheck failed:', err instanceof Error ? err.message : err);
    res.status(500).json({ status: 'error', db: 'unreachable' });
  }
});

export default router;
