"use client";

import { useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  AlertTriangle,
  ArrowLeft,
  FileText,
  ImageIcon,
  Loader2,
  MessageSquare,
  Sparkles,
  Upload,
  X,
} from "lucide-react";

import { importCandidate } from "@/lib/api";
import { getToken } from "@/lib/auth";

function cn(...classes: Array<string | false | null | undefined>): string {
  return classes.filter(Boolean).join(" ");
}

export default function ImportCandidatePage() {
  const router = useRouter();
  const params = useParams();
  const projectId = params.id as string;

  const [listingText, setListingText] = useState("");
  const [chatText, setChatText] = useState("");
  const [noteText, setNoteText] = useState("");
  const [uploadedImages, setUploadedImages] = useState<File[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadingMessage, setLoadingMessage] = useState("");
  const [error, setError] = useState("");
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const handleImport = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (!listingText.trim() && !chatText.trim() && !noteText.trim() && uploadedImages.length === 0) {
      setError("Please paste text or upload at least one image.");
      return;
    }

    const token = getToken();
    if (!token) {
      router.push("/login");
      return;
    }

    setLoading(true);
    setLoadingMessage(uploadedImages.length > 0 ? "Uploading images..." : "Extracting and assessing...");
    const stageOneTimer =
      uploadedImages.length > 0
        ? window.setTimeout(() => setLoadingMessage("Running OCR on uploaded images..."), 800)
        : null;
    const stageTwoTimer = window.setTimeout(
      () => setLoadingMessage(uploadedImages.length > 0 ? "Queueing OCR and assessment..." : "Queueing assessment..."),
      uploadedImages.length > 0 ? 2200 : 1000
    );
    try {
      const candidate = await importCandidate(token, projectId, {
        source_type:
          uploadedImages.length > 0
            ? listingText || chatText || noteText
              ? "mixed"
              : "image_upload"
            : listingText && chatText
              ? "mixed"
              : listingText
                ? "manual_text"
                : "chat_log",
        raw_listing_text: listingText || undefined,
        raw_chat_text: chatText || undefined,
        raw_note_text: noteText || undefined,
        uploaded_images: uploadedImages,
      });
      router.push(`/projects/${projectId}/candidates/${candidate.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to import candidate.");
    } finally {
      if (stageOneTimer) window.clearTimeout(stageOneTimer);
      window.clearTimeout(stageTwoTimer);
      setLoading(false);
      setLoadingMessage("");
    }
  };

  const removeImage = (name: string, size: number) => {
    setUploadedImages((imgs) => imgs.filter((f) => !(f.name === name && f.size === size)));
  };

  const inputCls =
    "w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 shadow-sm focus:outline-none focus:ring-2 focus:ring-gray-900/10 focus:border-gray-500";

  return (
    <main className="relative min-h-screen overflow-hidden bg-gray-50">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 h-[360px] bg-gradient-to-br from-violet-100 via-blue-50 to-emerald-50"
      />
      <div className="relative mx-auto w-full max-w-3xl px-4 py-10 lg:px-6">
        <Link
          href={`/projects/${projectId}`}
          className="mb-5 inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to project
        </Link>

        <div className="mb-6 flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gray-900 text-white">
            <Sparkles className="h-5 w-5" />
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-violet-700">RentWise</p>
            <h1 className="text-xl font-semibold tracking-tight text-gray-900">Add a candidate</h1>
          </div>
        </div>
        <p className="mb-6 text-sm text-gray-600">
          Paste the listing text, agent chat, upload screenshots, or add your own notes. RentWise
          will extract the key details and decide what to verify next.
        </p>

        {error && (
          <div className="mb-4 flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">
            <AlertTriangle className="h-4 w-4 flex-none text-red-600" />
            <span>{error}</span>
          </div>
        )}
        {loadingMessage && (
          <div className="mb-4 flex items-center gap-2 rounded-lg border border-blue-200 bg-blue-50 p-3 text-sm text-blue-800">
            <Loader2 className="h-4 w-4 flex-none animate-spin text-blue-600" />
            <span>{loadingMessage}</span>
          </div>
        )}

        <form onSubmit={handleImport} className="space-y-5">
          <section className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
            <div className="mb-4 flex items-center gap-2 text-sm font-semibold text-gray-900">
              <FileText className="h-4 w-4 text-gray-500" />
              Paste listing content
            </div>
            <div className="space-y-4">
              <div>
                <label className="mb-1.5 block text-sm font-medium text-gray-700">Listing text</label>
                <textarea
                  value={listingText}
                  onChange={(e) => setListingText(e.target.value)}
                  rows={6}
                  className={inputCls}
                  placeholder="Paste the property ad or listing details here..."
                />
              </div>
              <div>
                <label className="mb-1.5 block text-sm font-medium text-gray-700">
                  Agent or landlord chat <span className="text-gray-400">(optional)</span>
                </label>
                <textarea
                  value={chatText}
                  onChange={(e) => setChatText(e.target.value)}
                  rows={4}
                  className={inputCls}
                  placeholder="Paste the conversation if it contains extra pricing or clause details..."
                />
              </div>
              <div>
                <label className="mb-1.5 block text-sm font-medium text-gray-700">
                  Your notes <span className="text-gray-400">(optional)</span>
                </label>
                <textarea
                  value={noteText}
                  onChange={(e) => setNoteText(e.target.value)}
                  rows={3}
                  className={inputCls}
                  placeholder="Add reminders, concerns, or context for this candidate..."
                />
              </div>
            </div>
          </section>

          <section className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
            <div className="mb-4 flex items-center gap-2 text-sm font-semibold text-gray-900">
              <ImageIcon className="h-4 w-4 text-gray-500" />
              Upload screenshots or photos
              <span className="ml-1 text-xs font-normal text-gray-400">optional</span>
            </div>
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept="image/png,image/jpeg,image/webp,image/bmp"
              onChange={(e) => setUploadedImages(Array.from(e.target.files || []))}
              className="hidden"
            />
            <div className="flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className="inline-flex items-center gap-1.5 rounded-lg border border-gray-300 bg-white px-3.5 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50"
              >
                <Upload className="h-4 w-4" />
                Choose images
              </button>
              <span className="text-sm text-gray-500">
                {uploadedImages.length > 0
                  ? `${uploadedImages.length} image${uploadedImages.length > 1 ? "s" : ""} selected`
                  : "No images selected yet"}
              </span>
            </div>
            {uploadedImages.length > 0 && (
              <ul className="mt-3 space-y-1.5">
                {uploadedImages.map((file) => (
                  <li
                    key={`${file.name}-${file.size}`}
                    className="flex items-center justify-between rounded-md bg-gray-50 px-2.5 py-1.5 text-sm text-gray-700"
                  >
                    <span className="truncate">{file.name}</span>
                    <button
                      type="button"
                      onClick={() => removeImage(file.name, file.size)}
                      className="ml-2 flex-none rounded p-0.5 text-gray-400 hover:bg-gray-200 hover:text-gray-600"
                      aria-label={`Remove ${file.name}`}
                    >
                      <X className="h-3.5 w-3.5" />
                    </button>
                  </li>
                ))}
              </ul>
            )}
            <p className="mt-3 text-xs text-gray-500">
              OCR and assessment continue in the background after upload, so you can move straight to the candidate detail view.
            </p>
          </section>

          <div className="flex items-center justify-end gap-3">
            <Link
              href={`/projects/${projectId}`}
              className="text-sm text-gray-600 hover:text-gray-900"
            >
              Cancel
            </Link>
            <button
              type="submit"
              disabled={loading}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-lg bg-gray-900 px-4 py-2 text-sm font-medium text-white shadow-sm transition hover:bg-black disabled:cursor-not-allowed disabled:opacity-60"
              )}
            >
              {loading && <Loader2 className="h-4 w-4 animate-spin" />}
              {loading ? "Processing..." : "Import and assess"}
            </button>
          </div>
        </form>

        <section className="mt-8 rounded-xl border border-gray-200 bg-white/60 p-5 shadow-sm">
          <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-gray-900">
            <MessageSquare className="h-4 w-4 text-gray-500" />
            What helps the analysis most
          </div>
          <ul className="ml-5 list-disc space-y-1 text-sm text-gray-600">
            <li>The quoted rent, deposit, management fee, and any extra charges.</li>
            <li>Lease term, move-in timing, and repair responsibility details.</li>
            <li>Screenshots from listings, chats, or contracts can be uploaded for OCR.</li>
            <li>Any notes that explain what makes this candidate attractive or risky.</li>
          </ul>
        </section>
      </div>
    </main>
  );
}
