export default function handler(req, res) {
  const app = String(req.query.app || "").toLowerCase();
  const ua = String(req.headers["user-agent"] || "");

  if (app !== "spotify") {
    res.statusCode = 302;
    res.setHeader("Location", "https://open.spotify.com/");
    res.end();
    return;
  }

  const isIOS = /iPhone|iPad|iPod/i.test(ua) || (/Macintosh/i.test(ua) && /Mobile/i.test(ua));
  const isWindows = /Windows NT/i.test(ua);

  if (isIOS) {
    res.statusCode = 302;
    res.setHeader("Location", "https://openinapp.link/w93c0");
    res.end();
    return;
  }

  if (isWindows) {
    res.statusCode = 302;
    res.setHeader("Location", "spotify:");
    res.end();
    return;
  }

  res.statusCode = 302;
  res.setHeader("Location", "https://open.spotify.com/");
  res.end();
}
