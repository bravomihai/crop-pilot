export default function Home() {
  return (
    <main style={{ fontFamily: "system-ui", padding: 24 }}>
      <h1>Field Shift API</h1>
      <p>
        Backend only. The app is the React frontend. Endpoints are listed in <code>contracts/api.md</code>; try{" "}
        <a href="/api/health">/api/health</a>.
      </p>
    </main>
  );
}
