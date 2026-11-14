import Link from "next/link";
import Calculator from "@/components/calculator";
import ThemeControl from "@/components/theme-control";
import { fullExampleRequest } from "@/lib/api";

export default async function CalculatorPage({
  searchParams,
}: {
  searchParams: Promise<{ fixture?: string }>;
}) {
  const { fixture } = await searchParams;
  const mock = process.env.NEXT_PUBLIC_USE_MOCK_API === "true";
  return (
    <main className="calculator-page">
      <header className="analysis-page-header">
        <Link href="/">← FieldShift dashboard</Link>
        <ThemeControl />
      </header>
      <h1>Compare your next crop rotations</h1>
      <p>
        Use a location, your known history, and your priorities. Your current
        rotation is optional.
      </p>
      {mock && (
        <nav className="fixture-switch" aria-label="Development fixtures">
          <strong>DEMO · fixed examples</strong>
          <Link
            href="/calculator?fixture=default"
            aria-current={fixture !== "full" ? "page" : undefined}
          >
            Basic fixture
          </Link>
          <Link
            href="/calculator?fixture=full"
            aria-current={fixture === "full" ? "page" : undefined}
          >
            Full fixture with scores & baseline
          </Link>
          <Link href="/chart-previews">Future chart previews</Link>
        </nav>
      )}
      <Calculator
        key={fixture ?? "default"}
        initialRequest={
          mock && fixture === "full" ? fullExampleRequest : undefined
        }
      />
    </main>
  );
}
