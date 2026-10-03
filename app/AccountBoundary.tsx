'use client';
import {useUser,SignInButton,SignUpButton,UserButton} from '@clerk/nextjs';

export default function AccountBoundary({children}:{children:React.ReactNode}){
 const {isLoaded,isSignedIn,user}=useUser();
 if(!isLoaded)return <main className="account-welcome"><p>Opening your secure workspace…</p></main>;
 if(!isSignedIn)return <main className="account-welcome"><div className="account-card"><span className="eyebrow">GRIEVANCE CLOCK</span><h1>Your next step, saved securely.</h1><p>Sign in to keep your complaints, evidence and follow-ups together, and return to them from any device.</p><div className="account-actions"><SignInButton mode="modal"><button className="primary">Sign in</button></SignInButton><SignUpButton mode="modal"><button className="secondary">Create an account</button></SignUpButton></div><p className="account-note">Your complaints are private to your account. You choose whether to share content with AI.</p></div></main>;
 return <div key={user.id}><div className="account-bar"><span>Your private workspace</span><UserButton showName/></div>{children}</div>;
}
