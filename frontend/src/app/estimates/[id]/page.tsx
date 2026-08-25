import type { Metadata } from "next"
import EstimateClient from "./EstimateClient"

export const metadata: Metadata = {
  title: "Takeoff workspace — Huzaifa AEC",
}

export default async function EstimatePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params
  return <EstimateClient estimateId={id} />
}
