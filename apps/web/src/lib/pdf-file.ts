/** Checks file selection only; it does not parse or validate a PDF document. */
export async function pdfSelectionError(file: File): Promise<string | null> {
  if (!file.name.toLowerCase().endsWith(".pdf") || file.size > 10 * 1024 * 1024)
    return "Choose one PDF file, up to 10 MB.";
  if ((await file.slice(0, 5).text()) !== "%PDF-")
    return "This file does not have a valid PDF header.";
  return null;
}
