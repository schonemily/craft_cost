"use client";
import * as React from "react";
import { signIn } from "next-auth/react";
import toast from "react-hot-toast";
import { useRouter, useSearchParams } from "next/navigation";
import { useSession } from "next-auth/react";
import { Suspense } from "react";

function Face({ color, mouse, size = 140, width, height, variant = "circle", className = "" }: { color: string; mouse: { x: number; y: number } | null; size?: number; width?: number; height?: number; variant?: "circle" | "rect"; className?: string }) {
  const ref = React.useRef<HTMLDivElement | null>(null);
  const eyeRadius = 10;
  const pupilRadius = 5;
  const maxOffset = 6;
  const [leftPupil, setLeftPupil] = React.useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [rightPupil, setRightPupil] = React.useState<{ x: number; y: number }>({ x: 0, y: 0 });
  React.useEffect(() => {
    const el = ref.current;
    if (!el || !mouse) {
      setLeftPupil({ x: 0, y: 0 });
      setRightPupil({ x: 0, y: 0 });
      return;
    }
    const rect = el.getBoundingClientRect();
    const cx = rect.left + rect.width / 2;
    const cy = rect.top + rect.height / 2;
    const angle = Math.atan2(mouse.y - cy, mouse.x - cx);
    const ox = Math.cos(angle) * maxOffset;
    const oy = Math.sin(angle) * maxOffset;
    setLeftPupil({ x: ox, y: oy });
    setRightPupil({ x: ox, y: oy });
  }, [mouse]);
  const w = typeof width === "number" ? width : size;
  const h = typeof height === "number" ? height : size;
  const eyeStyle = (dx: number, dy: number) => ({ transform: `translate(${dx}px, ${dy}px)` });
  return (
    <div ref={ref} className={"relative " + (variant === "circle" ? "rounded-full" : "rounded-xl") + " " + className} style={{ width: w, height: h, background: color }}>
      <div className="absolute left-[30%] top-[35%] h-5 w-5 rounded-full bg-white flex items-center justify-center" style={{ width: eyeRadius * 2, height: eyeRadius * 2 }}>
        <div className="h-2.5 w-2.5 rounded-full bg-blue-400" style={{ width: pupilRadius * 2, height: pupilRadius * 2, ...eyeStyle(leftPupil.x, leftPupil.y) }} />
      </div>
      <div className="absolute right-[30%] top-[35%] h-5 w-5 rounded-full bg-white flex items-center justify-center" style={{ width: eyeRadius * 2, height: eyeRadius * 2 }}>
        <div className="h-2.5 w-2.5 rounded-full bg-blue-400" style={{ width: pupilRadius * 2, height: pupilRadius * 2, ...eyeStyle(rightPupil.x, rightPupil.y) }} />
      </div>
      <div className="absolute bottom-[25%] left-1/2 -translate-x-1/2 h-1 w-8 rounded-full bg-black/60" />
    </div>
  );
}

