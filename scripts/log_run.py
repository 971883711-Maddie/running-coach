#!/usr/bin/env python3
"""
记录一次跑步 / 基线测试到日志。
Usage:
    # 日常跑步记录
    python3 log_run.py --date 2026-06-18 --distance 5 --duration 28 --pace "5:36" --hr 152 --cadence 172 --rpe 6 --note "晨跑" --file runner-data.json

    # 阶段3 基线测试记录
    python3 log_run.py --baseline --date 2026-06-18 --distance 1 --duration 8 --pace "8:00" --hr 158 --max-hr 172 --cadence 164 --rpe 7 --note "1km慢跑测试" --file runner-data.json
"""
import argparse, json
from datetime import date
from pathlib import Path


def calc_pace(distance, duration):
    if distance and duration and distance > 0:
        secs_per_km = (duration * 60) / distance
        return f"{int(secs_per_km // 60)}:{int(secs_per_km % 60):02d}"
    return None


def main():
    ap = argparse.ArgumentParser(description="记录一次跑步 / 基线测试")
    ap.add_argument("--date", default=None)
    ap.add_argument("--distance", type=float, default=None)
    ap.add_argument("--duration", type=float, default=None, help="分钟")
    ap.add_argument("--pace", default=None, help="5:23 格式")
    ap.add_argument("--hr", type=int, default=None, dest="hr", help="平均心率")
    ap.add_argument("--max-hr", type=int, default=None, dest="max_hr", help="最大心率（基线测试用）")
    ap.add_argument("--cadence", type=int, default=None, help="步频 spm")
    ap.add_argument("--rpe", type=int, default=None, help="主观劳累度 1-10")
    ap.add_argument("--surface", default="", help="路面：塑胶/柏油/跑步机/越野")
    ap.add_argument("--note", default="")
    ap.add_argument("--baseline", action="store_true", help="记录为阶段3基线测试数据")
    ap.add_argument("--file", default="runner-data.json")
    args = ap.parse_args()

    if args.date is None:
        args.date = date.today().isoformat()

    pace = args.pace
    if not pace and args.distance and args.duration:
        pace = calc_pace(args.distance, args.duration)

    entry = {
        "date": args.date,
        "distance_km": args.distance,
        "duration_min": args.duration,
        "pace": pace,
        "avg_hr": args.hr,
        "max_hr": args.max_hr,
        "cadence": args.cadence,
        "rpe": args.rpe,
        "surface": args.surface,
        "note": args.note,
    }

    p = Path(args.file)
    data = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}

    if args.baseline:
        data.setdefault("stage3_baselines", []).append(entry)
        print(f"✅ 已记录基线测试（阶段3） {args.date}")
        print(f"   距离 {args.distance} km | 时长 {args.duration} min | 配速 {pace}")
        print(f"   心率 {args.hr}/{args.max_hr} | 步频 {args.cadence} | RPE {args.rpe}")
        print(f"\n   接下来运行：python3 analyze.py --baseline --file {args.file} 生成基线分析")
    else:
        entry["type"] = "run"
        data.setdefault("logs", []).append(entry)
        print(f"✅ 已记录 {args.date} 的跑步")
        print(f"   距离 {args.distance} km | 时长 {args.duration} min | 配速 {pace} | 心率 {args.hr} | 步频 {args.cadence} | RPE {args.rpe}")

    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    # 日常跑步记录后：自动回流检测
    if not args.baseline:
        alerts = check_reentry_alerts(data)
        if alerts:
            print("\n" + "=" * 55)
            print("  ⚠️ 回流检测：发现以下异常，建议重新评估")
            print("=" * 55)
            for a in alerts:
                print(f"  {a}")


