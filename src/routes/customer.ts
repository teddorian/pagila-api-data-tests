import { Router } from 'express';
import { query } from '../utils/db';
import { createCustomer } from '../controllers/customerController';

const router = Router();

router.post('/', createCustomer);

router.get('/:id', async (req, res) => {
  try {
    const result = await query(
      'SELECT customer_id, first_name, last_name, email FROM customer WHERE customer_id = $1',
      [req.params.id]
    );

    if (result.rows.length === 0) {
      return res.status(404).json({ error: 'Customer not found' });
    }

    return res.json(result.rows[0]);
  } catch (err) {
    console.error('GET /api/customer/:id failed:', err instanceof Error ? err.message : err);
    return res.status(500).json({ error: 'Internal Server Error' });
  }
});

export default router;
