import type { Metadata } from 'next';
import {ClerkProvider} from '@clerk/nextjs';
import AccountBoundary from './AccountBoundary';
import './globals.css';
export const metadata: Metadata = {title:'Grievance Clock — Your next step, made clear',description:'An accessible investor grievance assistant. Explain your problem, prepare evidence and keep track of the next step.',icons:{icon:'/favicon.svg'}};
export default function RootLayout({children}:{children:React.ReactNode}) {
 const local=process.env.AUTH_MODE==='local'&&process.env.APP_ENV!=='production';
 const configured=!!process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY&&!!process.env.CLERK_SECRET_KEY;
 return <html lang="en"><body>{local?children:configured?<ClerkProvider localization={{signIn:{start:{title:"Sign in to Grievance Clock",titleCombined:"Sign in to Grievance Clock"},emailCode:{subtitle:"to continue to Grievance Clock"}},signUp:{start:{title:"Create your Grievance Clock account",titleCombined:"Create your Grievance Clock account"}}}} signInForceRedirectUrl="/" signUpForceRedirectUrl="/"><AccountBoundary>{children}</AccountBoundary></ClerkProvider>:<main className="account-welcome"><div className="account-card"><span className="eyebrow">GRIEVANCE CLOCK</span><h1>Sign-in is being set up.</h1><p>Your workspace will be available once account services are connected. Please check back shortly.</p></div></main>}</body></html>;
}
