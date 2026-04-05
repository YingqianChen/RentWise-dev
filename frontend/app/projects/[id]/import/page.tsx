"use client";

import { useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";

import { importCandidate } from "@/lib/api";
import { getToken } from "@/lib/auth";

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

  return (
    <main className="min-h-screen p-8">
      <div className="max-w-2xl mx-auto">
        <Link
          href={`/projects/${projectId}`}
          className="text-sm text-gray-500 hover:text-gray-700 mb-4 inline-block"
        >
          Back to project
        </Link>

        <h1 className="text-2xl font-bold text-gray-900 mb-2">Add a candidate</h1>
        <p className="text-gray-600 mb-6">
          Paste the listing text, agent chat, upload screenshots, or add your own notes. RentWise will extract
          the key details and decide what to verify next.
        </p>

        {error && <div className="mb-4 p-3 bg-red-50 text-red-700 rounded-lg text-sm">{error}</div>}
        {loadingMessage && (
          <div className="mb-4 p-3 bg-blue-50 text-blue-700 rounded-lg text-sm">
            {loadingMessage}
          </div>
        )}

        <form onSubmit={handleImport} className="space-y-6">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Listing text</label>
            <textarea
              value={listingText}
              onChange={(e) => setListingText(e.target.value)}
              rows={6}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
              placeholder="Paste the property ad or listing details here..."
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Agent or landlord chat (optional)</label>
            <textarea
              value={chatText}
              onChange={(e) => setChatText(e.target.value)}
              rows={4}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
              placeholder="Paste the conversation if it contains extra pricing or clause details..."
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Your notes (optional)</label>
            <textarea
              value={noteText}
              onChange={(e) => setNoteText(e.target.value)}
              rows={3}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
              placeholder="Add reminders, concerns, or context for this candidate..."
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Listing screenshots or photos (optional)</label>
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
                className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition"
              >
                Choose images
              </button>
              <span className="text-sm text-gray-500">
                {uploadedImages.length > 0
                  ? `${uploadedImages.length} image${uploadedImages.length > 1 ? "s" : ""} selected`
                  : "No images selected yet"}
              </span>
            </div>
            {uploadedImages.length > 0 && (
              <ul className="mt-3 space-y-1 text-sm text-gray-600">
                {uploadedImages.map((file) => (
                  <li key={`${file.name}-${file.size}`}>{file.name}</li>
                ))}
              </ul>
            )}
            <p className="mt-2 text-xs text-gray-500">
              OCR and assessment now continue in the background after upload, so you can move straight to the candidate detail view instead of waiting on this page.
            </p>
          </div>

          <div className="flex gap-3">
            <button
              type="submit"
              disabled={loading}
              className="px-6 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50 transition"
            >
              {loading ? "Processing..." : "Import and assess"}
            </button>
            <Link
              href={`/projects/${projectId}`}
              className="px-6 py-2 text-gray-600 hover:text-gray-900 transition"
            >
              Cancel
            </Link>
          </div>
        </form>

        <div className="mt-8 p-4 bg-gray-50 rounded-lg">
          <h3 className="font-medium text-gray-900 mb-2">What helps the analysis most</h3>
          <ul className="text-sm text-gray-600 space-y-1 list-disc list-inside">
            <li>The quoted rent, deposit, management fee, and any extra charges.</li>
            <li>Lease term, move-in timing, and repair responsibility details.</li>
            <li>Screenshots from listings, chats, or contracts can be uploaded for OCR.</li>
            <li>Any notes that explain what makes this candidate attractive or risky.</li>
          </ul>
        </div>
      </div>
    </main>
  );
}
