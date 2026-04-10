"use client";

import Image from "next/image";
import Link from "next/link";
import { useMemo, useState } from "react";

type Meal = {
  id: string;
  name: string;
  time: string;
  calories: string;
  protein: string;
};

type JournalDay = {
  id: string;
  day: string;
  date: string;
  meals: Meal[];
};

const initialJournalEntries: JournalDay[] = [
  {
    id: "today",
    day: "Today",
    date: "April 6, 2026",
    meals: [
      {
        id: "m1",
        name: "Eggs and Toast",
        time: "8:10 AM",
        calories: "430 kcal",
        protein: "22g",
      },
      {
        id: "m2",
        name: "Grilled Chicken Bowl",
        time: "1:15 PM",
        calories: "620 kcal",
        protein: "48g",
      },
      {
        id: "m3",
        name: "Protein Shake",
        time: "4:20 PM",
        calories: "280 kcal",
        protein: "30g",
      },
      {
        id: "m4",
        name: "Salmon Rice Plate",
        time: "7:45 PM",
        calories: "510 kcal",
        protein: "42g",
      },
    ],
  },
  {
    id: "yesterday",
    day: "Yesterday",
    date: "April 5, 2026",
    meals: [
      {
        id: "m5",
        name: "Greek Yogurt Bowl",
        time: "9:00 AM",
        calories: "350 kcal",
        protein: "20g",
      },
      {
        id: "m6",
        name: "Turkey Sandwich",
        time: "1:05 PM",
        calories: "540 kcal",
        protein: "34g",
      },
      {
        id: "m7",
        name: "Chicken Alfredo",
        time: "8:00 PM",
        calories: "760 kcal",
        protein: "41g",
      },
      {
        id: "m8",
        name: "Casein Shake",
        time: "10:15 PM",
        calories: "390 kcal",
        protein: "28g",
      },
    ],
  },
];

const DAILY_GOAL = 2300;
const CARB_ESTIMATE = 165;
const FAT_ESTIMATE = 54;

function parseNumber(value: string) {
  const num = parseInt(value.replace(/[^\d]/g, ""), 10);
  return isNaN(num) ? 0 : num;
}

function formatCalories(total: number) {
  return `${total.toLocaleString()} kcal`;
}

function formatProtein(total: number) {
  return `${total}g`;
}

