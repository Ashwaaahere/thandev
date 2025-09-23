// components/utils/base64urls.ts
export function b64urlEncode(input: string): string {
  if (!input) return "";
  const b64 = Buffer.from(input, "utf8").toString("base64");
  return b64.replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}

export function b64urlDecode(input: string): string {
  if (!input) return "";
  // allow both url-safe and standard base64
  let s = input.replace(/-/g, "+").replace(/_/g, "/");
  // pad
  while (s.length % 4 !== 0) s += "=";
  return Buffer.from(s, "base64").toString("utf8");
}