function LetterFace({ letter, mouse, width = 160, height = 200, gradFrom, gradTo, className = "" }: { letter: "C" | "F"; mouse: { x: number; y: number } | null; width?: number; height?: number; gradFrom?: string; gradTo?: string; className?: string }) {
  const ref = React.useRef<SVGSVGElement | null>(null);
  const [p, setP] = React.useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [t, setT] = React.useState(0);
  React.useEffect(() => {
    const el = ref.current;
    if (!el || !mouse) {
      setP({ x: 0, y: 0 });
      return;
    }
    const r = el.getBoundingClientRect();
    const cx = r.left + r.width / 2;
    const cy = r.top + r.height / 2;
    const angle = Math.atan2(mouse.y - cy, mouse.x - cx);
    const amp = Math.min(width, height) * 0.04;
    setP({ x: Math.cos(angle) * amp, y: Math.sin(angle) * amp });
  }, [mouse, width, height]);
  React.useEffect(() => {
    let raf = 0;
    const loop = (time: number) => {
      setT(time);
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, []);
  const id = React.useId();
  const from = gradFrom || "#FDE68A";
  const to = gradTo || "#F59E0B";
  const noseY = height * 0.5;
  const mouthY = height * 0.63;
  const mouthW = width * 0.28 + Math.abs(p.x) * 0.6;
  const smile = 18 + Math.abs(Math.sin(t / 700)) * 2;
  const mx1 = width / 2 - mouthW / 2;
  const mx2 = width / 2 + mouthW / 2;
  const eyeY = height * 0.42;
  const eyeDX = letter === "F" ? width * 0.06 : width * 0.1;
  const leftEyeX = width * 0.42 - eyeDX;
  const rightEyeX = width * 0.58 + (letter === "F" ? -eyeDX : 0);
  const eyeR = Math.max(10, Math.min(width, height) * 0.07);
  const pupilR = Math.max(5, eyeR * 0.45);
  const bob = Math.sin(t / 800) * 3;
  return (
    <svg ref={ref} width={width} height={height} viewBox={`0 0 ${width} ${height}`} className={"drop-shadow-2xl " + className} style={{ filter: "drop-shadow(0 14px 24px rgba(0,0,0,.35))", transform: `translateY(${bob}px)` }}>
      <defs>
        <linearGradient id={id + "-g"} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={from} />
          <stop offset="100%" stopColor={to} />
        </linearGradient>
        <radialGradient id={id + "-shine"} cx="30%" cy="20%" r="60%">
          <stop offset="0%" stopColor="#ffffff" stopOpacity="0.35" />
          <stop offset="100%" stopColor="#ffffff" stopOpacity="0" />
        </radialGradient>
        <clipPath id={id + "-clip"}>
          <text x={width / 2} y={height * 0.78} textAnchor="middle" fontWeight={900} fontFamily="Inter,ui-sans-serif,system-ui,Segoe UI,Arial" fontSize={height * 1.02}>{letter}</text>
        </clipPath>
      </defs>
      <text x={width / 2} y={height * 0.78} textAnchor="middle" fontWeight={900} fontFamily="Inter,ui-sans-serif,system-ui,Segoe UI,Arial" fontSize={height * 1.02} fill={`url(#${id}-g)`} stroke="#ffffff" strokeOpacity="0.25" strokeWidth={2}>{letter}</text>
      <g clipPath={`url(#${id}-clip)`}>
        <rect x={0} y={0} width={width} height={height} fill={`url(#${id}-shine)`} />
        <circle cx={leftEyeX} cy={eyeY} r={eyeR} fill="#ffffff" />
        <circle cx={rightEyeX} cy={eyeY} r={eyeR} fill="#ffffff" />
        <circle cx={leftEyeX + p.x} cy={eyeY + p.y} r={pupilR} fill="#3b82f6" />
        <circle cx={rightEyeX + p.x} cy={eyeY + p.y} r={pupilR} fill="#3b82f6" />
        <circle cx={leftEyeX + p.x - pupilR * 0.3} cy={eyeY + p.y - pupilR * 0.3} r={pupilR * 0.2} fill="#ffffff" fillOpacity="0.85" />
        <circle cx={rightEyeX + p.x - pupilR * 0.3} cy={eyeY + p.y - pupilR * 0.3} r={pupilR * 0.2} fill="#ffffff" fillOpacity="0.85" />
        <rect x={width * 0.48 - 4} y={noseY - 8} width={8} height={16} rx={3} fill="#111827" />
        <path d={`M ${mx1} ${mouthY} Q ${width * 0.5} ${mouthY + smile} ${mx2} ${mouthY}`} stroke="#111827" strokeWidth={5} strokeLinecap="round" fill="none" />
        <circle cx={mx1 + 6} cy={mouthY - 4} r={3} fill="#F87171" fillOpacity="0.6" />
        <circle cx={mx2 - 6} cy={mouthY - 4} r={3} fill="#F87171" fillOpacity="0.6" />
      </g>
    </svg>
  );
}

function SignInInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { data: session } = useSession();
  const [email, setEmail] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [loading, setLoading] = React.useState(false);
  const [sending, setSending] = React.useState(false);
  const [mouse, setMouse] = React.useState<{ x: number; y: number } | null>(null);

  React.useEffect(() => {
    if (session) {
      const cb = searchParams.get("callbackUrl") || "/";
      router.replace(cb);
    }
  }, [session, router, searchParams]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      const cb = searchParams.get("callbackUrl") || "/";
      const res = await signIn("credentials", {
        email,
        password,
        redirect: false,
        callbackUrl: cb,
      });
      if ((res as any)?.error || res === undefined) {
        toast.error("Invalid credentials");
      } else if ((res as any)?.ok || (res as any)?.url) {
        router.replace((res as any)?.url || cb);
      }
    } catch {
      toast.error("Sign-in failed");
    } finally {
      setLoading(false);
    }
  }

  async function onMagicLink(e: React.FormEvent) {
    e.preventDefault();
    if (!email) {
      toast.error("Enter your email first");
      return;
    }
    setSending(true);
    try {
      await signIn("email", { email, redirect: true, callbackUrl: "/" });
      toast.success("Check your email for a magic link");
    } catch {
      toast.error("Failed to send magic link");
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="mx-auto max-w-5xl grid grid-cols-1 md:grid-cols-2 gap-6 items-stretch" onPointerMove={(e) => setMouse({ x: e.clientX, y: e.clientY })} onPointerLeave={() => setMouse(null)}>
      <div className="hidden md:flex items-center justify-center rounded-2xl border border-[var(--border)]/60 bg-[var(--surface)]/60 p-5">
        <div className="relative w-full h-[380px] flex items-end justify-center gap-6">
          <div className="absolute top-3 left-0 right-0 text-center text-white/90 font-bold tracking-tight text-2xl md:text-3xl">Craft Your Cost's</div>
          <LetterFace letter="C" mouse={mouse} width={180} height={220} gradFrom="#FDBA74" gradTo="#FB923C" className="-mr-2" />
          <LetterFace letter="F" mouse={mouse} width={220} height={320} gradFrom="#C4B5FD" gradTo="#7C3AED" className="-ml-2 -mr-2" />
          <LetterFace letter="C" mouse={mouse} width={180} height={220} gradFrom="#FDE68A" gradTo="#F59E0B" className="-ml-2" />
        </div>
      </div>
      <div className="mx-auto w-full max-w-sm">
        <h1 className="text-2xl font-semibold text-white/90 mb-2">Welcome back</h1>
        <p className="text-sm text-[var(--muted)] mb-4">Please sign in to continue</p>
        <form onSubmit={onSubmit} className="space-y-3">
          <div>
            <label className="block text-sm text-[var(--muted)] mb-1">Email</label>
            <input
              type="email"
              className="w-full bg-transparent outline-none border border-[var(--border)]/60 rounded px-3 py-2"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>
          <div>
            <label className="block text-sm text-[var(--muted)] mb-1">Password</label>
            <input
              type="password"
              className="w-full bg-transparent outline-none border border-[var(--border)]/60 rounded px-3 py-2"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="w-full rounded bg-brand-600/80 hover:bg-brand-600 px-3 py-2 text-sm text-white"
          >
            {loading ? "Signing in…" : "Sign in"}
          </button>
          <div className="text-center text-xs text-[var(--muted)]">or</div>
          <button
            type="button"
            onClick={onMagicLink}
            disabled={sending}
            className="w-full rounded border border-[var(--border)]/60 px-3 py-2 text-sm hover:bg-white/5"
          >
            {sending ? "Sending…" : "Send magic link"}
          </button>
          <div className="my-2 text-center text-xs text-[var(--muted)]">— or continue with —</div>
          <button
            type="button"
            onClick={() => signIn("google", { callbackUrl: "/" })}
            className="w-full rounded border border-[var(--border)]/60 px-3 py-2 text-sm hover:bg-white/5 flex items-center justify-center gap-2"
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" className="h-4 w-4" aria-hidden="true"><path fill="#FFC107" d="M43.611,20.083H42V20H24v8h11.303c-1.649,4.657-6.08,8-11.303,8c-6.627,0-12-5.373-12-12s5.373-12,12-12 c3.059,0,5.842,1.154,7.961,3.039l5.657-5.657C33.63,6.053,29.043,4,24,4C12.955,4,4,12.955,4,24s8.955,20,20,20 s20-8.955,20-20C44,22.659,43.862,21.35,43.611,20.083z"/><path fill="#FF3D00" d="M6.306,14.691l6.571,4.819C14.655,16.108,18.961,14,24,14c3.059,0,5.842,1.154,7.961,3.039l5.657-5.657 C33.63,6.053,29.043,4,24,4C16.318,4,9.656,8.337,6.306,14.691z"/><path fill="#4CAF50" d="M24,44c5.166,0,9.86-1.977,13.409-5.197l-6.2-5.238C29.211,35.091,26.715,36,24,36 c-5.202,0-9.619-3.317-11.283-7.946l-6.536,5.036C9.5,39.556,16.227,44,24,44z"/><path fill="#1976D2" d="M43.611,20.083H42V20H24v8h11.303c-0.793,2.237-2.231,4.166-4.094,5.565c0.001-0.001,0.002-0.001,0.003-0.002 l6.2,5.238C36.271,39.205,44,34,44,24C44,22.659,43.862,21.35,43.611,20.083z"/></svg>
            <span>Continue with Google</span>
          </button>
          <button
            type="button"
            onClick={() => signIn("github", { callbackUrl: "/" })}
            className="w-full rounded border border-[var(--border)]/60 px-3 py-2 text-sm hover:bg-white/5 flex items-center justify-center gap-2"
          >
            <svg viewBox="0 0 16 16" version="1.1" aria-hidden="true" className="h-4 w-4 fill-white"><path fillRule="evenodd" d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"></path></svg>
            <span>Continue with GitHub</span>
          </button>
        </form>
      </div>
    </div>
  );
}

export default function SignInPage() {
  return (
    <Suspense fallback={<div className="mx-auto max-w-sm text-sm text-[var(--muted)]">Loading…</div>}>
      <SignInInner />
    </Suspense>
  );
}
