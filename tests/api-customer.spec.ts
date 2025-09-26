import { test, expect, request } from '@playwright/test';
import { Client } from 'pg';
import dotenv from 'dotenv';

dotenv.config();

let client: Client;

test.beforeAll(async () => {
  client = new Client({ connectionString: process.env.DB_URL });
  await client.connect();
  console.log('Connected to PostgreSQL');
});

test.afterAll(async () => {
  await client.end();
  console.log('Disconnected from PostgreSQL');
});

test('Customer API matches database', async () => {
  const customerId = 1;

  // Получаем данные из API
  const apiContext = await request.newContext();
  const apiResponse = await apiContext.get(`http://localhost:3000/api/customer/${customerId}`);
  expect(apiResponse.ok()).toBeTruthy();

  const apiData = await apiResponse.json();

  // Получаем данные напрямую из базы
  const dbResult = await client.query('SELECT * FROM customer WHERE customer_id = $1', [customerId]);
  expect(dbResult.rowCount).toBe(1);

  const dbData = dbResult.rows[0];

  console.log('API Data:', apiData);
  console.log('DB Data:', dbData);

  // Сравниваем ключевые поля
  expect(apiData.first_name).toBe(dbData.first_name);
  expect(apiData.last_name).toBe(dbData.last_name);
  expect(apiData.email).toBe(dbData.email);
});
