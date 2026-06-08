import React from "react";
import { BookOpen, CalendarClock, CheckCircle2, GraduationCap, Plus, RefreshCw, Target, Timer, TrendingUp } from "lucide-react";
import { api } from "../lib/api";

type AnyRecord = Record<string, any>;

const panel = "rounded-lg border border-amber-200/10 bg-white/[0.04] p-4";
const button = "inline-flex h-9 items-center gap-2 rounded-lg bg-amber-300 px-3 text-sm font-medium text-black hover:bg-amber-200 disabled:cursor-not-allowed disabled:opacity-50";
const ghost = "inline-flex h-9 items-center gap-2 rounded-lg border border-amber-200/15 px-3 text-sm text-amber-100 hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-50";
const input = "h-10 w-full rounded-lg border border-amber-200/10 bg-black/25 px-3 text-sm text-amber-50 outline-none placeholder:text-slate-500 focus:border-amber-300/50";

export function StudyAssistant() {
  const [data, setData] = React.useState<AnyRecord | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState("");
  const [subjectName, setSubjectName] = React.useState("DBMS");
  const [examDate, setExamDate] = React.useState("");
  const [topics, setTopics] = React.useState("ER Model,SQL Normalization,Transactions,Indexing,Recovery");
  const [sessionMinutes, setSessionMinutes] = React.useState(25);

  const refresh = React.useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setData(await api<AnyRecord>("/evolution/study/dashboard"));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load study dashboard");
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    void refresh();
  }, [refresh]);

  const run = async (operation: () => Promise<unknown>) => {
    setLoading(true);
    setError("");
    try {
      await operation();
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Study action failed");
    } finally {
      setLoading(false);
    }
  };

  const subjects = data?.subjects ?? [];
  const exams = data?.exams ?? [];
  const revisions = data?.revisions ?? [];
  const recommendations = data?.recommendations ?? [];
  const goals = data?.goals ?? [];
  const sessions = data?.sessions ?? [];
  const achievements = data?.achievements ?? [];
  const firstSubject = subjects[0];

  return (
    <div className="space-y-5">
      <section className="flex flex-col gap-3 border-b border-amber-200/10 pb-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <div className="flex items-center gap-2 text-sm text-amber-200/70"><GraduationCap size={16} /> Smart Study Assistant</div>
          <h1 className="mt-1 text-2xl font-semibold text-amber-50">Study Planner, Exam Coach, Progress Tracker</h1>
          <p className="mt-1 max-w-3xl text-sm text-slate-400">Plan exams, track chapters, schedule revisions, record study sessions, and keep preparation visible offline.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button className={ghost} onClick={refresh} disabled={loading}><RefreshCw size={16} /> Refresh</button>
          <button className={button} onClick={() => run(() => api("/evolution/study/sessions", { method: "POST", body: JSON.stringify({ subject_id: firstSubject?.id, subject_name: firstSubject?.name ?? subjectName, duration_minutes: sessionMinutes, session_type: "study" }) }))} disabled={loading}><Timer size={16} /> Record Session</button>
        </div>
      </section>

      {error && <div className="rounded-lg border border-red-400/25 bg-red-500/10 p-3 text-sm text-red-100">{error}</div>}

      <section className="grid gap-4 xl:grid-cols-4">
        <Metric title="Readiness" value={`${Math.round(data?.readiness_score ?? 0)}%`} icon={<TrendingUp size={18} />} />
        <Metric title="Study Today" value={`${Math.round((data?.today_study_seconds ?? 0) / 60)}m`} icon={<Timer size={18} />} />
        <Metric title="Subjects" value={subjects.length} icon={<BookOpen size={18} />} />
        <Metric title="Upcoming Exams" value={exams.length} icon={<CalendarClock size={18} />} />
      </section>

      <section className="grid gap-4 xl:grid-cols-[1fr_0.85fr]">
        <div className={panel}>
          <h2 className="mb-3 flex items-center gap-2 text-lg font-semibold text-amber-50"><Plus size={18} /> Create Study Strategy</h2>
          <div className="grid gap-3 md:grid-cols-2">
            <input className={input} value={subjectName} onChange={(event) => setSubjectName(event.target.value)} placeholder="Subject" />
            <input className={input} type="date" value={examDate} onChange={(event) => setExamDate(event.target.value)} />
            <input className={`${input} md:col-span-2`} value={topics} onChange={(event) => setTopics(event.target.value)} placeholder="Chapters or topics, comma separated" />
            <input className={input} type="number" min={1} value={sessionMinutes} onChange={(event) => setSessionMinutes(Number(event.target.value))} />
            <button className={button} onClick={() => run(() => api("/evolution/study/plans", { method: "POST", body: JSON.stringify({ title: `${subjectName} Exam Plan`, subject_name: subjectName, exam_date: examDate, topics: topics.split(",").map((item) => item.trim()).filter(Boolean), priority: "high" }) }))} disabled={loading}>Create Plan</button>
          </div>
        </div>

        <div className={panel}>
          <h2 className="mb-3 flex items-center gap-2 text-lg font-semibold text-amber-50"><Target size={18} /> Coach Recommendations</h2>
          <div className="space-y-2">
            {recommendations.map((item: AnyRecord, index: number) => (
              <div key={`${item.title}-${index}`} className="rounded-lg border border-white/10 bg-black/20 p-3 text-sm">
                <div className="font-medium text-amber-100">{item.title}</div>
                <div className="mt-1 text-slate-400">{item.message}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        <Panel title="Subjects" icon={<BookOpen size={18} />}>
          {subjects.length === 0 ? <Empty text="No subjects yet." /> : subjects.map((subject: AnyRecord) => (
            <div key={subject.id} className="rounded-lg border border-white/10 bg-black/20 p-3">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="font-medium text-amber-100">{subject.name}</div>
                  <div className="text-xs text-slate-500">{subject.chapters_completed}/{subject.chapters_total} chapters complete</div>
                </div>
                <div className="text-right text-sm text-amber-100">{Math.round(subject.readiness_score)}%</div>
              </div>
              <div className="mt-3 h-2 overflow-hidden rounded-full bg-white/10"><div className="h-full bg-amber-300" style={{ width: `${subject.completion_percent}%` }} /></div>
              <div className="mt-3 grid gap-2">
                {(subject.chapters ?? []).slice(0, 5).map((chapter: AnyRecord) => (
                  <button key={chapter.id} className="flex items-center justify-between rounded-md border border-white/10 px-3 py-2 text-left text-sm hover:bg-white/10" onClick={() => run(() => api(`/evolution/study/chapters/${chapter.id}/progress`, { method: "PUT", body: JSON.stringify({ completion_percent: 100, status: "completed" }) }))}>
                    <span className="text-slate-300">{chapter.title}</span>
                    <span className="text-xs text-slate-500">{Math.round(chapter.completion_percent)}%</span>
                  </button>
                ))}
              </div>
            </div>
          ))}
        </Panel>

        <Panel title="Exam Countdowns" icon={<CalendarClock size={18} />}>
          {exams.length === 0 ? <Empty text="No exams configured." /> : exams.map((exam: AnyRecord) => (
            <div key={exam.id} className="flex items-center justify-between gap-3 rounded-lg border border-white/10 bg-black/20 p-3 text-sm">
              <div>
                <div className="font-medium text-amber-100">{exam.title}</div>
                <div className="text-slate-500">{exam.preparation_status}</div>
              </div>
              <div className="text-right">
                <div className="text-amber-100">{exam.days_remaining ?? "--"} days</div>
                <div className="text-xs text-slate-500">{Math.round(exam.readiness_score)}% ready</div>
              </div>
            </div>
          ))}
        </Panel>
      </section>

      <section className="grid gap-4 xl:grid-cols-3">
        <Summary title="Revision Plan" icon={<RefreshCw size={18} />} items={revisions.slice(0, 8).map((item: AnyRecord) => `${item.scheduled_date}: ${item.title}`)} />
        <Summary title="Study Goals" icon={<Target size={18} />} items={goals.slice(0, 8).map((item: AnyRecord) => `${item.title}: ${Math.round(item.progress_percent)}%`)} />
        <Summary title="Achievements" icon={<CheckCircle2 size={18} />} items={achievements.slice(0, 8).map((item: AnyRecord) => item.title)} />
      </section>

      <Panel title="Recent Study Sessions" icon={<Timer size={18} />}>
        {sessions.length === 0 ? <Empty text="No study sessions recorded." /> : sessions.slice(0, 10).map((session: AnyRecord) => (
          <div key={session.id} className="flex items-center justify-between gap-3 border-b border-white/10 py-2 text-sm last:border-b-0">
            <span className="text-slate-300">{session.subject_name || session.topic || "Study Session"}</span>
            <span className="text-slate-500">{Math.round(session.duration_seconds / 60)}m</span>
          </div>
        ))}
      </Panel>
    </div>
  );
}

function Metric({ title, value, icon }: { title: string; value: React.ReactNode; icon: React.ReactNode }) {
  return <div className={panel}><div className="mb-2 flex items-center gap-2 text-sm text-slate-400">{icon}{title}</div><div className="text-2xl font-semibold text-amber-50">{value}</div></div>;
}

function Panel({ title, icon, children }: { title: string; icon: React.ReactNode; children: React.ReactNode }) {
  return <div className={panel}><h2 className="mb-3 flex items-center gap-2 text-lg font-semibold text-amber-50">{icon}{title}</h2><div className="space-y-2">{children}</div></div>;
}

function Summary({ title, icon, items }: { title: string; icon: React.ReactNode; items: string[] }) {
  return <Panel title={title} icon={icon}>{items.length === 0 ? <Empty text="Nothing scheduled yet." /> : items.map((item) => <div key={item} className="rounded-lg border border-white/10 bg-black/20 p-3 text-sm text-slate-300">{item}</div>)}</Panel>;
}

function Empty({ text }: { text: string }) {
  return <div className="rounded-lg border border-white/10 bg-black/20 p-3 text-sm text-slate-500">{text}</div>;
}
