/** @type {import('next').NextConfig} */
const nextConfig = {
  // Note: 'allowedDevOrigins' is often placed under 'experimental' in Next.js 15
  // but if the CLI warning persists, ensure the URL matches exactly.
  experimental: {
    allowedDevOrigins: ["http://172.30.240.1:3000"]
  }
};

module.exports = nextConfig;
