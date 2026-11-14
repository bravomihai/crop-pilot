import Calculator from "@/components/calculator";

export default function Home() {
  return (
    <>
      <a className="skip-link" href="#calculator">Skip to calculator</a>
      <header className="masthead page-width">
        <a className="brand" href="/" aria-label="FieldShift — home">
          <span className="brand-mark" aria-hidden="true">
            <svg viewBox="0 0 32 32" fill="none">
              <path d="M8 23C5 12 11 6 25 7c1 13-6 20-17 16Z" stroke="currentColor" strokeWidth="2" />
              <path d="m7 26 13-13M12 21v-7m4 3h7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
            </svg>
          </span>
          FieldShift<span className="brand-dot">.</span>
        </a>
        <nav aria-label="Main navigation">
          <a href="#calculator">Calculator</a>
          <a href="#how-it-works">How it works</a>
        </nav>
        <span className="prototype-badge">Prototype · Space Apps 2026</span>
      </header>

      <main className="page-width">
        <section className="intro" aria-labelledby="page-title">
          <div>
            <p className="eyebrow"><span aria-hidden="true" /> CROP PLANNING</p>
            <h1 id="page-title">Your next crop.<br /><span>An informed choice.</span></h1>
            <p className="intro-description">
              Start with your land. Compare plans for three successive main crops
              and understand the timing, benefits, and trade-offs of each.
            </p>
            <a className="button button--primary" href="#calculator">
              Start planning <span aria-hidden="true">↗</span>
            </a>
            <p className="intro-note">No account needed. A fresh form every time.</p>
          </div>
          <aside className="journey" aria-label="What you will find in a plan">
            <p className="eyebrow">FROM FIELD TO PLAN</p>
            <ol>
              <li><span aria-hidden="true">01</span><div><strong>Your field's context</strong><p>The location and details you already know.</p></div></li>
              <li><span aria-hidden="true">02</span><div><strong>Three successive crops</strong><p>Sowing and harvest windows for each crop.</p></div></li>
              <li><span aria-hidden="true">03</span><div><strong>Alternatives to compare</strong><p>Benefits, trade-offs, and limitations explained.</p></div></li>
            </ol>
            <p className="journey-note">Three successive crops do not necessarily mean three years.</p>
          </aside>
        </section>

        <Calculator />

        <section className="how-it-works" id="how-it-works" aria-labelledby="help-title">
          <div>
            <p className="eyebrow">GOOD TO KNOW</p>
            <h2 id="help-title">A clearer path from information to decisions.</h2>
            <p className="muted">Understand your results and their limitations.</p>
          </div>
          <div className="help-questions">
            <details>
              <summary>Do I need to know everything about my field?</summary>
              <p>Start with the location and the date your field becomes available.
                Crop history and soil details are optional. Missing data and
                assumptions are highlighted in the results.</p>
            </details>
            <details>
              <summary>What do the three plans mean?</summary>
              <p>Each alternative contains three successive main crops. The duration
                depends on the crop calendar, and the plan does not repeat
                automatically. If fewer valid alternatives are available, the
                result will explain this limitation.</p>
            </details>
            <details>
              <summary>How should I read demo results?</summary>
              <p>Results marked “Demo” are fictional examples for the interface.
                Agronomic evaluation and real optimization are still in
                development. These examples are not recommendations calculated for your field.</p>
            </details>
          </div>
        </section>
      </main>

      <footer className="page-footer page-width">
        <div><strong>FieldShift.</strong><span>A fresh starting point for your field.</span></div>
        <p>Regional data provides context. Results require local agronomic review.</p>
      </footer>
    </>
  );
}
