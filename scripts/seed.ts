import { Client } from 'pg';
import dotenv from 'dotenv';

dotenv.config();

const client = new Client({ connectionString: process.env.DB_URL });

(async () => {
  try {
    await client.connect();
    console.log('Connected to PostgreSQL');

    // Seed store
    await client.query(`
      INSERT INTO store (store_id, manager_staff_id, address_id)
      VALUES (1, 1, 1)
      ON CONFLICT (store_id) DO NOTHING;
    `);

    // Seed address
    await client.query(`
      INSERT INTO address (address_id, address, city_id, postal_code, phone)
      VALUES (576, 'Test Street 123', 1, '12345', '555-1234')
      ON CONFLICT (address_id) DO NOTHING;
    `);

    // Seed customer
    await client.query(`
      INSERT INTO customer (
        customer_id, store_id, first_name, last_name, email, address_id, active, create_date
      )
      VALUES (
        1, 1, 'Ситников', 'Митя', 'MITIASITNIKOV@teleworm.us', 576, true, '2023-03-06T21:44:21.000Z'
      )
      ON CONFLICT (customer_id) DO NOTHING;
    `);

    console.log('Seed complete');
  } catch (err) {
    console.error('Seed failed:', err instanceof Error ? err.message : err);
  } finally {
    await client.end();
    console.log('🧹 Disconnected from PostgreSQL');
  }
})();
