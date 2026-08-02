import { AuthShell, LoginForm } from "../../components/auth/auth-forms";

export default function LoginPage() {
  return <AuthShell title="Log in to Yoranix" subtitle="Access your AI knowledge workspace securely."><LoginForm /></AuthShell>;
}
