import { Client } from 'pg';
import dotenv from 'dotenv';

dotenv.config();
const client = new Client({ connectionString: process.env.DB_URL });

(async () => {
  await client.connect();

  await client.query(`
    INSERT INTO customer (
      customer_id, store_id, first_name, last_name, email, address_id, active, create_date
    )
    VALUES (
      1, 1, 'Ситников', 'Митя', 'MITIASITNIKOV@teleworm.us', 576, 1, '2023-03-06T21:44:21.000Z'
    )
    ON CONFLICT (customer_id) DO NOTHING;
  `);

  await client.end();
})();
