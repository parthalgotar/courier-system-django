import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";
import { Button, Input, Select, ErrorBanner, Card } from "../components/ui.jsx";

export default function Register() {
  const { register, login } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({
    email: "",
    full_name: "",
    password: "",
    role: "vendor",
  });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await register(form);
      await login({ email: form.email, password: form.password });
      navigate("/accounting");
    } catch (err) {
      setError(err.message || "Registration failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-console-bg flex items-center justify-center px-4">
      <Card className="w-full max-w-sm p-8">
        <p className="font-mono text-[11px] tracking-[0.2em] text-freight uppercase mb-1">
          Manifest
        </p>
        <h1 className="font-display text-xl font-semibold text-ink mb-6">
          Create your account
        </h1>
        <ErrorBanner message={error} />
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <Input
            label="Full name"
            required
            value={form.full_name}
            onChange={(e) => setForm({ ...form, full_name: e.target.value })}
            placeholder="Ada Lovelace"
          />
          <Input
            label="Email"
            type="email"
            required
            value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })}
            placeholder="user@erp.com"
          />
          <Input
            label="Password"
            type="password"
            required
            minLength={6}
            value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })}
            placeholder="At least 6 characters"
          />
          <Select
            label="Role"
            value={form.role}
            onChange={(e) => setForm({ ...form, role: e.target.value })}
          >
            <option value="vendor">Vendor (Shipper)</option>
            <option value="driver">Driver (Fleet)</option>
            <option value="dispatcher">Dispatcher</option>
          </Select>
          <Button type="submit" disabled={loading} className="mt-2">
            {loading ? "Creating…" : "Create account"}
          </Button>
        </form>
        <p className="text-sm text-ink-faint mt-6">
          Already have an account?{" "}
          <Link to="/login" className="text-freight font-medium hover:underline">
            Sign in
          </Link>
        </p>
      </Card>
    </div>
  );
}
