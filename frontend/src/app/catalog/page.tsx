import { AppShell } from "@/components/layout/AppShell"
import { PageHeader } from "@/components/common/PageHeader"
import { CatalogImport } from "@/components/catalog/CatalogImport"
import { CatalogTable } from "@/components/catalog/CatalogTable"

export default function CatalogPage() {
  return (
    <AppShell>
      <div className="mx-auto w-full max-w-4xl px-6 py-8">
        <PageHeader title="Material & Labor Catalog" />
        <CatalogImport />
        <div className="mt-8">
          <CatalogTable />
        </div>
      </div>
    </AppShell>
  )
}
