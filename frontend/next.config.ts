import type { NextConfig } from 'next';
const backend=(process.env.BACKEND_URL||'http://127.0.0.1:8000').replace(/\/$/,'');
if(process.env.VERCEL && !process.env.BACKEND_URL)throw new Error('Set BACKEND_URL to the Render HTTPS service URL before building on Vercel.');
const target=new URL(backend);
if(target.username||target.password||target.search||target.hash||target.pathname!=='/')throw new Error('BACKEND_URL must be an origin without credentials, query or /api path.');
if(process.env.VERCEL && target.protocol!=='https:')throw new Error('Render BACKEND_URL must use HTTPS.');
const config: NextConfig = {
  turbopack: { root: __dirname },
  poweredByHeader: false,
  async rewrites() { return [{source:'/api/:path*', destination:`${backend}/api/:path*`}]; },
  async headers() { return [{source:'/:path*',headers:[{key:'X-Content-Type-Options',value:'nosniff'},{key:'Referrer-Policy',value:'strict-origin-when-cross-origin'},{key:'X-Frame-Options',value:'DENY'}]}]; }
};
export default config;
