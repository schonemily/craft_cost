import { DefaultSession } from "next-auth";

declare module "next-auth" {
  interface Session {
    apiToken?: string;
    user?: DefaultSession["user"] & {
      role?: string;
      plan?: string;
    };
  }
}

declare module "next-auth/jwt" {
  interface JWT {
    apiToken?: string;
    role?: string;
    plan?: string;
  }
}
