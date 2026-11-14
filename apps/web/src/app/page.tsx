import Calculator from "@/components/calculator";
export default function Home() {
  return (
    <main>
      <header className="masthead">
        <a href="/">FieldShift</a>
        <span>Earth-to-farm intelligence</span>
      </header>
      <section className="intro">
        <p className="eyebrow">NASA SPACE APPS · PROTOTIP</p>
        <h1>Ce cultivi mai departe?</h1>
        <p>
          Introdu localizarea și ce cunoști despre teren. Compară trei planuri
          pentru următoarele trei culturi principale, cu calendarul și
          compromisurile fiecăruia.
        </p>
      </section>
      <Calculator />
      <footer>
        Datele regionale oferă context. Rezultatele necesită verificare
        agronomică locală.
      </footer>
    </main>
  );
}
