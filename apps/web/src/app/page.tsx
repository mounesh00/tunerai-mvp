import Link from "next/link";

export default function Home() {
  return (
    <div className="min-h-screen flex flex-col">
      <header className="border-b border-[var(--border)]">
        <div className="mx-auto max-w-6xl px-6 h-14 flex items-center justify-between">
          <span className="font-semibold tracking-tight">TunerAI</span>
          <nav className="flex items-center gap-4 text-sm">
            <Link
              href="/docs"
              className="text-[var(--muted-foreground)] hover:text-white transition"
            >
              Documentation
            </Link>
            <Link
              href="/login"
              className="text-[var(--muted-foreground)] hover:text-white transition"
            >
              Sign in
            </Link>
            <Link
              href="/register"
              className="rounded-md bg-[var(--primary)] px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-600 transition"
            >
              Start tuning
            </Link>
          </nav>
        </div>
      </header>

      <main className="flex-1">
        <section className="mx-auto max-w-6xl px-6 pt-24 pb-16">
          <h1 className="text-4xl sm:text-5xl font-semibold tracking-tight max-w-2xl leading-tight">
            Tune AI to your domain.
          </h1>
          <p className="mt-5 text-lg text-[var(--muted-foreground)] max-w-xl">
            Turn specialized data into measurable, deployable domain-specialized
            AI models — with validation, QLoRA fine-tuning, rigorous evaluation,
            and OpenAI-compatible deployment.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link
              href="/register"
              className="rounded-md bg-[var(--primary)] px-5 py-2.5 text-sm font-medium text-white hover:bg-blue-600 transition"
            >
              Start tuning
            </Link>
            <Link
              href="/docs"
              className="rounded-md border border-[var(--border)] px-5 py-2.5 text-sm font-medium hover:bg-[var(--muted)] transition"
            >
              View documentation
            </Link>
          </div>
        </section>

        <section className="mx-auto max-w-6xl px-6 py-12">
          <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
            {[
              { step: "1", title: "Data", desc: "Upload JSONL, validate quality, score readiness" },
              { step: "2", title: "Tune", desc: "QLoRA / SFT on supported open-weight models" },
              { step: "3", title: "Evaluate", desc: "Base vs tuned comparison on held-out benchmarks" },
              { step: "4", title: "Deploy", desc: "OpenAI-compatible API with versioning" },
            ].map((item) => (
              <div
                key={item.step}
                className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-5"
              >
                <div className="text-xs font-mono text-[var(--muted-foreground)] mb-2">
                  {item.step}
                </div>
                <div className="font-medium">{item.title}</div>
                <p className="mt-1 text-sm text-[var(--muted-foreground)]">{item.desc}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="mx-auto max-w-6xl px-6 py-12 border-t border-[var(--border)]">
          <h2 className="text-lg font-medium mb-4">Example evaluation</h2>
          <p className="text-sm text-[var(--muted-foreground)] mb-4 max-w-2xl">
            Every tuned model is compared against its base model. Results are
            honest — if tuning does not improve the benchmark, TunerAI reports
            that explicitly.
          </p>
          <div className="rounded-lg border border-[var(--border)] bg-[var(--card)] overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--border)] text-left text-[var(--muted-foreground)]">
                  <th className="px-4 py-3 font-medium">Metric</th>
                  <th className="px-4 py-3 font-medium">Base</th>
                  <th className="px-4 py-3 font-medium">Tuned</th>
                  <th className="px-4 py-3 font-medium">Delta</th>
                </tr>
              </thead>
              <tbody className="font-mono text-xs">
                <tr className="border-b border-[var(--border)]">
                  <td className="px-4 py-3">Domain accuracy</td>
                  <td className="px-4 py-3">62.4%</td>
                  <td className="px-4 py-3">78.1%</td>
                  <td className="px-4 py-3 text-[var(--success)]">+15.7</td>
                </tr>
                <tr className="border-b border-[var(--border)]">
                  <td className="px-4 py-3">Instruction following</td>
                  <td className="px-4 py-3">81.0%</td>
                  <td className="px-4 py-3">84.2%</td>
                  <td className="px-4 py-3 text-[var(--success)]">+3.2</td>
                </tr>
                <tr>
                  <td className="px-4 py-3">Safety (pass rate)</td>
                  <td className="px-4 py-3">94.0%</td>
                  <td className="px-4 py-3">93.5%</td>
                  <td className="px-4 py-3 text-[var(--warning)]">−0.5</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p className="mt-3 text-xs text-[var(--muted-foreground)]">
            Illustrative layout only. Real numbers come from your held-out
            evaluation set after training.
          </p>
        </section>
      </main>

      <footer className="border-t border-[var(--border)] py-8">
        <div className="mx-auto max-w-6xl px-6 text-sm text-[var(--muted-foreground)]">
          TunerAI — domain adaptation for production open-source LLMs
        </div>
      </footer>
    </div>
  );
}
