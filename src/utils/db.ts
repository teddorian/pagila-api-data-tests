import { Pool } from 'pg';
import dotenv from 'dotenv';

dotenv.config();

const connectionString = process.env.DB_URL;
if (!connectionString) {
  throw new Error('DB_URL is not defined in environment');
}

// 🔁 создаём пул соединений
const pool = new Pool({ connectionString });

// 🧠 обёртка для запросов с логированием
export const query = async (text: string, params?: any[]) => {
  const start = Date.now();
  try {
    const res = await pool.query(text, params);
    const duration = Date.now() - start;
    console.log(`SQL: ${text} | ⏱ ${duration}ms`);
    return res;
  } catch (err) {
    console.error(`SQL Error: ${text}`, err);
    throw err;
  }
};