def check_reentry_alerts(data):
    """记录后自动检测异常，返回告警列表。触发时建议回到阶段3或调整阶段4。"""
    alerts = []
    logs = data.get("logs", [])
    if len(logs) < 1:
        return alerts

    last = logs[-1]
    recent = logs[-5:] if len(logs) >= 5 else logs[:]

    # 1. RPE 连续≥8（疲劳/过度训练）
    if len(recent) >= 3:
        rpes = [l.get("rpe") for l in recent if l.get("rpe") is not None]
        if len(rpes) >= 3 and all(r >= 8 for r in rpes[-3:]):
            alerts.append("🔴 连续3次 RPE≥8，配速无提升 → 疑似过度训练，建议减量并回到阶段3重评体能")

    # 2. RPE 单次≥9（急性疲劳）
    if last.get("rpe") and last["rpe"] >= 9:
        alerts.append("🔴 本次 RPE≥9，主观劳累极高 → 建议休息2-3天，下次训练降强度")

    # 3. 跑量递进超阈值（10%原则，caution者8%）
    screening = data.get("stage2_screening", {})
    threshold = 0.08 if screening.get("screening_result") == "caution" else 0.10
    if len(logs) >= 2:
        this_week_km, last_week_km = calc_weekly_km(logs, weeks=2)
        if last_week_km > 0 and this_week_km > 0:
            inc = (this_week_km - last_week_km) / last_week_km
            if inc > threshold:
                alerts.append(f"🔴 本周跑量较上周增长 {inc*100:.0f}%，超过 {threshold*100:.0f}% 原则 → 伤病风险，建议减量")

    # 4. 同等心率下配速不进反退（4周内）
    if len(logs) >= 4:
        hr_runs = [l for l in logs[-10:] if l.get("avg_hr") and l.get("pace")]
        if len(hr_runs) >= 4:
            # 取心率相近（±5bpm）的两次对比
            recent_run = hr_runs[-1]
            comparable = [l for l in hr_runs[:-1] if abs(l["avg_hr"] - recent_run["avg_hr"]) <= 5]
            if comparable:
                old = comparable[-1]
                old_pace = parse_pace_secs(old["pace"])
                new_pace = parse_pace_secs(recent_run["pace"])
                if new_pace > old_pace + 15:  # 配速慢15秒以上
                    alerts.append("🟡 同等心率下配速较此前慢15秒+ → 可能有氧能力退步或疲劳累积，建议回到阶段3重测基线")

    # 5. 新疼痛记录（note含痛/疼/不适）
    pain_keywords = ["痛", "疼", "不适", "酸", "胀"]
    note = last.get("note", "") or ""
    if any(kw in note for kw in pain_keywords):
        # 检查是否已记录到injuries
        existing_parts = [i.get("part", "") for i in screening.get("injuries", [])]
        alerts.append(f"🟡 本次记录含不适描述「{note}」→ 若是新伤，建议记录到阶段2伤病列表并回到阶段3评估")

    # 6. 心率异常偏高（Z5区间且非间歇训练）
    baseline = data.get("stage3_analysis", {})
    hr_zones = baseline.get("hr_zones", {})
    if last.get("avg_hr") and hr_zones.get("Z5"):
        z5_lo = parse_hr_str(hr_zones["Z5"])
        if z5_lo and last["avg_hr"] > z5_lo and last.get("rpe", 0) < 7:
            alerts.append("🟡 心率进入Z5但RPE不高 → 可能心率漂移或环境因素，留意有氧耐力")

    return alerts


def calc_weekly_km(logs, weeks=2):
    """返回本周和上周跑量。"""
    from datetime import datetime, timedelta
    today = datetime.now().date()
    week_start = today - timedelta(days=today.weekday())
    this_week = sum(l.get("distance_km", 0) or 0 for l in logs
                    if _in_week(l.get("date", ""), week_start))
    last_week_start = week_start - timedelta(days=7)
    last_week = sum(l.get("distance_km", 0) or 0 for l in logs
                    if _in_week(l.get("date", ""), last_week_start))
    return this_week, last_week


def _in_week(date_str, week_start):
    from datetime import datetime, timedelta
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
        return week_start <= d < week_start + timedelta(days=7)
    except (ValueError, TypeError):
        return False


def parse_pace_secs(pace_str):
    try:
        parts = pace_str.split(":")
        return int(parts[0]) * 60 + int(parts[1])
    except (ValueError, IndexError):
        return 0


def parse_hr_str(hr_str):
    """'>165' 或 '153-165' → 取下限/单一值。"""
    try:
        s = hr_str.replace(">", "").replace("<", "").strip()
        if "-" in s:
            return int(s.split("-")[0])
        return int(s)
    except (ValueError, TypeError):
        return None


if __name__ == "__main__":
    main()
