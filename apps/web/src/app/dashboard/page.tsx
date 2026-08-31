"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, Project, User } from "@/lib/api";

export default function DashboardPage() {
  const [user, setUser] = useState<User | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [newName, setNewName] = useState("");
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (!token) {
      window.location.href = "/login";
      return;
    }
    Promise.all([api.me(token), api.listProjects(token)])
      .then(([u, p]) => {
        setUser(u);
        setProjects(p);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    const token = localStorage.getItem("access_token");
    if (!token || !newName.trim()) return;
    setCreating(true);
    try {
      const project = await api.createProject(token, { name: newName.trim() });
      setProjects((prev) => [project, ...prev]);
      setNewName("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create project");
    } finally {
      setCreating(false);
    }
  }

  function logout() {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    window.location.href = "/";
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center text-[var(--muted-foreground)]">
        Loading…
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      <header className="border-b border-[var(--border)]">
        <div className="mx-auto max-w-6xl px-6 h-14 flex items-center justify-between">
          <Link href="/dashboard" className="font-semibold tracking-tight">
            TunerAI
          </Link>
          <div className="flex items-center gap-4 text-sm">
            <span className="text-[var(--muted-foreground)]">{user?.email}</span>
            <button
              onClick={logout}
              className="text-[var(--muted-foreground)] hover:text-white transition"
            >
              Sign out
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-6 py-10">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-semibold">Projects</h1>
            <p className="mt-1 text-sm text-[var(--muted-foreground)]">
              Domain adaptation workspaces
            </p>
          </div>
        </div>

        {error && (
          <div className="mb-6 rounded-md border border-red-900/50 bg-red-950/30 px-4 py-3 text-sm text-red-200">
            {error}
          </div>
        )}

        <form onSubmit={handleCreate} className="mb-8 flex gap-3">
          <input
            type="text"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="New project name"
            className="flex-1 rounded-md border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-sm outline-none focus:border-blue-500"
          />
          <button
            type="submit"
            disabled={creating || !newName.trim()}
            className="rounded-md bg-[var(--primary)] px-4 py-2 text-sm font-medium text-white hover:bg-blue-600 disabled:opacity-50 transition"
          >
            {creating ? "Creating…" : "Create Model / Project"}
          </button>
        </form>

        {projects.length === 0 ? (
          <div className="rounded-lg border border-dashed border-[var(--border)] p-12 text-center">
            <p className="text-[var(--muted-foreground)]">
              No projects yet. Create one to start adapting a model to your domain.
            </p>
          </div>
        ) : (
          <div className="grid gap-3">
            {projects.map((p) => (
              <Link
                key={p.id}
                href={`/projects/${p.id}`}
                className="rounded-lg border border-[var(--border)] bg-[var(--card)] px-5 py-4 hover:border-zinc-600 transition flex items-center justify-between"
              >
                <div>
                  <div className="font-medium">{p.name}</div>
                  <div className="mt-0.5 text-sm text-[var(--muted-foreground)]">
                    {p.domain || "No domain set"} · {p.status}
                  </div>
                </div>
                <span className="text-xs font-mono text-[var(--muted-foreground)]">
                  {p.slug}
                </span>
              </Link>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
