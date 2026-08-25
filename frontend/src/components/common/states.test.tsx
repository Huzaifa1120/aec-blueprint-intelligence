import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"
import { EmptyState } from "./EmptyState"
import { ErrorState } from "./ErrorState"
import { LoadingSpinner } from "./LoadingSpinner"
import { PageHeader } from "./PageHeader"
import { AppShell } from "@/components/layout/AppShell"

describe("state components", () => {
  it("EmptyState renders title, description and fires action", async () => {
    const onClick = vi.fn()
    const user = userEvent.setup()
    render(
      <EmptyState
        title="No rates added yet."
        description="Import a CSV to start pricing your estimates."
        action={
          <button type="button" onClick={onClick}>
            Import CSV
          </button>
        }
      />,
    )
    expect(screen.getByText("No rates added yet.")).toBeInTheDocument()
    expect(screen.getByText("Import a CSV to start pricing your estimates.")).toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Import CSV" }))
    expect(onClick).toHaveBeenCalledOnce()
  })

  it("ErrorState renders named failure copy with alert role", () => {
    render(<ErrorState description="Processing stopped during Cluster symbols." />)
    const alert = screen.getByRole("alert")
    expect(alert).toHaveTextContent("Processing stopped during Cluster symbols.")
  })

  it("LoadingSpinner exposes an aria-labelled busy indicator", () => {
    render(<LoadingSpinner />)
    expect(screen.getByRole("status")).toHaveAttribute("aria-label", "Loading")
  })

  it("PageHeader renders title and action slot", () => {
    render(
      <PageHeader
        title="Material & Labor Catalog"
        actions={<button type="button">Import</button>}
      />,
    )
    expect(
      screen.getByRole("heading", { level: 1, name: "Material & Labor Catalog" }),
    ).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Import" })).toBeInTheDocument()
  })

  it("AppShell renders chrome with brand link and right slot", () => {
    render(
      <AppShell right={<span>Export ▾</span>}>
        <main>workspace</main>
      </AppShell>,
    )
    expect(screen.getByRole("link", { name: "Huzaifa AEC home" })).toHaveAttribute("href", "/")
    expect(screen.getByRole("link", { name: "Estimates" })).toHaveAttribute("href", "/estimates")
    expect(screen.getByRole("link", { name: "Catalog" })).toHaveAttribute("href", "/catalog")
    expect(screen.getByText("Export ▾")).toBeInTheDocument()
    expect(screen.getByText("workspace")).toBeInTheDocument()
  })
})
