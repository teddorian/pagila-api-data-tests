// src/controllers/customer.ts
import { Request, Response } from 'express';
import { query } from '../utils/db';

export const createCustomer = async (req: Request, res: Response) => {
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
    } else {
      console.error('Unknown error in POST /customer:', err);
    }
    res.status(500).json({ error: 'Internal Server Error' });
  }
};
