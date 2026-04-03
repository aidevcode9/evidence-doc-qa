import { useMDXComponents as getDocsMDXComponents } from 'nextra-theme-docs'
import type { MDXComponents } from 'mdx/types'

export const useMDXComponents = (components?: MDXComponents): MDXComponents => ({
  ...getDocsMDXComponents({}),
  ...components,
})
