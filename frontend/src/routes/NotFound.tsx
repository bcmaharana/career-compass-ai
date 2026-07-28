import { buttonVariants } from "@/components/ui/button-variants";
import { Link } from "react-router-dom";

export function NotFoundPage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-3 text-center">
      <h1 className="font-display text-3xl font-semibold">Page not found</h1>
      <p className="text-sm text-muted-foreground">
        The page you're looking for doesn't exist or may have moved.
      </p>
      <Link to="/" className={buttonVariants({ variant: "primary" })}>
        Back to dashboard
      </Link>
    </div>
  );
}
