import { Suspense } from "react";
import ResearchApp from "./_components/research-app";

export default function Home() {
  return <Suspense fallback={<main className="boot">Opening research workspace…</main>}><ResearchApp /></Suspense>;
}
