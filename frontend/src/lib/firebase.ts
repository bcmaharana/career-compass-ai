import { initializeApp } from "firebase/app";
import type { FirebaseApp } from "firebase/app";
import { getAuth } from "firebase/auth";
import type { Auth } from "firebase/auth";

/**
 * Firebase Phone Auth client init — used only by PhoneLoginForm.tsx.
 * Firebase owns the entire SMS/OTP lifecycle (sending the code, its own
 * reCAPTCHA-backed abuse protection, code expiry/retry limits); this app
 * never sees the code itself, only the resulting ID token, which the
 * backend verifies server-side (see
 * app/adapters/identity_providers/firebase_phone.py) before ever
 * trusting the phone number it claims.
 *
 * All of these values are safe to ship to the browser (Firebase's web
 * config is not a secret — it identifies the project, not a credential;
 * the actual security boundary is Firebase Auth's own rules plus this
 * app's own backend verifying the ID token). See frontend/.env.example
 * for where to find them in the Firebase console.
 */
const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
};

export class FirebaseNotConfiguredError extends Error {
  constructor() {
    super("Phone login isn't set up yet.");
    this.name = "FirebaseNotConfiguredError";
  }
}

let cachedAuth: Auth | null = null;
let cachedInitError: FirebaseNotConfiguredError | null = null;

/**
 * Lazily constructs the Firebase Auth client on first actual use — only
 * ever called from inside PhoneLoginForm's submit handlers, never at
 * module import time. Firebase's getAuth() throws synchronously
 * (auth/invalid-api-key) for an empty/invalid config; doing this
 * eagerly at import time — even just importing lib/firebase.ts, since
 * ES module top-level code always runs regardless of which LoginPage
 * tab is active — crashed the *entire* app, including the unrelated
 * email/password login path, before Firebase credentials were ever
 * configured. Every call after the first failure re-throws the same
 * cached FirebaseNotConfiguredError instead of hitting the SDK again.
 */
export function getFirebaseAuth(): Auth {
  if (cachedAuth) return cachedAuth;
  if (cachedInitError) throw cachedInitError;
  try {
    const app: FirebaseApp = initializeApp(firebaseConfig);
    cachedAuth = getAuth(app);
    return cachedAuth;
  } catch {
    cachedInitError = new FirebaseNotConfiguredError();
    throw cachedInitError;
  }
}
