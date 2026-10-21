import { useEffect, useRef, useState, type FormEvent } from "react";
import { AuthLayout } from "../layouts/AuthLayout";
import { Alert, Button, FormField, Input } from "../components/ui";
import { auth, errorMessage } from "../services/api";
import { Link } from "../router";
import type { AuthResult } from "../types/api";

type GoogleCredential = { credential: string };
type GoogleIdentity = {
  accounts: { id: {
    initialize: (options: { client_id: string; callback: (response: GoogleCredential) => void }) => void;
    renderButton: (parent: HTMLElement, options: { theme: string; size: string; width: number; text: string }) => void;
  } };
};
declare global { interface Window { google?: GoogleIdentity } }

let googleScript: Promise<void> | undefined;
function loadGoogle(): Promise<void> {
  if (window.google) return Promise.resolve();
  googleScript ??= new Promise<void>((resolve, reject) => {
    const script = document.createElement("script");
    script.src = "https://accounts.google.com/gsi/client";
    script.async = true;
    script.onload = () => resolve();
    script.onerror = () => { googleScript = undefined; reject(new Error("Could not load Google sign-in")); };
    document.head.appendChild(script);
  });
  return googleScript;
}

export function AuthPage({ signUp = false, onSuccess }: { signUp?: boolean; onSuccess: (result: AuthResult) => void }) {
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [googleClientId, setGoogleClientId] = useState<string | null>(null);
  const googleButton = useRef<HTMLDivElement>(null);
  const success = useRef(onSuccess);
  success.current = onSuccess;

  useEffect(() => { auth.config().then((c) => setGoogleClientId(c.google_client_id)).catch(() => setGoogleClientId(null)); }, []);

  useEffect(() => {
    if (!googleClientId) return;
    let cancelled = false;
    loadGoogle().then(() => {
      const el = googleButton.current;
      if (cancelled || !window.google || !el) return;
      window.google.accounts.id.initialize({
        client_id: googleClientId,
        callback: async ({ credential }) => {
          setError(""); setLoading(true);
          try { success.current(await auth.google(credential)); }
          catch (e) { setError(errorMessage(e, "Google sign-in failed")); setLoading(false); }
        }
      });
      el.replaceChildren();
      window.google.accounts.id.renderButton(el, { theme: "outline", size: "large", width: 360, text: signUp ? "signup_with" : "signin_with" });
    }).catch((e) => !cancelled && setError(errorMessage(e)));
    return () => { cancelled = true; };
  }, [googleClientId, signUp]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(""); setLoading(true);
    const data = new FormData(event.currentTarget);
    const email = String(data.get("email") || "").trim();
    const password = String(data.get("password") || "");
    try {
      const result = signUp
        ? await auth.signup({ name: String(data.get("name") || "").trim(), email, password })
        : await auth.login({ email, password });
      onSuccess(result);
    } catch (e) {
      setError(errorMessage(e, "Unable to continue"));
      setLoading(false);
    }
  }

  return (
    <AuthLayout>
      <section className="auth-card">
        <h1>{signUp ? "Create your account" : "Welcome back"}</h1>
        <p className="muted">{signUp ? "Start your workspace in a minute." : "Sign in to your workspace."}</p>
        {googleClientId && <>
          <div ref={googleButton} style={{ display: "flex", justifyContent: "center", margin: "20px 0" }} />
          <div className="auth-divider"><span>or use email</span></div>
        </>}
        <form onSubmit={submit}>
          {signUp && <FormField label="Full name"><Input name="name" required maxLength={120} autoComplete="name" /></FormField>}
          <FormField label="Email"><Input name="email" type="email" required autoComplete="email" /></FormField>
          <FormField label="Password" hint={signUp ? "At least 8 characters" : undefined}>
            <Input name="password" type="password" required minLength={signUp ? 8 : 1} maxLength={128} autoComplete={signUp ? "new-password" : "current-password"} />
          </FormField>
          {error && <Alert tone="error">{error}</Alert>}
          <Button type="submit" loading={loading}>{signUp ? "Create account" : "Sign in"}</Button>
        </form>
        <div className="auth-footer">
          {signUp ? "Already have an account? " : "New to RegLens AI? "}
          <Link className="auth-link" href={signUp ? "#/signin" : "#/signup"}>{signUp ? "Sign in" : "Create an account"}</Link>
        </div>
      </section>
    </AuthLayout>
  );
}
