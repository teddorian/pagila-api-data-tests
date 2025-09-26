import { Router } from 'express';
import { query } from '../utils/db';

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
router.post('/', async (req, res) => {
  console.log('Incoming customer payload:', req.body);
  const { first_name, last_name, email, store_id, address_id, active, create_date } = req.body;

  if (!first_name || !last_name || !email || !store_id || !address_id) {
    return res.status(400).json({ error: 'Missing required fields' });
  }

  try {
    const result = await query(
      `INSERT INTO customer (store_id, first_name, last_name, email, address_id, active, create_date)
       VALUES ($1, $2, $3, $4, $5, $6, $7)
       RETURNING *`,
      [store_id, first_name, last_name, email, address_id, active ?? true, create_date ?? new Date()]
    );
    res.status(201).json(result.rows[0]);
  } catch (err) {
    if (err instanceof Error) {
      console.error('POST /customer failed:', err.message);
    }
    res.status(500).json({ error: 'Internal Server Error' });
  }
});


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
