// Static export only (ADR 0008 D5): no Node server, served by the demo API from web/out.
// Pages Router: the App Router's export inlines <script> tags the strict CSP would block.
/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "export",
  trailingSlash: true,
  images: { unoptimized: true },
  poweredByHeader: false,
  reactStrictMode: true,
  productionBrowserSourceMaps: false,
};
export default nextConfig;
