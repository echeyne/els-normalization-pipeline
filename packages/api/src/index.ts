import { Hono } from "hono";
import { cors } from "hono/cors";

const app = new Hono();

app.use("/*", cors());

app.get("/api/health", (c) => {
  return c.json({ status: "ok" });
});

export default app;
