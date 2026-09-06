// Firebase web SDK setup. The web config is PUBLIC by design (it only identifies
// the project; it is not a secret). It is injected at build time via
// VITE_FIREBASE_CONFIG so the same code works locally and in deployment.
import { initializeApp, type FirebaseOptions } from "firebase/app";
import { getAuth } from "firebase/auth";

function loadConfig(): FirebaseOptions {
  const raw = import.meta.env.VITE_FIREBASE_CONFIG;
  if (!raw) {
    throw new Error(
      "VITE_FIREBASE_CONFIG is not set. Put your Firebase web config JSON in frontend/.env"
    );
  }
  return JSON.parse(raw) as FirebaseOptions;
}

const app = initializeApp(loadConfig());
export const auth = getAuth(app);
