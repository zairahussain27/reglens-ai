import { useEffect, useState } from "react";

const read = () => window.location.hash.replace(/^#\/?/, "").split("?")[0] || "";

export function useRoute() {
  const [route, setRoute] = useState(read);
  useEffect(() => {
    const fn = () => setRoute(read());
    window.addEventListener("hashchange", fn);
    return () => window.removeEventListener("hashchange", fn);
  }, []);
  return route;
}

export const navigate = (route: string) => { window.location.hash = `#/${route}`; };

export function Link({ href, className, children, ...props }: React.AnchorHTMLAttributes<HTMLAnchorElement>) {
  return <a href={href} className={className} {...props}>{children}</a>;
}
