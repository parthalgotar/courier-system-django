import React from "react";

export function Card({ children, className = "", hover = false, ...props }) {
  return (
    <div
      className={`bg-paper-card border border-paper-line rounded-lg ${hover ? "card-hover" : ""} ${className}`}
      {...props}
    >
      {children}
    </div>
  );
}

export function Button({ children, variant = "primary", className = "", ...props }) {
  const base =
    "inline-flex items-center justify-center gap-2 rounded-md px-4 py-2 text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed select-none";
  const variants = {
    primary: "bg-freight text-white hover:bg-freight-dark btn-primary",
    ghost:   "bg-transparent text-ink border border-paper-line hover:bg-paper btn-ghost",
    danger:  "bg-alert text-white hover:opacity-90 btn-danger",
  };
  return (
    <button className={`${base} ${variants[variant]} ${className}`} {...props}>
      {children}
    </button>
  );
}

export function Input({ label, className = "", ...props }) {
  return (
    <label className="flex flex-col gap-1.5 text-sm">
      {label && <span className="font-medium text-ink-soft">{label}</span>}
      <input
        className={`rounded-md border border-paper-line bg-white px-3 py-2 text-sm text-ink placeholder:text-ink-faint focus:border-freight outline-none ${className}`}
        {...props}
      />
    </label>
  );
}

export function Select({ label, className = "", children, ...props }) {
  return (
    <label className="flex flex-col gap-1.5 text-sm">
      {label && <span className="font-medium text-ink-soft">{label}</span>}
      <select
        className={`rounded-md border border-paper-line bg-white px-3 py-2 text-sm text-ink focus:border-freight outline-none ${className}`}
        {...props}
      >
        {children}
      </select>
    </label>
  );
}

export function ErrorBanner({ message }) {
  if (!message) return null;
  return (
    <div className="rounded-md border border-alert/30 bg-alert-soft px-4 py-3 text-sm text-alert mb-4 scale-in">
      {message}
    </div>
  );
}

export function EmptyState({ title, hint }) {
  return (
    <div className="border border-dashed border-paper-line rounded-lg py-16 text-center scale-in">
      <p className="font-display text-ink font-medium">{title}</p>
      {hint && <p className="text-sm text-ink-faint mt-1">{hint}</p>}
    </div>
  );
}
