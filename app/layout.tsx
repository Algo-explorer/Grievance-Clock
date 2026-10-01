import type { Metadata } from 'next';
import './globals.css';
export const metadata: Metadata = {title:'Grievance Clock — Your next step, made clear',description:'An accessible investor grievance assistant. Explain your problem, prepare evidence and keep track of the next step.',icons:{icon:'/favicon.svg'}};
export default function RootLayout({children}:{children:React.ReactNode}) { return <html lang="en"><body>{children}</body></html>; }
