import React, { useEffect } from "react";
import Sidebar from "./Sidebar.jsx";

export default function Layout({ title, eyebrow, action, children }) {
  useEffect(() => {
    if (title) {
      document.title = `${title} | ERP Console`;
    }
  }, [title]);

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="flex-1 px-10 py-8 page-enter">
        <header className="flex items-start justify-between mb-8">
          <div>
            {eyebrow && (
              <p className="font-mono text-xs uppercase tracking-[0.2em] text-freight mb-1">
                {eyebrow}
              </p>
            )}
            <h2 className="font-display text-2xl font-semibold text-ink">{title}</h2>
          </div>
          {action}
        </header>
        {children}
      </main>
    </div>
  );
}
