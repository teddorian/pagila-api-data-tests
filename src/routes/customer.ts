import { Router } from 'express';
import { query } from '../utils/db';
import { createCustomer } from '../controllers/customerController';

const router = Router();

// 🔍 Получить клиента по ID
router.get('/:id', async (req, res) => {
  try {
    const result = await query(
      'SELECT * FROM customer WHERE customer_id = $1',
      [req.params.id]
    );
    res.json(result.rows[0]);
  } catch (error) {
    res.status(500).json({ error: 'Internal Server Error' });
  }
});

// 👤 Создать нового клиента
router.post('/', createCustomer);

// 📧 Фильтрация по email
router.get('/', async (req, res) => {
  const { email } = req.query;
  if (!email || typeof email !== 'string') {
    return res.status(400).json({ error: 'Email query param required' });
  }

  try {
    const result = await query(
      'SELECT * FROM customer WHERE email ILIKE $1',
      [`%${email}%`]
    );
    res.json(result.rows);
  } catch (error) {
    res.status(500).json({ error: 'Internal Server Error' });
  }
});

export default router;
