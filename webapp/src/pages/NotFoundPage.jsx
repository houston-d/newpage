import { Link } from "react-router-dom";

export default function NotFoundPage() {
  return (
    <main className="page">
      <div className="not-found">
        <h1>Page not found</h1>
        <p>Go to the jobs page to see available roles.</p>
        <Link to="/jobs">Open /jobs</Link>
      </div>
    </main>
  );
}
