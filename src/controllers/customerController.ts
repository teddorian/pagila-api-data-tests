import { Request, Response } from 'express';
import { query } from '../utils/db';

const REQUIRED_FIELDS = ['first_name', 'last_name', 'store_id', 'address_id'] as const;

// Postgres error codes we can translate into a client error instead of a 500.
const FOREIGN_KEY_VIOLATION = '23503';

const isPositiveInteger = (value: unknown): boolean =>
  Number.isInteger(value) && (value as number) > 0;

export const createCustomer = async (req: Request, res: Response) => {
  const body = req.body ?? {};
  const { first_name, last_name, email, store_id, address_id, active } = body;

  const missing = REQUIRED_FIELDS.filter((field) => body[field] === undefined || body[field] === null);
  if (missing.length > 0) {
    return res.status(400).json({ error: `Missing required fields: ${missing.join(', ')}` });
  }

  const invalid = (['store_id', 'address_id'] as const).filter((field) => !isPositiveInteger(body[field]));
  if (invalid.length > 0) {
    return res.status(400).json({ error: `Fields must be positive integers: ${invalid.join(', ')}` });
  }

  try {
    const result = await query(
      `INSERT INTO customer (store_id, first_name, last_name, email, address_id, active)
       VALUES ($1, $2, $3, $4, $5, $6)
       RETURNING customer_id, first_name, last_name, email`,
      [store_id, first_name, last_name, email ?? null, address_id, active ?? 1]
    );

    return res.status(201).json(result.rows[0]);
  } catch (err) {
    if (typeof err === 'object' && err !== null && (err as { code?: string }).code === FOREIGN_KEY_VIOLATION) {
      return res.status(400).json({ error: 'Unknown store_id or address_id' });
    }

    console.error('POST /api/customer failed:', err instanceof Error ? err.message : err);
    return res.status(500).json({ error: 'Internal Server Error' });
  }
};
