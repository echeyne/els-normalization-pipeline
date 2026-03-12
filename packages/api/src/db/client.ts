import pg from "pg";

const { Pool } = pg;

// Connection pool — configured via environment variables
const pool = new Pool({
  host: process.env.DB_HOST ?? "localhost",
  port: Number(process.env.DB_PORT ?? 5432),
  database: process.env.DB_NAME ?? "els_corpus",
  user: process.env.DB_USER ?? "postgres",
  password: process.env.DB_PASSWORD ?? "",
  max: 20,
  idleTimeoutMillis: 30_000,
  connectionTimeoutMillis: 5_000,
});

// --- Low-level helpers ---

export async function query<T extends pg.QueryResultRow = pg.QueryResultRow>(
  text: string,
  params?: unknown[],
): Promise<pg.QueryResult<T>> {
  return pool.query<T>(text, params);
}

export async function queryOne<T extends pg.QueryResultRow = pg.QueryResultRow>(
  text: string,
  params?: unknown[],
): Promise<T | null> {
  const result = await pool.query<T>(text, params);
  return result.rows[0] ?? null;
}

export async function queryMany<
  T extends pg.QueryResultRow = pg.QueryResultRow,
>(text: string, params?: unknown[]): Promise<T[]> {
  const result = await pool.query<T>(text, params);
  return result.rows;
}

// --- CRUD helpers ---

/**
 * Build and execute a dynamic UPDATE statement.
 * Only columns present in `fields` are updated.
 * Returns the updated row or null if not found.
 */
export async function updateRow<
  T extends pg.QueryResultRow = pg.QueryResultRow,
>(
  table: string,
  id: number,
  fields: Record<string, unknown>,
  extraSets?: Record<string, unknown>,
): Promise<T | null> {
  const entries = Object.entries({ ...fields, ...extraSets }).filter(
    ([, v]) => v !== undefined,
  );
  if (entries.length === 0)
    return queryOne<T>(`SELECT * FROM ${table} WHERE id = $1`, [id]);

  const setClauses = entries.map(([col], i) => `${col} = $${i + 2}`);
  const values = entries.map(([, v]) => v);

  const sql = `UPDATE ${table} SET ${setClauses.join(", ")} WHERE id = $1 RETURNING *`;
  return queryOne<T>(sql, [id, ...values]);
}

/**
 * Delete a row by id. Returns true if a row was deleted.
 */
export async function deleteRow(table: string, id: number): Promise<boolean> {
  const result = await query(`DELETE FROM ${table} WHERE id = $1`, [id]);
  return (result.rowCount ?? 0) > 0;
}

// --- Lifecycle ---

export async function closePool(): Promise<void> {
  await pool.end();
}

export { pool };
