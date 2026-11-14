import { useEffect, useState } from "react";
import exampleFarm from "../../contracts/examples/farm-request.example.json";
import { analyze, getAnalysis, saveFarm } from "./api";
import FarmScreen from "./screens/FarmScreen";
import ProfileScreen from "./screens/ProfileScreen";
import ResultsScreen from "./screens/ResultsScreen";
import type { AnalysisResult, FarmRequest } from "./types";

type Step = "farm" | "profile" | "results";

// Three screens: select the field → fill in the profile → results.
// The farm starts from the example so every screen works before the map and form exist.
export default function App() {
  const [step, setStep] = useState<Step>("farm");
  const [farm, setFarm] = useState<FarmRequest>(exampleFarm as FarmRequest);
  const [result, setResult] = useState<AnalysisResult>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();

  // SMS links point to /r/<analysis_id>.
  useEffect(() => {
    const match = window.location.pathname.match(/^\/r\/([\w-]+)$/);
    if (match) {
      getAnalysis(match[1]).then((r) => { setResult(r); setStep("results"); }).catch((e) => setError(String(e.message ?? e)));
    }
  }, []);

  async function run(overrides: Pick<Partial<FarmRequest>, "priorities" | "scenario"> = {}) {
    setBusy(true);
    setError(undefined);
    try {
      const farm_id = await saveFarm(farm);
      setFarm({ ...farm, farm_id });
      setResult(await analyze(farm_id, overrides));
      setStep("results");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="app">
      <header>
        <h1>Field Shift</h1>
        <nav>
          <button disabled={step === "farm"} onClick={() => setStep("farm")}>1. Parcela</button>
          <button disabled={step === "profile"} onClick={() => setStep("profile")}>2. Profil</button>
          <button disabled={!result || step === "results"} onClick={() => setStep("results")}>3. Rezultate</button>
        </nav>
      </header>

      {error && <p className="error">{error}</p>}

      {step === "farm" && <FarmScreen farm={farm} onChange={setFarm} onNext={() => setStep("profile")} />}
      {step === "profile" && <ProfileScreen farm={farm} onChange={setFarm} onAnalyze={() => run()} busy={busy} />}
      {step === "results" && result && (
        <ResultsScreen result={result} farm={farm} busy={busy} onWhatIf={(overrides) => run(overrides)} />
      )}
    </main>
  );
}
