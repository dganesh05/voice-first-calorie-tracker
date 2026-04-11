"use client";

import Image from "next/image";
import Link from "next/link";
import { useRef, useState } from "react";

type NutritionTotals = {
  calories: number | string;
  protein_g: number | string;
  carbs_g: number | string;
  fat_g: number | string;
  sugar_g: number | string;
  fiber_g: number | string;
  vitamin_d_mcg: number | string;
};

type SearchResultItem = {
  food: string;
  source?: string;
  source_item?: string;
} & NutritionTotals;

type SearchResponse = {
  query: string;
  results: SearchResultItem[];
  totals: NutritionTotals;
};

type VoiceResponse = SearchResponse & {
  transcript: string;
};

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export default function LoggerPage() {
  const [isListening, setIsListening] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [apiData, setApiData] = useState<SearchResponse | null>(null);
  const [error, setError] = useState("");
  const [selectedFood, setSelectedFood] = useState<SearchResultItem | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);

  const supportsSpeechRecognition =
    typeof window !== "undefined" &&
    ("SpeechRecognition" in window || "webkitSpeechRecognition" in window);

  const fetchByQuery = async (queryText: string) => {
    const response = await fetch(
      `${API_BASE_URL}/api/foods/search?query=${encodeURIComponent(queryText)}`
    );

    if (!response.ok) {
      throw new Error(`Backend request failed: ${response.status}`);
    }

    const data: SearchResponse = await response.json();
    setApiData(data);
  };

  const uploadRecordedAudio = async (blob: Blob) => {
    const formData = new FormData();
    const extension = blob.type.includes("ogg") ? "ogg" : "webm";
    formData.append("file", blob, `meal.${extension}`);

    const response = await fetch(`${API_BASE_URL}/api/voice`, {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      throw new Error(`Voice upload failed: ${response.status}`);
    }

    const data: VoiceResponse = await response.json();
    setTranscript(data.transcript || "");
    setApiData({ query: data.query, results: data.results, totals: data.totals });
  };

  const startMediaRecorderFallback = async () => {
    if (
      typeof navigator === "undefined" ||
      !navigator.mediaDevices ||
      typeof MediaRecorder === "undefined"
    ) {
      setError("This browser does not support audio recording.");
      return;
    }

    setError("");
    setIsListening(true);

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const candidates = ["audio/webm;codecs=opus", "audio/ogg;codecs=opus", "audio/webm"];
      const mimeType = candidates.find((type) => MediaRecorder.isTypeSupported(type));
      const recorder = mimeType
        ? new MediaRecorder(stream, { mimeType })
        : new MediaRecorder(stream);
      mediaRecorderRef.current = recorder;

      const chunks: BlobPart[] = [];

      recorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) {
          chunks.push(event.data);
        }
      };

      recorder.onerror = () => {
        setError("Audio recording failed.");
      };

      recorder.onstop = async () => {
        setIsListening(false);
        setIsProcessing(true);

        try {
          const recordedBlob = new Blob(chunks, {
            type: recorder.mimeType || "audio/webm",
          });
          await uploadRecordedAudio(recordedBlob);
        } catch (requestError: any) {
          setError(requestError.message ?? "Failed to transcribe audio.");
        } finally {
          setIsProcessing(false);
          mediaRecorderRef.current = null;
          stream.getTracks().forEach((track) => track.stop());
        }
      };

      recorder.start();
    } catch {
      setIsListening(false);
      setError("Microphone access was denied or unavailable.");
    }
  };

  const handleMicClick = async () => {
    if (isProcessing) {
      return;
    }

    if (!supportsSpeechRecognition && mediaRecorderRef.current && isListening) {
      mediaRecorderRef.current.stop();
      return;
    }

    const SpeechRecognitionConstructor =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

    if (!SpeechRecognitionConstructor) {
      await startMediaRecorderFallback();
      return;
    }

    setError("");
    setIsListening(true);
    const recognition = new SpeechRecognitionConstructor();
    recognition.lang = "en-US";
    recognition.interimResults = false;
    recognition.continuous = false;

    let finalTranscript = "";

    recognition.onresult = (event: any) => {
      finalTranscript = event.results[0][0].transcript;
      setTranscript(finalTranscript);
    };

    recognition.onerror = (event: any) => {
      setError(`Speech error: ${event.error}`);
      setIsListening(false);
    };

    recognition.onend = async () => {
      setIsListening(false);

      if (!finalTranscript.trim()) {
        return;
      }

      setIsProcessing(true);
      try {
        await fetchByQuery(finalTranscript);
      } catch (requestError: any) {
        setError(requestError.message ?? "Failed to fetch nutrition data.");
      } finally {
        setIsProcessing(false);
      }
    };

    recognition.start();
  };

  const formatValue = (value: number | string, suffix = "") => {
    if (typeof value === "number") {
      return `${Math.round(value * 100) / 100}${suffix}`;
    }

    return value;
  };

  const estimatedCalories = apiData
    ? formatValue(apiData.totals.calories, " kcal")
    : "--";
  const protein = apiData ? formatValue(apiData.totals.protein_g, "g") : "--";
  const carbs = apiData ? formatValue(apiData.totals.carbs_g, "g") : "--";
  const fats = apiData ? formatValue(apiData.totals.fat_g, "g") : "--";

  const closeFoodPopup = () => setSelectedFood(null);

  return (
    <main className="relative min-h-screen overflow-x-hidden bg-gradient-to-b from-[#0b1220] via-[#0b1220] to-[#07121a] text-white">
      {/* Background glow */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute -top-20 left-1/2 h-[520px] w-[520px] -translate-x-1/2 rounded-full bg-emerald-500/15 blur-[140px]" />
        <div className="absolute top-40 left-0 h-[360px] w-[360px] rounded-full bg-sky-500/10 blur-[120px]" />
        <div className="absolute bottom-10 right-0 h-[420px] w-[420px] rounded-full bg-emerald-500/10 blur-[140px]" />
      </div>

      {/* Navbar */}
      <header className="relative z-20 mx-auto flex max-w-6xl items-center justify-between px-6 py-6">
        <Link href="/" className="flex items-center gap-3">
          <Image
            src="/vocalorie-icon.PNG"
            alt="Vocalorie"
            width={150}
            height={150}
            className="object-contain drop-shadow-[0_0_14px_rgba(16,185,129,0.45)]"
            priority
          />
          <div className="leading-tight">
            <p className="text-sm text-white/70">Voice-first calorie tracking</p>
            <p className="text-lg font-semibold tracking-tight text-white">
              Vocalorie
            </p>
          </div>
        </Link>

        <nav className="hidden items-center gap-6 text-sm text-white/70 md:flex">
          <Link href="/" className="hover:text-white">
            Home
          </Link>
          <Link href="/logger" className="text-emerald-300">
            Logger
          </Link>
          <Link href="/journal" className="hover:text-white">
            Journal
          </Link>
          <Link href="/profile" className="hover:text-white">
            Profile
          </Link>
        </nav>

        <div className="flex items-center gap-3">
          <Link
            href="/login"
            className="rounded-full bg-white/10 px-4 py-2 text-sm text-white ring-1 ring-white/15 hover:bg-white/15"
          >
            Sign in
          </Link>
        </div>
      </header>

      {/* Page Content */}
      <section className="relative z-10 mx-auto max-w-6xl px-6 pb-20 pt-8">
        <div className="mb-10">
          <p className="text-sm uppercase tracking-[0.2em] text-emerald-300/80">
            Logger
          </p>
          <h1 className="mt-3 text-4xl font-semibold tracking-tight md:text-5xl">
            Log your meal with voice
          </h1>
          <p className="mt-4 max-w-2xl text-lg text-white/70">
            Tap the mic, describe your meal naturally, and let Vocalorie prepare
            the nutrition summary for confirmation.
          </p>
        </div>

        <div className="grid gap-8 lg:grid-cols-[1.1fr_0.9fr]">
          {/* Left Panel */}
          <div className="rounded-[32px] bg-white/5 p-6 ring-1 ring-white/10 backdrop-blur">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-white/60">Voice capture</p>
                <h2 className="mt-1 text-2xl font-semibold">Speak your meal</h2>
              </div>

              <span className="rounded-full bg-white/10 px-3 py-1 text-xs text-white/70 ring-1 ring-white/10">
                {isListening
                  ? "Listening..."
                  : isProcessing
                  ? "Processing..."
                  : "Ready"}
              </span>
            </div>

            <div className="relative mt-10 flex items-center justify-center">
              <div
                className={`absolute h-[260px] w-[260px] rounded-full blur-3xl transition ${
                  isListening
                    ? "bg-emerald-500/40 animate-pulse"
                    : isProcessing
                    ? "bg-sky-500/30"
                    : "bg-emerald-500/15"
                }`}
              />

              <button
                onClick={handleMicClick}
                className={`relative z-10 flex h-40 w-40 items-center justify-center rounded-full transition duration-300 ${
                  isListening
                    ? "scale-110 bg-emerald-500 shadow-[0_0_80px_rgba(16,185,129,0.55)]"
                    : isProcessing
                    ? "bg-sky-500 shadow-[0_0_70px_rgba(56,189,248,0.45)]"
                    : "bg-white/10 hover:scale-105 hover:bg-white/15"
                }`}
              >
                <Image
                  src="/vocalorie-mic.PNG"
                  alt="Vocalorie Mic"
                  width={90}
                  height={90}
                  className={`object-contain transition duration-300 ${
                    isListening ? "animate-pulse scale-110" : ""
                  }`}
                />
              </button>
            </div>

            <div className="mt-8 text-center">
              {error && (
                <p className="mb-4 text-sm font-medium text-red-300">{error}</p>
              )}

              {!supportsSpeechRecognition && (
                <p className="mb-3 text-xs text-white/60">
                  Firefox mode: tap once to record, tap again to stop and transcribe.
                </p>
              )}

              {!isListening && !isProcessing && (
                <>
                  <p className="text-lg font-medium text-white">
                    Tap the microphone to begin
                  </p>
                  <p className="mt-2 text-sm text-white/60">
                    Example: “I had two eggs, toast, and orange juice.”
                  </p>
                </>
              )}

              {isListening && (
                <>
                  <p className="text-lg font-medium text-emerald-300">
                    Listening...
                  </p>
                  <p className="mt-2 text-sm text-white/60">
                    Speak naturally. Vocalorie is capturing your meal.
                  </p>
                </>
              )}

              {isProcessing && (
                <>
                  <p className="text-lg font-medium text-sky-300">
                    Processing your meal...
                  </p>
                  <p className="mt-2 text-sm text-white/60">
                    Extracting foods, calories, and macros.
                  </p>
                </>
              )}
            </div>

            <div className="mt-10 rounded-3xl bg-black/20 p-5 ring-1 ring-white/10">
              <div className="flex items-center justify-between">
                <p className="text-sm font-medium text-white/80">Transcript</p>
                <span className="text-xs text-white/50">Preview</span>
              </div>
              <p className="mt-3 text-base leading-7 text-white/90">
                {transcript}
              </p>
            </div>
          </div>

          {/* Right Panel */}
          <div className="space-y-6">
            <div className="rounded-[32px] bg-white/5 p-6 ring-1 ring-white/10 backdrop-blur">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-white/60">Nutrition summary</p>
                  <h2 className="mt-1 text-2xl font-semibold">
                    Estimated meal
                  </h2>
                </div>
                <span className="rounded-full bg-emerald-500/15 px-3 py-1 text-xs text-emerald-200 ring-1 ring-emerald-500/20">
                  {apiData ? "Live backend" : "Awaiting input"}
                </span>
              </div>

              <div className="mt-6 rounded-3xl bg-black/20 p-5 ring-1 ring-white/10">
                <div className="flex items-end justify-between">
                  <div>
                    <p className="text-sm text-white/60">Total calories</p>
                    <p className="mt-2 text-4xl font-semibold text-emerald-300">
                      {estimatedCalories}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm text-white/60">Confidence</p>
                    <p className="mt-2 text-lg font-medium text-white/90">
                      94%
                    </p>
                  </div>
                </div>

                <div className="mt-6 h-2 w-full rounded-full bg-white/10">
                  <div className="h-2 w-[68%] rounded-full bg-emerald-400" />
                </div>

                <p className="mt-2 text-xs text-white/50">
                  Daily progress preview
                </p>
              </div>

              <div className="mt-6 grid grid-cols-3 gap-4">
                <MacroCard label="Protein" value={protein} />
                <MacroCard label="Carbs" value={carbs} />
                <MacroCard label="Fats" value={fats} />
              </div>

              <div className="mt-6 rounded-3xl bg-black/20 p-5 ring-1 ring-white/10">
                <p className="text-sm font-medium text-white/80">
                  Detected foods
                </p>
                <div className="mt-4 flex flex-wrap gap-3">
                  {apiData && apiData.results.length > 0 ? (
                    apiData.results.map((item, index) => (
                      <FoodPill
                        key={`${item.food}-${index}`}
                        label={item.food}
                        onClick={() => setSelectedFood(item)}
                      />
                    ))
                  ) : (
                    <span className="text-sm text-white/60">
                      Speak a meal to populate this list.
                    </span>
                  )}
                </div>

                {selectedFood && (
                  <div className="mt-4 rounded-2xl bg-[#0f1a25] p-4 ring-1 ring-emerald-400/30">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-sm text-white/60">Selected food</p>
                        <p className="text-base font-semibold text-white">{selectedFood.food}</p>
                      </div>
                      <button
                        onClick={closeFoodPopup}
                        className="rounded-lg bg-white/10 px-2 py-1 text-xs text-white/80 ring-1 ring-white/15 hover:bg-white/15"
                      >
                        Close
                      </button>
                    </div>

                    <p className="mt-3 text-xs text-white/60">
                      Source: {selectedFood.source || "Not Available"}
                    </p>
                    <p className="mt-1 text-xs text-white/60">
                      Resolver item: {selectedFood.source_item || "Not Available"}
                    </p>

                    <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-white/80">
                      <NutritionCell label="Calories" value={selectedFood.calories} />
                      <NutritionCell label="Protein" value={selectedFood.protein_g} suffix="g" />
                      <NutritionCell label="Carbs" value={selectedFood.carbs_g} suffix="g" />
                      <NutritionCell label="Fat" value={selectedFood.fat_g} suffix="g" />
                      <NutritionCell label="Sugar" value={selectedFood.sugar_g} suffix="g" />
                      <NutritionCell label="Fiber" value={selectedFood.fiber_g} suffix="g" />
                    </div>
                  </div>
                )}
              </div>

              <div className="mt-6 flex gap-4">
                <button className="flex-1 rounded-2xl bg-white/10 px-4 py-3 text-sm font-semibold text-white ring-1 ring-white/15 transition hover:bg-white/15">
                  Edit meal
                </button>
                <button className="flex-1 rounded-2xl bg-emerald-500 px-4 py-3 text-sm font-semibold text-[#08131a] transition hover:bg-emerald-400">
                  Confirm & Log
                </button>
              </div>
            </div>

            <div className="rounded-[32px] bg-white/5 p-6 ring-1 ring-white/10 backdrop-blur">
              <p className="text-sm text-white/60">Quick tips</p>
              <ul className="mt-4 space-y-3 text-sm text-white/75">
                <li>• Speak meals naturally, no need for perfect phrasing.</li>
                <li>• Include quantity when possible for better estimates.</li>
                <li>• You can edit the result before confirming.</li>
              </ul>
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}

function MacroCard({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-2xl bg-white/5 p-4 ring-1 ring-white/10">
      <p className="text-xs uppercase tracking-wide text-white/50">{label}</p>
      <p className="mt-2 text-xl font-semibold text-white">{value}</p>
    </div>
  );
}

function FoodPill({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="rounded-full bg-white/10 px-4 py-2 text-sm text-white/80 ring-1 ring-white/10 transition hover:bg-white/20"
    >
      {label}
    </button>
  );
}

function NutritionCell({
  label,
  value,
  suffix = "",
}: {
  label: string;
  value: number | string;
  suffix?: string;
}) {
  const displayValue =
    typeof value === "number" ? `${Math.round(value * 100) / 100}${suffix}` : value;

  return (
    <div className="rounded-xl bg-black/20 px-3 py-2 ring-1 ring-white/10">
      <p className="text-[11px] uppercase tracking-wide text-white/50">{label}</p>
      <p className="mt-1 text-sm font-medium text-white">{displayValue}</p>
    </div>
  );
}