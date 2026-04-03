import { Footer, Layout, Navbar } from 'nextra-theme-docs'
import { Head } from 'nextra/components'
import { getPageMap } from 'nextra/page-map'
import 'nextra-theme-docs/style.css'

export const metadata = {
  title: 'Evidence-Bound Docs',
  description: 'Enterprise Document Q&A with Verified Citations',
}

const navbar = (
  <Navbar
    logo={<span style={{ fontWeight: 800 }}>Evidence-Bound</span>}
    projectLink="https://github.com/aidevcode9/evidence-doc-qa"
  />
)

const footer = <Footer>Evidence-Bound Documentation — bound.legal</Footer>

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" dir="ltr" suppressHydrationWarning>
      <Head />
      <body>
        <Layout
          navbar={navbar}
          footer={footer}
          pageMap={await getPageMap()}
          docsRepositoryBase="https://github.com/aidevcode9/evidence-doc-qa/tree/main/docs"
        >
          {children}
        </Layout>
      </body>
    </html>
  )
}
