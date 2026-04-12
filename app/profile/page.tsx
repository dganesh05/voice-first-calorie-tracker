"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useState } from "react";
import { requireAccessTokenOrRedirect } from "../../lib/auth";
import { getSessionUser } from "../../lib/supabase";

export default function ProfilePage() {
  const [name, setName] = useState("Dev Bollam");
  const [email, setEmail] = useState("dev@example.com");

  const [age, setAge] = useState("22");
  const [sex, setSex] = useState("Male");
  const [heightFeet, setHeightFeet] = useState("5");
  const [heightInches, setHeightInches] = useState("10");
  const [weight, setWeight] = useState("180");

  const [activityLevel, setActivityLevel] = useState("Moderately Active");
  const [goal, setGoal] = useState("Lean Bulk");
  const [diet, setDiet] = useState("High Protein");

  const [dailyCalories, setDailyCalories] = useState("2300");
  const [proteinGoal, setProteinGoal] = useState("180");
  const [carbGoal, setCarbGoal] = useState("220");
  const [fatGoal, setFatGoal] = useState("70");

  const [useAutoGoals, setUseAutoGoals] = useState(true);
  const [isEditing, setIsEditing] = useState(false);

  const toNumber = (value: string) => {
    const num = Number(value);
    return Number.isFinite(num) ? num : 0;
  };

  const calculateGoals = () => {
    const ageNum = toNumber(age);
    const weightLb = toNumber(weight);
    const feet = toNumber(heightFeet);
    const inches = toNumber(heightInches);

    if (!ageNum || !weightLb || !feet) return;

    const weightKg = weightLb * 0.453592;
    const totalInches = feet * 12 + inches;
    const heightCm = totalInches * 2.54;

    let bmr = 0;

    if (sex === "Male") {
      bmr = 10 * weightKg + 6.25 * heightCm - 5 * ageNum + 5;
    } else {
      bmr = 10 * weightKg + 6.25 * heightCm - 5 * ageNum - 161;
    }

    let activityMultiplier = 1.2;
    if (activityLevel === "Lightly Active") activityMultiplier = 1.375;
    if (activityLevel === "Moderately Active") activityMultiplier = 1.55;
    if (activityLevel === "Very Active") activityMultiplier = 1.725;

    let calories = bmr * activityMultiplier;

    if (goal === "Fat Loss") calories -= 400;
    if (goal === "Maintenance") calories += 0;
    if (goal === "Lean Bulk") calories += 250;
    if (goal === "Muscle Gain") calories += 400;

    calories = Math.round(calories);

    let proteinPerLb = 0.8;
    if (goal === "Fat Loss") proteinPerLb = 1.0;
    if (goal === "Lean Bulk") proteinPerLb = 0.95;
    if (goal === "Muscle Gain") proteinPerLb = 1.0;

    let protein = Math.round(weightLb * proteinPerLb);
    let fat = Math.round((calories * 0.25) / 9);
    let carbs = Math.round((calories - protein * 4 - fat * 9) / 4);

    if (diet === "High Protein") {
      protein = Math.round(protein * 1.1);
      carbs = Math.round(carbs * 0.92);
    }

    if (diet === "Low Carb") {
      carbs = Math.round(carbs * 0.65);
      fat = Math.round((calories - protein * 4 - carbs * 4) / 9);
    }

    if (diet === "Keto") {
      carbs = Math.round((calories * 0.08) / 4);
      fat = Math.round((calories - protein * 4 - carbs * 4) / 9);
    }

    if (diet === "Vegetarian") {
      carbs = Math.round(carbs * 1.05);
    }

    if (diet === "Vegan") {
      protein = Math.round(protein * 0.92);
      carbs = Math.round(carbs * 1.1);
    }

    setDailyCalories(String(Math.max(calories, 1200)));
    setProteinGoal(String(Math.max(protein, 0)));
    setCarbGoal(String(Math.max(carbs, 0)));
    setFatGoal(String(Math.max(fat, 0)));
  };

  useEffect(() => {
    const loadUser = async () => {
      const accessToken = await requireAccessTokenOrRedirect();
      if (!accessToken) {
        return;
      }

      const user = await getSessionUser();
      if (!user) {
        return;
      }

      if (user.fullName) {
        setName(user.fullName);
      }

      if (user.email) {
        setEmail(user.email);
      }
    };

    loadUser();
  }, []);

  useEffect(() => {
    if (useAutoGoals) {
      calculateGoals();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    age,
    sex,
    heightFeet,
    heightInches,
    weight,
    activityLevel,
    goal,
    diet,
    useAutoGoals,
  ]);

  const proteinCalories = Number(proteinGoal) * 4;
  const carbCalories = Number(carbGoal) * 4;
  const fatCalories = Number(fatGoal) * 9;
  const macroTotalCalories = proteinCalories + carbCalories + fatCalories;

  const proteinPercent =
    macroTotalCalories > 0
      ? Math.round((proteinCalories / macroTotalCalories) * 100)
      : 0;

  const carbPercent =
    macroTotalCalories > 0
      ? Math.round((carbCalories / macroTotalCalories) * 100)
      : 0;

  const fatPercent =
    macroTotalCalories > 0
      ? Math.round((fatCalories / macroTotalCalories) * 100)
      : 0;

  const handleCancel = () => {
    setName("Dev Bollam");
    setEmail("dev@example.com");
    setAge("22");
    setSex("Male");
    setHeightFeet("5");
    setHeightInches("10");
    setWeight("180");
    setActivityLevel("Moderately Active");
    setGoal("Lean Bulk");
    setDiet("High Protein");
    setDailyCalories("2300");
    setProteinGoal("180");
    setCarbGoal("220");
    setFatGoal("70");
    setUseAutoGoals(true);
    setIsEditing(false);
  };

  const handleSave = () => {
    setIsEditing(false);
  };

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
            width={42}
            height={42}
            className="object-contain drop-shadow-[0_0_14px_rgba(16,185,129,0.45)]"
            priority
          />
          <div className="leading-tight">
            <p className="text-sm text-white/70">
              Voice-first calorie tracking
            </p>
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
          <Link href="/journal" className="hover:text-white">
            Journal
          </Link>
          <Link href="/profile" className="text-emerald-300">
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
              Profile
            </p>
            <h1 className="mt-3 text-4xl font-semibold tracking-tight md:text-5xl">
              Your account
            </h1>
            <p className="mt-4 max-w-2xl text-lg text-white/70">
              Personalized nutrition targets based on your body metrics,
              activity level, and goals.
            </p>
          </div>

          <div className="flex gap-3">
            {!isEditing ? (
              <button
                onClick={() => setIsEditing(true)}
                className="rounded-full bg-emerald-500 px-5 py-3 text-sm font-semibold text-[#08131a] transition hover:bg-emerald-400"
              >
                Edit Profile
              </button>
            ) : (
              <>
                <button
                  onClick={handleSave}
                  className="rounded-full bg-emerald-500 px-5 py-3 text-sm font-semibold text-[#08131a] transition hover:bg-emerald-400"
                >
                  Save Changes
                </button>
                <button
                  onClick={handleCancel}
                  className="rounded-full bg-white/10 px-5 py-3 text-sm font-semibold text-white ring-1 ring-white/15 transition hover:bg-white/15"
                >
                  Cancel
                </button>
              </>
            )}
          </div>
        </div>

        <div className="grid gap-8 lg:grid-cols-[0.9fr_1.1fr]">
          <div className="space-y-6">
            <div className="rounded-[32px] bg-white/5 p-6 ring-1 ring-white/10 backdrop-blur">
              <div className="flex items-center gap-4">
                <div className="flex h-20 w-20 items-center justify-center rounded-full bg-emerald-500/15 ring-1 ring-emerald-500/20">
                  <span className="text-2xl font-semibold text-emerald-300">
                    {name.charAt(0)}
                  </span>
                </div>
                <div>
                  <p className="text-sm text-white/60">Account holder</p>
                  <h2 className="mt-1 text-2xl font-semibold">{name}</h2>
                  <p className="mt-1 text-sm text-white/60">{email}</p>
                </div>
              </div>
            </div>

            <div className="rounded-[32px] bg-white/5 p-6 ring-1 ring-white/10 backdrop-blur">
              <p className="text-sm text-white/60">Quick overview</p>
              <div className="mt-6 grid grid-cols-2 gap-4">
                <StatCard label="Daily goal" value={`${dailyCalories} kcal`} />
                <StatCard label="Protein goal" value={`${proteinGoal}g`} />
                <StatCard label="Goal type" value={goal} />
                <StatCard label="Diet style" value={diet} />
              </div>
            </div>

            <div className="rounded-[32px] bg-white/5 p-6 ring-1 ring-white/10 backdrop-blur">
              <p className="text-sm text-white/60">Account actions</p>
              <div className="mt-5 space-y-3">
                <button className="w-full rounded-2xl bg-white/10 px-4 py-3 text-left text-sm text-white ring-1 ring-white/10 transition hover:bg-white/15">
                  Notification settings
                </button>
                <button className="w-full rounded-2xl bg-white/10 px-4 py-3 text-left text-sm text-white ring-1 ring-white/10 transition hover:bg-white/15">
                  Connected devices
                </button>
                <button className="w-full rounded-2xl bg-red-500/10 px-4 py-3 text-left text-sm text-red-300 ring-1 ring-red-500/20 transition hover:bg-red-500/15">
                  Log out
                </button>
              </div>
            </div>
          </div>

          <div className="space-y-6">
            <div className="rounded-[32px] bg-white/5 p-6 ring-1 ring-white/10 backdrop-blur">
              <p className="text-sm text-white/60">Personal info</p>
              <h2 className="mt-1 text-2xl font-semibold">Basic details</h2>

              <div className="mt-6 grid gap-4 md:grid-cols-2">
                <Field
                  label="Full name"
                  value={name}
                  editable={isEditing}
                  onChange={setName}
                />
                <Field
                  label="Email"
                  value={email}
                  editable={isEditing}
                  onChange={setEmail}
                />
                <Field
                  label="Age"
                  value={age}
                  editable={isEditing}
                  onChange={setAge}
                />
                <SelectField
                  label="Sex"
                  value={sex}
                  editable={isEditing}
                  onChange={setSex}
                  options={["Male", "Female"]}
                />
              </div>
            </div>

            <div className="rounded-[32px] bg-white/5 p-6 ring-1 ring-white/10 backdrop-blur">
              <p className="text-sm text-white/60">Body metrics</p>
              <h2 className="mt-1 text-2xl font-semibold">
                Personalized inputs
              </h2>

              <div className="mt-6 grid gap-4 md:grid-cols-2">
                <Field
                  label="Weight (lb)"
                  value={weight}
                  editable={isEditing}
                  onChange={setWeight}
                />

                <div className="rounded-2xl bg-black/20 p-4 ring-1 ring-white/10">
                  <p className="text-xs uppercase tracking-wide text-white/50">
                    Height
                  </p>

                  {isEditing ? (
                    <div className="mt-3 flex gap-3">
                      <input
                        value={heightFeet}
                        onChange={(e) => setHeightFeet(e.target.value)}
                        className="w-full rounded-xl bg-white/10 px-3 py-3 text-sm text-white outline-none ring-1 ring-white/10 placeholder:text-white/40"
                        placeholder="ft"
                      />
                      <input
                        value={heightInches}
                        onChange={(e) => setHeightInches(e.target.value)}
                        className="w-full rounded-xl bg-white/10 px-3 py-3 text-sm text-white outline-none ring-1 ring-white/10 placeholder:text-white/40"
                        placeholder="in"
                      />
                    </div>
                  ) : (
                    <p className="mt-3 text-base font-medium text-white">
                      {heightFeet}&apos; {heightInches}&quot;
                    </p>
                  )}
                </div>

                <SelectField
                  label="Activity level"
                  value={activityLevel}
                  editable={isEditing}
                  onChange={setActivityLevel}
                  options={[
                    "Sedentary",
                    "Lightly Active",
                    "Moderately Active",
                    "Very Active",
                  ]}
                />

                <SelectField
                  label="Fitness goal"
                  value={goal}
                  editable={isEditing}
                  onChange={setGoal}
                  options={[
                    "Fat Loss",
                    "Maintenance",
                    "Lean Bulk",
                    "Muscle Gain",
                  ]}
                />

                <SelectField
                  label="Diet preference"
                  value={diet}
                  editable={isEditing}
                  onChange={setDiet}
                  options={[
                    "High Protein",
                    "Balanced",
                    "Low Carb",
                    "Keto",
                    "Vegetarian",
                    "Vegan",
                  ]}
                />
              </div>
            </div>

            <div className="rounded-[32px] bg-white/5 p-6 ring-1 ring-white/10 backdrop-blur">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-sm text-white/60">Nutrition targets</p>
                  <h2 className="mt-1 text-2xl font-semibold">
                    Recommended daily goals
                  </h2>
                  <p className="mt-2 max-w-2xl text-sm text-white/55">
                    Smart mode recommends calories and macros from your body
                    metrics. Manual mode lets you override them.
                  </p>
                </div>

                <div className="rounded-2xl bg-black/20 px-4 py-3 ring-1 ring-white/10">
                  <p className="text-xs uppercase tracking-wide text-white/45">
                    Goal mode
                  </p>
                  <button
                    onClick={() => setUseAutoGoals((prev) => !prev)}
                    disabled={!isEditing}
                    className={`mt-2 rounded-full px-3 py-1.5 text-xs font-medium transition ${
                      useAutoGoals
                        ? "bg-emerald-500 text-[#08131a]"
                        : "bg-white/10 text-white"
                    } ${!isEditing ? "opacity-60 cursor-not-allowed" : ""}`}
                  >
                    {useAutoGoals ? "Smart Auto" : "Manual Override"}
                  </button>
                </div>
              </div>

              <div className="mt-6 grid gap-6 lg:grid-cols-[1.15fr_0.85fr]">
                <div className="rounded-[28px] bg-black/20 p-6 ring-1 ring-white/10">
                  <p className="text-xs uppercase tracking-wide text-white/50">
                    Main target
                  </p>
                  <h3 className="mt-2 text-xl font-semibold text-white">
                    Daily Calorie Goal
                  </h3>

                  {isEditing && !useAutoGoals ? (
                    <div className="mt-5">
                      <label className="mb-2 block text-sm text-white/65">
                        Calories per day
                      </label>
                      <input
                        value={dailyCalories}
                        onChange={(e) => setDailyCalories(e.target.value)}
                        className="w-full rounded-2xl bg-white/10 px-4 py-3 text-lg font-semibold text-white outline-none ring-1 ring-white/10 placeholder:text-white/35"
                        placeholder="2300"
                      />
                      <p className="mt-3 text-xs text-white/45">
                        Manual mode is active. You can directly edit this value.
                      </p>
                    </div>
                  ) : (
                    <div className="mt-5">
                      <p className="text-5xl font-semibold tracking-tight text-emerald-300">
                        {dailyCalories}
                      </p>
                      <p className="mt-2 text-sm text-white/60">kcal per day</p>
                    </div>
                  )}
                </div>

                <div className="grid gap-4">
                  <MacroGoalCard
                    label="Protein Goal"
                    value={proteinGoal}
                    unit="g"
                    color="text-emerald-300"
                    editable={isEditing && !useAutoGoals}
                    onChange={setProteinGoal}
                  />
                  <MacroGoalCard
                    label="Carb Goal"
                    value={carbGoal}
                    unit="g"
                    color="text-yellow-300"
                    editable={isEditing && !useAutoGoals}
                    onChange={setCarbGoal}
                  />
                  <MacroGoalCard
                    label="Fat Goal"
                    value={fatGoal}
                    unit="g"
                    color="text-pink-300"
                    editable={isEditing && !useAutoGoals}
                    onChange={setFatGoal}
                  />
                </div>
              </div>

              <div className="mt-6 rounded-3xl bg-black/20 p-5 ring-1 ring-white/10">
                <p className="text-sm font-medium text-white/80">
                  Goal strategy
                </p>
                <p className="mt-2 text-sm leading-6 text-white/60">
                  Smart mode estimates your calories from body weight, height,
                  age, sex, and activity level, then adjusts macros for your
                  fitness goal and diet style. Manual mode lets advanced users
                  set their own exact numbers.
                </p>
              </div>

              <div className="mt-6 rounded-3xl bg-black/20 p-5 ring-1 ring-white/10">
                <div className="flex items-center justify-between">
                  <p className="text-sm font-medium text-white/80">
                    Macro distribution
                  </p>
                  <p className="text-xs text-white/45">
                    Based on current targets
                  </p>
                </div>

                <div className="mt-5 space-y-4">
                  <MacroBar
                    label="Protein"
                    grams={proteinGoal}
                    percent={proteinPercent}
                    color="bg-emerald-400"
                    textColor="text-emerald-300"
                  />
                  <MacroBar
                    label="Carbs"
                    grams={carbGoal}
                    percent={carbPercent}
                    color="bg-yellow-400"
                    textColor="text-yellow-300"
                  />
                  <MacroBar
                    label="Fats"
                    grams={fatGoal}
                    percent={fatPercent}
                    color="bg-pink-400"
                    textColor="text-pink-300"
                  />
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}

function Field({
  label,
  value,
  editable,
  onChange,
}: {
  label: string;
  value: string;
  editable: boolean;
  onChange: (value: string) => void;
}) {
  return (
    <div className="rounded-2xl bg-black/20 p-4 ring-1 ring-white/10">
      <p className="text-xs uppercase tracking-wide text-white/50">{label}</p>

      {editable ? (
        <input
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="mt-3 w-full rounded-xl bg-white/10 px-3 py-3 text-sm text-white outline-none ring-1 ring-white/10 placeholder:text-white/40"
        />
      ) : (
        <p className="mt-3 text-base font-medium text-white">{value}</p>
      )}
    </div>
  );
}

function SelectField({
  label,
  value,
  editable,
  onChange,
  options,
}: {
  label: string;
  value: string;
  editable: boolean;
  onChange: (value: string) => void;
  options: string[];
}) {
  return (
    <div className="rounded-2xl bg-black/20 p-4 ring-1 ring-white/10">
      <p className="text-xs uppercase tracking-wide text-white/50">{label}</p>

      {editable ? (
        <select
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="mt-3 w-full rounded-xl bg-white/10 px-3 py-3 text-sm text-white outline-none ring-1 ring-white/10"
        >
          {options.map((option) => (
            <option
              key={option}
              value={option}
              className="bg-[#111827] text-white"
            >
              {option}
            </option>
          ))}
        </select>
      ) : (
        <p className="mt-3 text-base font-medium text-white">{value}</p>
      )}
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl bg-black/20 p-4 ring-1 ring-white/10">
      <p className="text-xs uppercase tracking-wide text-white/50">{label}</p>
      <p className="mt-2 text-lg font-semibold text-white">{value}</p>
    </div>
  );
}

function MacroGoalCard({
  label,
  value,
  unit,
  color,
  editable,
  onChange,
}: {
  label: string;
  value: string;
  unit: string;
  color: string;
  editable: boolean;
  onChange: (value: string) => void;
}) {
  return (
    <div className="rounded-2xl bg-black/20 p-4 ring-1 ring-white/10">
      <p className="text-xs uppercase tracking-wide text-white/50">{label}</p>

      {editable ? (
        <div className="mt-3 flex items-center gap-2">
          <input
            value={value}
            onChange={(e) => onChange(e.target.value)}
            className="w-full rounded-xl bg-white/10 px-3 py-3 text-sm text-white outline-none ring-1 ring-white/10 placeholder:text-white/40"
            placeholder="0"
          />
          <span className="text-sm text-white/50">{unit}</span>
        </div>
      ) : (
        <p className={`mt-3 text-2xl font-semibold ${color}`}>
          {value}
          <span className="ml-1 text-base text-white/55">{unit}</span>
        </p>
      )}
    </div>
  );
}

function MacroBar({
  label,
  grams,
  percent,
  color,
  textColor,
}: {
  label: string;
  grams: string;
  percent: number;
  color: string;
  textColor: string;
}) {
  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className={`text-sm font-medium ${textColor}`}>{label}</span>
          <span className="text-xs text-white/45">{grams}g</span>
        </div>
        <span className="text-sm text-white/70">{percent}%</span>
      </div>

      <div className="h-2.5 w-full rounded-full bg-white/10">
        <div
          className={`h-2.5 rounded-full ${color} transition-all duration-300`}
          style={{ width: `${percent}%` }}
        />
      </div>
    </div>
  );
}
