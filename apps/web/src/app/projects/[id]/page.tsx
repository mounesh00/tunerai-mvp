"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  api,
  Project,
  DatasetWithVersions,
  DatasetVersion,
} from "@/lib/api";

export default function ProjectDetailPage() {
  const params = useParams();
  const projectId = params.id as string;

  const [project, setProject] = useState<Project | null>(null);
  const [datasets, setDatasets] = useState<DatasetWithVersions[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [datasetName, setDatasetName] = useState("");
  const [uploading, setUploading] = useState(false);
  const [selectedReport, setSelectedReport] = useState<Record<string, unknown> | null>(null);

  const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null;

  const load = useCallback(async () => {
    if (!token) {
      window.location.href = "/login";
      return;
    }
    try {
      const [p, d] = await Promise.all([
        api.getProject(token, projectId),
        api.listDatasets(token, projectId),
      ]);
      setProject(p);
      setDatasets(d);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, [projectId, token]);

  useEffect(() => {
    load();
  }, [load]);

  async function createAndUpload(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!token || !datasetName.trim()) return;
    const fileInput = (e.target as HTMLFormElement).elements.namedItem(
      "file"
    ) as HTMLInputElement;
    const file = fileInput?.files?.[0];
    if (!file) {
      setError("Select a JSONL file");
      return;
    }
    setUploading(true);
    setError(null);
    try {
      const ds = await api.createDataset(token, {
        name: datasetName.trim(),
        project_id: projectId,
      });
      await api.uploadDataset(token, ds.id, file);
      setDatasetName("");
      fileInput.value = "";
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  async function showReport(dsId: string, version: DatasetVersion) {
    if (!token) return;
    try {
      const res = await api.getQualityReport(token, dsId, version.id);
      setSelectedReport(res.report);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load report");
    }
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
          <div className="flex items-center gap-4">
            <Link href="/dashboard" className="font-semibold tracking-tight">
              TunerAI
            </Link>
            <span className="text-[var(--muted-foreground)]">/</span>
            <span className="text-sm">{project?.name}</span>
          </div>
          <Link
            href="/dashboard"
            className="text-sm text-[var(--muted-foreground)] hover:text-white"
          >
            All projects
          </Link>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-6 py-10">
        <div className="mb-8">
          <h1 className="text-2xl font-semibold">{project?.name}</h1>
          <p className="mt-1 text-sm text-[var(--muted-foreground)]">
            {project?.domain || "No domain"} · {project?.status}
          </p>
        </div>

        {error && (
          <div className="mb-6 rounded-md border border-red-900/50 bg-red-950/30 px-4 py-3 text-sm text-red-200">
            {error}
          </div>
        )}

        <section className="mb-12">
          <h2 className="text-lg font-medium mb-4">Upload dataset</h2>
          <form
            onSubmit={createAndUpload}
            className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-5 space-y-4 max-w-xl"
          >
            <div>
              <label className="block text-sm mb-1.5">Dataset name</label>
              <input
                type="text"
                value={datasetName}
                onChange={(e) => setDatasetName(e.target.value)}
                placeholder="e.g. cybersec-v1"
                required
                className="w-full rounded-md border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm outline-none focus:border-blue-500"
              />
            </div>
            <div>
              <label className="block text-sm mb-1.5">JSONL file</label>
              <input
                type="file"
                name="file"
                accept=".jsonl,.json"
                required
                className="w-full text-sm text-[var(--muted-foreground)]"
              />
              <p className="mt-1 text-xs text-[var(--muted-foreground)]">
                Instruction or messages format. Max 100 MB.
              </p>
            </div>
            <button
              type="submit"
              disabled={uploading}
              className="rounded-md bg-[var(--primary)] px-4 py-2 text-sm font-medium text-white hover:bg-blue-600 disabled:opacity-50"
            >
              {uploading ? "Validating…" : "Upload & validate"}
            </button>
          </form>
        </section>

        <section>
          <h2 className="text-lg font-medium mb-4">Datasets</h2>
          {datasets.length === 0 ? (
            <p className="text-sm text-[var(--muted-foreground)]">
              No datasets yet. Upload a JSONL file to get a quality report.
            </p>
          ) : (
            <div className="space-y-4">
              {datasets.map((ds) => (
                <div
                  key={ds.id}
                  className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-5"
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="font-medium">{ds.name}</div>
                      <div className="text-sm text-[var(--muted-foreground)]">
                        Status: {ds.status}
                      </div>
                    </div>
                  </div>
                  {ds.versions?.length > 0 && (
                    <div className="mt-4 overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="text-left text-[var(--muted-foreground)] border-b border-[var(--border)]">
                            <th className="pb-2 pr-4">Version</th>
                            <th className="pb-2 pr-4">Records</th>
                            <th className="pb-2 pr-4">Valid</th>
                            <th className="pb-2 pr-4">Quality</th>
                            <th className="pb-2 pr-4">Format</th>
                            <th className="pb-2">Report</th>
                          </tr>
                        </thead>
                        <tbody className="font-mono text-xs">
                          {ds.versions.map((v) => (
                            <tr key={v.id} className="border-b border-[var(--border)]">
                              <td className="py-2 pr-4">{v.version}</td>
                              <td className="py-2 pr-4">{v.total_records ?? "—"}</td>
                              <td className="py-2 pr-4">{v.valid_records ?? "—"}</td>
                              <td className="py-2 pr-4">
                                {v.quality_score != null
                                  ? `${v.quality_score.toFixed(1)}`
                                  : "—"}
                              </td>
                              <td className="py-2 pr-4">{v.format}</td>
                              <td className="py-2">
                                <button
                                  type="button"
                                  onClick={() => showReport(ds.id, v)}
                                  className="text-blue-400 hover:underline"
                                >
                                  View
                                </button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </section>

        {selectedReport && (
          <div className="fixed inset-0 bg-black/60 flex items-center justify-center p-6 z-50">
            <div className="bg-[var(--card)] border border-[var(--border)] rounded-lg max-w-2xl w-full max-h-[80vh] overflow-auto p-6">
              <div className="flex justify-between items-center mb-4">
                <h3 className="font-medium">Quality report</h3>
                <button
                  type="button"
                  onClick={() => setSelectedReport(null)}
                  className="text-[var(--muted-foreground)] hover:text-white"
                >
                  Close
                </button>
              </div>
              <pre className="text-xs font-mono whitespace-pre-wrap text-[var(--muted-foreground)]">
                {JSON.stringify(selectedReport, null, 2)}
              </pre>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