export default function JournalPage() {
  const [journalEntries, setJournalEntries] =
    useState<JournalDay[]>(initialJournalEntries);

  const handleSaveMeal = (
    dayId: string,
    mealId: string,
    updatedMeal: { name: string; calories: string; protein: string }
  ) => {
    setJournalEntries((prev) =>
      prev.map((day) =>
        day.id === dayId
          ? {
              ...day,
              meals: day.meals.map((meal) =>
                meal.id === mealId ? { ...meal, ...updatedMeal } : meal
              ),
            }
          : day
      )
    );
  };

  const handleDeleteMeal = (dayId: string, mealId: string) => {
    setJournalEntries((prev) =>
      prev.map((day) =>
        day.id === dayId
          ? {
              ...day,
              meals: day.meals.filter((meal) => meal.id !== mealId),
            }
          : day
      )
    );
  };

  const todayEntry = journalEntries[0];

  const todayCalories = useMemo(() => {
    if (!todayEntry) return 0;
    return todayEntry.meals.reduce(
      (sum, meal) => sum + parseNumber(meal.calories),
      0
    );
  }, [todayEntry]);

  const todayProtein = useMemo(() => {
    if (!todayEntry) return 0;
    return todayEntry.meals.reduce(
      (sum, meal) => sum + parseNumber(meal.protein),
      0
    );
  }, [todayEntry]);

  const weeklyCalories = useMemo(() => {
    return journalEntries.reduce(
      (sum, day) =>
        sum +
        day.meals.reduce((mealSum, meal) => mealSum + parseNumber(meal.calories), 0),
      0
    );
  }, [journalEntries]);

  const averageProtein = useMemo(() => {
    if (journalEntries.length === 0) return 0;

    const totalProteinAcrossDays = journalEntries.reduce(
      (sum, day) =>
        sum +
        day.meals.reduce((mealSum, meal) => mealSum + parseNumber(meal.protein), 0),
      0
    );

    return Math.round(totalProteinAcrossDays / journalEntries.length);
  }, [journalEntries]);

  const remainingCalories = Math.max(DAILY_GOAL - todayCalories, 0);
  const progressPercent = Math.min((todayCalories / DAILY_GOAL) * 100, 100);

  return (
    <main className="relative min-h-screen overflow-x-hidden bg-gradient-to-b from-[#0b1220] via-[#0b1220] to-[#07121a] text-white">
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute -top-20 left-1/2 h-[520px] w-[520px] -translate-x-1/2 rounded-full bg-emerald-500/15 blur-[140px]" />
        <div className="absolute top-40 left-0 h-[360px] w-[360px] rounded-full bg-sky-500/10 blur-[120px]" />
        <div className="absolute bottom-10 right-0 h-[420px] w-[420px] rounded-full bg-emerald-500/10 blur-[140px]" />
      </div>

      <header className="relative z-20 mx-auto flex max-w-6xl items-center justify-between px-6 py-6">
        <Link href="/" className="flex items-center gap-3">
          <Image
            src="/vocalorie-icon.png"
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
          <Link href="/logger" className="hover:text-white">
            Logger
          </Link>
          <Link href="/journal" className="text-emerald-300">
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

      <section className="relative z-10 mx-auto max-w-6xl px-6 pb-20 pt-8">
        <div className="mb-10 flex flex-col gap-6 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="text-sm uppercase tracking-[0.2em] text-emerald-300/80">
              Journal
            </p>
            <h1 className="mt-3 text-4xl font-semibold tracking-tight md:text-5xl">
              Your food journal
            </h1>
            <p className="mt-4 max-w-2xl text-lg text-white/70">
              Review your meal history, daily totals, and protein intake in one
              clean timeline.
            </p>
          </div>

          <div className="grid grid-cols-2 gap-4 md:w-[340px]">
            <SummaryCard label="This week" value={formatCalories(weeklyCalories)} />
            <SummaryCard label="Avg protein" value={formatProtein(averageProtein)} />
          </div>
        </div>

        <div className="grid gap-8 lg:grid-cols-[1.05fr_0.95fr]">
          <div className="space-y-8">
            {journalEntries.map((entry) => {
              const dayTotal = entry.meals.reduce(
                (sum, meal) => sum + parseNumber(meal.calories),
                0
              );

              return (
                <div
                  key={entry.id}
                  className="rounded-[32px] bg-white/5 p-6 ring-1 ring-white/10 backdrop-blur"
                >
                  <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
                    <div>
                      <p className="text-sm text-emerald-300/80">{entry.day}</p>
                      <h2 className="mt-1 text-2xl font-semibold">{entry.date}</h2>
                    </div>

                    <div className="rounded-2xl bg-black/20 px-4 py-3 ring-1 ring-white/10">
                      <p className="text-xs uppercase tracking-wide text-white/50">
                        Total calories
                      </p>
                      <p className="mt-1 text-xl font-semibold text-emerald-300">
                        {formatCalories(dayTotal)}
                      </p>
                    </div>
                  </div>

                  <div className="mt-6 space-y-4">
                    {entry.meals.length > 0 ? (
                      entry.meals.map((meal) => (
                        <MealRow
                          key={meal.id}
                          dayId={entry.id}
                          meal={meal}
                          onSave={handleSaveMeal}
                          onDelete={handleDeleteMeal}
                        />
                      ))
                    ) : (
                      <div className="rounded-3xl bg-black/20 p-5 ring-1 ring-white/10">
                        <p className="text-sm text-white/60">
                          No meals logged for this day.
                        </p>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          <div className="space-y-6">
            <div className="rounded-[32px] bg-white/5 p-6 ring-1 ring-white/10 backdrop-blur">
              <p className="text-sm text-white/60">Daily progress</p>
              <h2 className="mt-1 text-2xl font-semibold">Today at a glance</h2>

              <div className="mt-6 rounded-3xl bg-black/20 p-5 ring-1 ring-white/10">
                <div className="flex items-end justify-between">
                  <div>
                    <p className="text-sm text-white/60">Calories consumed</p>
                    <p className="mt-2 text-4xl font-semibold text-emerald-300">
                      {todayCalories.toLocaleString()}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm text-white/60">Goal</p>
                    <p className="mt-2 text-lg font-medium text-white/90">
                      {formatCalories(DAILY_GOAL)}
                    </p>
                  </div>
                </div>

                <div className="mt-6 h-2 w-full rounded-full bg-white/10">
                  <div
                    className="h-2 rounded-full bg-emerald-400"
                    style={{ width: `${progressPercent}%` }}
                  />
                </div>

                <p className="mt-2 text-xs text-white/50">
                  {remainingCalories.toLocaleString()} kcal remaining
                </p>
              </div>

              <div className="mt-6 grid grid-cols-3 gap-4">
                <MacroCard label="Protein" value={formatProtein(todayProtein)} />
                <MacroCard label="Carbs" value={formatProtein(CARB_ESTIMATE)} />
                <MacroCard label="Fats" value={formatProtein(FAT_ESTIMATE)} />
              </div>
            </div>

            <div className="rounded-[32px] bg-white/5 p-6 ring-1 ring-white/10 backdrop-blur">
              <p className="text-sm text-white/60">Recent trends</p>
              <h2 className="mt-1 text-2xl font-semibold">Consistency</h2>

              <div className="mt-6 space-y-4">
                <InsightRow
                  title="Most logged day"
                  value={journalEntries[0]?.day || "N/A"}
                />
                <InsightRow
                  title="Average daily calories"
                  value={
                    journalEntries.length > 0
                      ? formatCalories(Math.round(weeklyCalories / journalEntries.length))
                      : "0 kcal"
                  }
                />
                <InsightRow title="Strongest macro" value="Protein" />
                <InsightRow title="Meals tracked" value={`${todayEntry?.meals.length || 0} today`} />
              </div>
            </div>

            <div className="rounded-[32px] bg-white/5 p-6 ring-1 ring-white/10 backdrop-blur">
              <p className="text-sm text-white/60">Journal tips</p>
              <ul className="mt-4 space-y-3 text-sm text-white/75">
                <li>• Voice logs appear here once confirmed.</li>
                <li>• Daily totals update automatically.</li>
                <li>• Meals can be edited or removed before integration.</li>
              </ul>
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}

function SummaryCard({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-2xl bg-white/5 p-4 ring-1 ring-white/10">
      <p className="text-xs uppercase tracking-wide text-white/50">{label}</p>
      <p className="mt-2 text-lg font-semibold text-white">{value}</p>
    </div>
  );
}

function MealRow({
  dayId,
  meal,
  onSave,
  onDelete,
}: {
  dayId: string;
  meal: Meal;
  onSave: (
    dayId: string,
    mealId: string,
    updatedMeal: { name: string; calories: string; protein: string }
  ) => void;
  onDelete: (dayId: string, mealId: string) => void;
}) {
  const [isEditing, setIsEditing] = useState(false);
  const [mealName, setMealName] = useState(meal.name);
  const [mealCalories, setMealCalories] = useState(meal.calories);
  const [mealProtein, setMealProtein] = useState(meal.protein);

  const handleSave = () => {
    onSave(dayId, meal.id, {
      name: mealName,
      calories: mealCalories,
      protein: mealProtein,
    });
    setIsEditing(false);
  };

  const handleCancel = () => {
    setMealName(meal.name);
    setMealCalories(meal.calories);
    setMealProtein(meal.protein);
    setIsEditing(false);
  };

  return (
    <div className="rounded-3xl bg-black/20 p-5 ring-1 ring-white/10">
      {!isEditing ? (
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <h3 className="text-lg font-medium text-white">{mealName}</h3>
            <p className="mt-1 text-sm text-white/55">{meal.time}</p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <Pill label={mealProtein} />
            <Pill label={mealCalories} highlight />

            <button
              onClick={() => setIsEditing(true)}
              className="rounded-full bg-white/10 px-3 py-2 text-xs text-white ring-1 ring-white/10 transition hover:bg-white/15"
            >
              Edit
            </button>

            <button
              onClick={() => onDelete(dayId, meal.id)}
              className="rounded-full bg-red-500/10 px-3 py-2 text-xs text-red-300 ring-1 ring-red-500/20 transition hover:bg-red-500/15"
            >
              Delete
            </button>
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="grid gap-4 md:grid-cols-3">
            <input
              value={mealName}
              onChange={(e) => setMealName(e.target.value)}
              className="rounded-xl bg-white/10 px-3 py-3 text-sm text-white outline-none ring-1 ring-white/10 placeholder:text-white/40"
              placeholder="Meal name"
            />
            <input
              value={mealCalories}
              onChange={(e) => setMealCalories(e.target.value)}
              className="rounded-xl bg-white/10 px-3 py-3 text-sm text-white outline-none ring-1 ring-white/10 placeholder:text-white/40"
              placeholder="Calories"
            />
            <input
              value={mealProtein}
              onChange={(e) => setMealProtein(e.target.value)}
              className="rounded-xl bg-white/10 px-3 py-3 text-sm text-white outline-none ring-1 ring-white/10 placeholder:text-white/40"
              placeholder="Protein"
            />
          </div>

          <div className="flex gap-3">
            <button
              onClick={handleSave}
              className="flex-1 rounded-xl bg-emerald-500 py-3 text-sm font-semibold text-black transition hover:bg-emerald-400"
            >
              Save
            </button>

            <button
              onClick={handleCancel}
              className="flex-1 rounded-xl bg-white/10 py-3 text-sm text-white ring-1 ring-white/10 transition hover:bg-white/15"
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function Pill({
  label,
  highlight = false,
}: {
  label: string;
  highlight?: boolean;
}) {
  return (
    <span
      className={`rounded-full px-4 py-2 text-sm ring-1 ${
        highlight
          ? "bg-emerald-500/15 text-emerald-200 ring-emerald-500/20"
          : "bg-white/10 text-white/80 ring-white/10"
      }`}
    >
      {label}
    </span>
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

function InsightRow({
  title,
  value,
}: {
  title: string;
  value: string;
}) {
  return (
    <div className="flex items-center justify-between rounded-2xl bg-black/20 px-4 py-4 ring-1 ring-white/10">
      <p className="text-sm text-white/65">{title}</p>
      <p className="text-sm font-medium text-white">{value}</p>
    </div>
  );
}