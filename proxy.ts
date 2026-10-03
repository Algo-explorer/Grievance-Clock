import {clerkMiddleware} from '@clerk/nextjs/server';
import {NextResponse, type NextRequest, type NextFetchEvent} from 'next/server';

const clerk=clerkMiddleware();
export default async function proxy(request:NextRequest,event:NextFetchEvent){
 // The API verifies signed tokens independently. Missing configuration never
 // enables guest access; it only lets the setup-unavailable page render.
 if(process.env.AUTH_MODE==='local'&&process.env.APP_ENV!=='production')return NextResponse.next();
 if(!process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY||!process.env.CLERK_SECRET_KEY)return NextResponse.next();
 const response=await clerk(request,event);
 // Clerk decorates a same-URL rewrite with verified auth request headers.
 // Next 16 can normalize that URL to localhost while serving 127.0.0.1,
 // turning it into a proxy back to itself. Resume the original route instead;
 // retain every Clerk auth/cookie header and all actual redirects/rewrites.
 if(response&&response.headers.get('x-middleware-rewrite')===request.url){
  response.headers.delete('x-middleware-rewrite');
  response.headers.set('x-middleware-next','1');
 }
 return response;
}
export const config={matcher:['/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)','/(api|trpc)(.*)']};
